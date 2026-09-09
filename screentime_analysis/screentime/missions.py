"""목표 제안과 미션 판정 (계획서 8절).

전부 순수 함수다. 여기서 만든 ``Proposal``은 추천이며 활성 미션이 아니다.
실제 수락·저장·활성화는 BE가 한다.
"""

from __future__ import annotations

import datetime as dt
from decimal import ROUND_FLOOR, Decimal

from .models import (
    MINUTE_MS,
    RULES_VERSION,
    AnalysisInput,
    Mission,
    MissionKind,
    MissionResult,
    Proposal,
    Quality,
    WeeklyMetrics,
    WindowAggregate,
)

BASELINE_SAMPLES = 7
#: 직전 주에 이만큼 판정 가능해야 추가 감축을 제안한다.
REQUIRED_EVALUABLE = 7
#: 그중 이만큼 성공해야 한다.
REQUIRED_SUCCESSES = 5

REASON_INITIAL_BASELINE = "INITIAL_BASELINE"
REASON_REDUCE_AFTER_SUCCESS = "REDUCE_AFTER_SUCCESS"
REASON_MAINTAIN_INSUFFICIENT_SUCCESS = "MAINTAIN_INSUFFICIENT_SUCCESS"
REASON_MAINTAIN_AT_FINAL_GOAL = "MAINTAIN_AT_FINAL_GOAL"
REASON_LOW_USAGE_NO_TARGET = "LOW_USAGE_NO_TARGET"


def reduce_target(reference_ms: int, final_goal_ms: int) -> int:
    """기준값에서 10% 낮춘 분 단위 목표. 최종 목표 아래로 내려가지 않는다.

    작은 양수가 반올림만으로 0이 되지 않게 최소 1분을 유지한다.
    목표 0은 사용자가 최종 목표를 0으로 두고 명시적으로 선택한 경우에만 나온다.
    """
    if reference_ms <= final_goal_ms:
        return reference_ms
    reduced = Decimal(reference_ms) * Decimal("0.90")
    minutes = int((reduced / MINUTE_MS).to_integral_value(rounding=ROUND_FLOOR))
    candidate = max(MINUTE_MS, minutes * MINUTE_MS)
    return min(reference_ms, max(final_goal_ms, candidate))


def _by_kind(aggregates: list[WindowAggregate]) -> dict[tuple[dt.date, str], WindowAggregate]:
    return {(a.anchor_date, a.kind): a for a in aggregates}


def night_observation(
    pre: WindowAggregate | None, post: WindowAggregate | None, packages: set[str]
) -> tuple[int | None, Quality]:
    """야간은 pre_bed와 after_bed가 **둘 다** complete일 때만 complete다."""
    if pre is None or post is None:
        return None, "unavailable"
    if pre.quality == "complete" and post.quality == "complete":
        pre_ms, post_ms = pre.total_ms(packages), post.total_ms(packages)
        if pre_ms is None or post_ms is None:  # pragma: no cover - complete면 항상 값이 있다
            return None, "unavailable"
        return pre_ms + post_ms, "complete"

    if pre.quality == "unavailable" or post.quality == "unavailable":
        quality: Quality = "unavailable"
    else:
        quality = "partial"
    pre_ms, post_ms = pre.total_ms(packages), post.total_ms(packages)
    if pre_ms is None or post_ms is None:
        return None, quality
    return pre_ms + post_ms, quality


def observed_for_mission(request: AnalysisInput, mission: Mission) -> tuple[int | None, Quality]:
    """미션 구간에서 확인된 선택 앱 사용량과 품질."""
    index = _by_kind(request.aggregates)
    packages = request.target_packages
    if mission.kind == "daily":
        agg = index.get((mission.anchor_date, "daily"))
        if agg is None:
            return None, "unavailable"
        return agg.total_ms(packages), agg.quality
    return night_observation(
        index.get((mission.anchor_date, "pre_bed")), index.get((mission.anchor_date, "after_bed")), packages
    )


def evaluate_mission(
    mission: Mission, observed_ms: int | None, quality: str, as_of_ms: int
) -> MissionResult:
    """계획서 8.3의 판정 순서를 그대로 따른다.

    데이터가 없다는 이유로 성공을 만들지 않는다. 확인 불가는 ``unknown``이다.
    """
    if mission.accepted_at_ms > mission.window_start_ms:
        # 구간이 시작한 뒤 수락된 미션은 그 구간의 공식 미션이 아니다 (F12/F16).
        status = "not_applicable"
        reported: int | None = None
    elif as_of_ms < mission.window_end_ms:
        status = "in_progress"
        reported = observed_ms
    elif quality != "complete" or observed_ms is None:
        status = "unknown"
        reported = observed_ms
    elif observed_ms <= mission.target_ms:
        status = "succeeded"
        reported = observed_ms
    else:
        status = "failed"
        reported = observed_ms
    return MissionResult(
        mission_id=mission.id, status=status, observed_ms=reported, evaluated_at_ms=as_of_ms
    )


def baseline_ms(request: AnalysisInput, kind: MissionKind) -> float | None:
    """요청 안의 유효 기록을 날짜순으로 정렬해 **처음 7개**의 평균.

    일일과 야간의 최초 기준선 확보 시점은 다를 수 있다.
    """
    packages = request.target_packages
    index = _by_kind(request.aggregates)
    dates = sorted({a.anchor_date for a in request.aggregates})
    samples: list[int] = []

    for day in dates:
        if kind == "daily":
            agg = index.get((day, "daily"))
            if agg is None or agg.quality != "complete":
                continue
            value = agg.total_ms(packages)
        else:
            value, quality = night_observation(
                index.get((day, "pre_bed")), index.get((day, "after_bed")), packages
            )
            if quality != "complete":
                continue
        if value is None:  # pragma: no cover - complete면 항상 값이 있다
            continue
        samples.append(value)
        if len(samples) == BASELINE_SAMPLES:
            break

    if len(samples) < BASELINE_SAMPLES:
        return None
    return sum(samples) / BASELINE_SAMPLES


def _performance(metrics: WeeklyMetrics, kind: MissionKind) -> tuple[int, int]:
    if kind == "daily":
        return metrics.daily_evaluable_count, metrics.daily_success_count
    return metrics.night_evaluable_count, metrics.night_success_count


def propose_targets(request: AnalysisInput, metrics: WeeklyMetrics) -> list[Proposal]:
    """유형별로 최대 한 개의 제안. 완화는 사용자 직접 수정으로만 가능하다."""
    profile = request.profile
    settings = {
        "daily": (request.current_daily_target_ms, profile.final_daily_ms, profile.temporary_daily_ms),
        "night": (request.current_night_target_ms, profile.final_night_ms, profile.temporary_night_ms),
    }

    proposals: list[Proposal] = []
    for kind in ("daily", "night"):
        current, final_goal, temporary = settings[kind]
        target, reason = _propose_one(request, metrics, kind, current, final_goal, temporary)
        if reason is None:
            continue  # 기준선을 확보하지 못한 유형은 제안을 비워 둔다
        proposals.append(
            Proposal(
                kind=kind,
                target_ms=target,
                reason_code=reason,
                basis_week=request.week_start,
                profile_version=profile.version,
                rules_version=RULES_VERSION,
            )
        )
    return proposals


def _propose_one(
    request: AnalysisInput,
    metrics: WeeklyMetrics,
    kind: MissionKind,
    current: int | None,
    final_goal: int,
    temporary: int,
) -> tuple[int | None, str | None]:
    if current is None:
        baseline = baseline_ms(request, kind)
        if baseline is None:
            return None, None  # 유효 7개가 없으면 제안하지 않는다. 설명이 이유를 알린다.
        if baseline < MINUTE_MS:
            # 초 단위 기준선을 분 단위 목표로 강제 변환하지 않는다.
            return None, REASON_LOW_USAGE_NO_TARGET
        candidate = reduce_target(int(baseline), final_goal)
        # 최초 제안은 임시 목표를 상한으로 삼는다.
        return min(candidate, temporary), REASON_INITIAL_BASELINE

    if current <= final_goal:
        return current, REASON_MAINTAIN_AT_FINAL_GOAL

    evaluable, successes = _performance(metrics, kind)
    if evaluable >= REQUIRED_EVALUABLE and successes >= REQUIRED_SUCCESSES:
        # 완화 금지: 어떤 경우에도 현재 목표보다 커지지 않는다 (F17).
        return min(reduce_target(current, final_goal), current), REASON_REDUCE_AFTER_SUCCESS
    return current, REASON_MAINTAIN_INSUFFICIENT_SUCCESS
