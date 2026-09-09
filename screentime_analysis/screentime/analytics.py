"""주간 집계·비교·데이터 품질 (계획서 5.3, 7.1).

핵심 규칙:
- ``*_total_ms``는 **complete 구간만** 합산한다. partial의 확인된 값은 per_day에만 보인다.
- 유효 구간이 하나도 없으면 합계는 0이 아니라 ``None``이다.
- 평균은 해당 주의 complete 구간이 7개일 때만 반환한다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from .missions import evaluate_mission, night_observation, observed_for_mission
from .models import (
    AnalysisInput,
    AppMetrics,
    Comparison,
    DayMetrics,
    MissionResult,
    Quality,
    WeeklyMetrics,
    WeekStatus,
    WindowAggregate,
)
from .windows import daily_window, night_windows, previous_week_start, week_dates

DAYS_PER_WEEK = 7


@dataclass
class WeekTotals:
    """한 주의 확정 집계. 비교를 위해 현재 주와 이전 주에 같은 계산을 쓴다."""

    valid_days: int = 0
    valid_nights: int = 0
    selected_total_ms: int | None = None
    all_apps_total_ms: int | None = None
    pre_bed_total_ms: int | None = None
    after_bed_total_ms: int | None = None
    night_total_ms: int | None = None
    per_app_day_ms: dict[str, int] = field(default_factory=dict)
    per_app_night_ms: dict[str, int] = field(default_factory=dict)

    @property
    def is_full(self) -> bool:
        return self.valid_days == DAYS_PER_WEEK


def index_aggregates(aggregates: list[WindowAggregate]) -> dict[tuple[dt.date, str], WindowAggregate]:
    return {(a.anchor_date, a.kind): a for a in aggregates}


def _accumulate(totals: dict[str, int], aggregate: WindowAggregate) -> None:
    for app in aggregate.apps or []:
        totals[app.package_name] = totals.get(app.package_name, 0) + app.duration_ms


def week_totals(request: AnalysisInput, week_start: dt.date) -> WeekTotals:
    """complete 구간만 사용해 한 주를 합산한다."""
    index = index_aggregates(request.aggregates)
    packages = request.target_packages
    result = WeekTotals()

    selected = all_apps = pre_bed = after_bed = night = 0
    has_daily = has_pre = has_after = has_night = False

    for day in week_dates(week_start):
        daily = index.get((day, "daily"))
        if daily is not None and daily.quality == "complete":
            result.valid_days += 1
            has_daily = True
            selected += daily.total_ms(packages) or 0
            all_apps += daily.total_ms() or 0
            _accumulate(result.per_app_day_ms, daily)

        pre = index.get((day, "pre_bed"))
        if pre is not None and pre.quality == "complete":
            has_pre = True
            pre_bed += pre.total_ms(packages) or 0

        post = index.get((day, "after_bed"))
        if post is not None and post.quality == "complete":
            has_after = True
            after_bed += post.total_ms(packages) or 0

        night_ms, night_quality = night_observation(pre, post, packages)
        if night_quality == "complete" and night_ms is not None:
            result.valid_nights += 1
            has_night = True
            night += night_ms
            for window in (pre, post):
                if window is not None:
                    _accumulate(result.per_app_night_ms, window)

    result.selected_total_ms = selected if has_daily else None
    result.all_apps_total_ms = all_apps if has_daily else None
    result.pre_bed_total_ms = pre_bed if has_pre else None
    result.after_bed_total_ms = after_bed if has_after else None
    result.night_total_ms = night if has_night else None
    return result


def get_week_status(request: AnalysisInput) -> WeekStatus:
    """계획서 5.3의 네 가지 상태."""
    profile = request.profile
    last_end = 0
    for day in week_dates(request.week_start):
        _, post = night_windows(day, profile)
        last_end = max(last_end, daily_window(day, profile).end_ms, post.end_ms)

    if request.as_of_ms < last_end:
        return "in_progress"

    attempt = request.last_collection_attempt_ms
    if attempt is None or attempt < last_end:
        # 구간은 끝났지만 그 뒤로 수집을 시도한 적이 없다.
        return "awaiting_data"

    totals = week_totals(request, request.week_start)
    if totals.valid_days == DAYS_PER_WEEK and totals.valid_nights == DAYS_PER_WEEK:
        return "ready"
    return "insufficient_data"


def _pct(numerator: int, denominator: int | None) -> float | None:
    """분모가 0이거나 없으면 null. `0분 -> 20분`을 무한대로 만들지 않는다."""
    if not denominator:
        return None
    return round(numerator / denominator * 100, 2)


def _build_comparison(current: WeekTotals, previous: WeekTotals, has_previous: bool) -> Comparison:
    if not has_previous:
        return Comparison(
            comparable=False,
            reason="NO_PREVIOUS_WEEK_DATA",
            selected_delta_ms=None,
            selected_delta_pct=None,
            all_apps_delta_ms=None,
        )
    if not (current.is_full and previous.is_full):
        # 완전한 두 주가 아니면 정식 증감률을 만들지 않는다.
        return Comparison(
            comparable=False,
            reason="INCOMPLETE_WEEK",
            selected_delta_ms=None,
            selected_delta_pct=None,
            all_apps_delta_ms=None,
        )

    delta = (current.selected_total_ms or 0) - (previous.selected_total_ms or 0)
    return Comparison(
        comparable=True,
        reason=None,
        selected_delta_ms=delta,
        selected_delta_pct=_pct(delta, previous.selected_total_ms),
        all_apps_delta_ms=(current.all_apps_total_ms or 0) - (previous.all_apps_total_ms or 0),
    )


def _day_metrics(request: AnalysisInput) -> list[DayMetrics]:
    """per_day는 partial의 확인된 값도 품질과 함께 보여준다."""
    index = index_aggregates(request.aggregates)
    packages = request.target_packages
    rows: list[DayMetrics] = []

    for day in week_dates(request.week_start):
        daily = index.get((day, "daily"))
        pre = index.get((day, "pre_bed"))
        post = index.get((day, "after_bed"))
        rows.append(
            DayMetrics(
                date=day,
                daily_quality=daily.quality if daily else None,
                pre_bed_quality=pre.quality if pre else None,
                after_bed_quality=post.quality if post else None,
                all_apps_ms=daily.total_ms() if daily else None,
                selected_ms=daily.total_ms(packages) if daily else None,
                pre_bed_ms=pre.total_ms(packages) if pre else None,
                after_bed_ms=post.total_ms(packages) if post else None,
            )
        )
    return rows


def _app_metrics(
    request: AnalysisInput, current: WeekTotals, previous: WeekTotals, comparison: Comparison
) -> list[AppMetrics]:
    packages = request.target_packages
    names = sorted(set(current.per_app_day_ms) | set(current.per_app_night_ms))
    rows: list[AppMetrics] = []

    for name in names:
        is_target = name in packages
        total = current.per_app_day_ms.get(name)
        night_total = current.per_app_night_ms.get(name) if name in current.per_app_night_ms else None
        delta_ms = delta_pct = None
        if comparison.comparable:
            before = previous.per_app_day_ms.get(name, 0)
            delta_ms = (total or 0) - before
            delta_pct = _pct(delta_ms, before)

        rows.append(
            AppMetrics(
                package_name=name,
                is_target=is_target,
                total_ms=total,
                share_pct=_pct(total, current.all_apps_total_ms) if total is not None else None,
                night_total_ms=night_total,
                # 야간 비중의 분모는 선택 앱 야간 합계다. 비선택 앱에서는 null이다.
                night_share_pct=(
                    _pct(night_total, current.night_total_ms)
                    if is_target and night_total is not None
                    else None
                ),
                delta_ms=delta_ms,
                delta_pct=delta_pct,
            )
        )
    return rows


def mission_results(request: AnalysisInput) -> list[MissionResult]:
    """입력으로 받은 미션 스냅샷만 판정한다. 미션을 새로 만들지 않는다."""
    results = []
    for mission in sorted(request.missions, key=lambda m: (m.anchor_date, m.kind, m.id)):
        observed, quality = observed_for_mission(request, mission)
        results.append(evaluate_mission(mission, observed, quality, request.as_of_ms))
    return results


def _mission_counts(results: list[MissionResult], request: AnalysisInput) -> dict[str, int]:
    """성공률 분모에서 unknown·in_progress·not_applicable을 제외한다."""
    kinds = {m.id: m.kind for m in request.missions}
    counts = {"daily_success": 0, "daily_evaluable": 0, "night_success": 0, "night_evaluable": 0}
    for result in results:
        kind = kinds.get(result.mission_id)
        if kind is None or result.status not in ("succeeded", "failed"):
            continue
        counts[f"{kind}_evaluable"] += 1
        if result.status == "succeeded":
            counts[f"{kind}_success"] += 1
    return counts


def analyze_week(request: AnalysisInput) -> WeeklyMetrics:
    current = week_totals(request, request.week_start)
    prev_start = previous_week_start(request.week_start)
    has_previous = any(a.anchor_date in set(week_dates(prev_start)) for a in request.aggregates)
    previous = week_totals(request, prev_start) if has_previous else WeekTotals()

    comparison = _build_comparison(current, previous, has_previous)
    results = mission_results(request)
    counts = _mission_counts(results, request)

    full_days = current.valid_days == DAYS_PER_WEEK
    full_nights = current.valid_nights == DAYS_PER_WEEK

    return WeeklyMetrics(
        valid_days=current.valid_days,
        valid_nights=current.valid_nights,
        all_apps_total_ms=current.all_apps_total_ms,
        selected_total_ms=current.selected_total_ms,
        # 평균은 7개가 다 모였을 때만 낸다. 부분 주의 평균은 오해를 만든다.
        selected_daily_mean_ms=(
            (current.selected_total_ms or 0) / DAYS_PER_WEEK if full_days else None
        ),
        selected_night_mean_ms=(
            (current.night_total_ms or 0) / DAYS_PER_WEEK if full_nights else None
        ),
        pre_bed_total_ms=current.pre_bed_total_ms,
        after_bed_total_ms=current.after_bed_total_ms,
        daily_success_count=counts["daily_success"],
        daily_evaluable_count=counts["daily_evaluable"],
        night_success_count=counts["night_success"],
        night_evaluable_count=counts["night_evaluable"],
        per_day=_day_metrics(request),
        per_app=_app_metrics(request, current, previous, comparison),
        comparison=comparison,
    )


__all__ = [
    "Quality",
    "WeekTotals",
    "analyze_week",
    "get_week_status",
    "index_aggregates",
    "mission_results",
    "week_totals",
]
