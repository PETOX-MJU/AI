"""근거 기반 한국어 설명 템플릿 (계획서 7.2, 9절).

경계:
- 숫자는 **코드가 계산해서 문장 슬롯에 넣는다.** 외부 모델이 다시 계산하지 않는다.
- 통계적 유의성, 중독, 불안·우울, 실제 잠든 시각, 의지 부족을 판단하지 않는다.
- 확인 불가를 성공으로 설명하지 않는다.
- ``source``는 항상 ``"template"``이다. 규칙 기반 문장을 생성형 AI 호출 결과로 표시하지 않는다.

외부 AI 제공자가 정해지면 이 모듈의 함수 경계만 유지한 채 어댑터를 덧붙인다.
지금은 사용하지 않는 SDK나 플러그인 구조를 만들지 않는다.
"""

from __future__ import annotations

from .models import MINUTE_MS, Insight, Profile, WeeklyMetrics

DAYS_PER_WEEK = 7
#: 사용 목적은 온보딩의 고정 선택지만 문장에 넣는다. 자유 입력은 신뢰하지 않는 데이터다.
KNOWN_PURPOSES = frozenset({"학습", "업무", "여가", "연락", "기타"})

CODE_DECREASED = "SELECTED_USAGE_DECREASED"
CODE_OTHER_INCREASED = "OTHER_APPS_INCREASED"
CODE_NIGHT_TOP_APP = "NIGHT_TOP_APP"
CODE_DAILY_NIGHT = "DAILY_NIGHT_DIFFERENCE"
CODE_INSUFFICIENT = "INSUFFICIENT_DATA"


def minutes(ms: float) -> int:
    """표시용 분. 내부 계산은 계속 밀리초를 쓴다."""
    return round(ms / MINUTE_MS)


def _decreased(metrics: WeeklyMetrics) -> Insight | None:
    comparison = metrics.comparison
    if not comparison.comparable or comparison.selected_delta_ms is None:
        return None
    if comparison.selected_delta_ms >= 0:
        return None

    dropped = minutes(-comparison.selected_delta_ms)
    daily_mean = metrics.selected_daily_mean_ms
    lead = (
        f"지난주 선택한 앱 사용량은 하루 평균 {minutes(daily_mean)}분입니다. "
        if daily_mean is not None
        else ""
    )
    text = f"{lead}그 전주보다 주간 합계가 {dropped}분 줄었습니다."
    if comparison.selected_delta_pct is not None:
        text += f" 변화율은 {abs(comparison.selected_delta_pct):.1f}%입니다."
    return Insight(
        code=CODE_DECREASED,
        evidence={
            "selected_delta_ms": comparison.selected_delta_ms,
            "selected_delta_pct": comparison.selected_delta_pct,
            "selected_daily_mean_ms": daily_mean,
        },
        text=text,
    )


def _other_apps_increased(metrics: WeeklyMetrics) -> Insight | None:
    """선택 앱이 줄면서 비선택 앱이 늘어난 사실까지만 말한다. 대체 사용의 원인을 확정하지 않는다."""
    comparison = metrics.comparison
    if not comparison.comparable or comparison.selected_delta_ms is None:
        return None
    if comparison.selected_delta_ms >= 0 or comparison.all_apps_delta_ms is None:
        return None

    others_delta = comparison.all_apps_delta_ms - comparison.selected_delta_ms
    if others_delta <= 0:
        return None
    return Insight(
        code=CODE_OTHER_INCREASED,
        evidence={
            "other_apps_delta_ms": others_delta,
            "selected_delta_ms": comparison.selected_delta_ms,
        },
        text=(
            f"선택한 앱은 줄었지만 나머지 앱 사용이 {minutes(others_delta)}분 늘었습니다. "
            "다른 앱 사용이 늘었다는 사실만 확인된 것이며 이유는 기록으로 알 수 없습니다."
        ),
    )


def _night_top_app(metrics: WeeklyMetrics, profile: Profile) -> Insight | None:
    ranked = [
        app
        for app in metrics.per_app
        if app.is_target and app.night_total_ms is not None and app.night_total_ms > 0
    ]
    if not ranked:
        return None
    top = max(ranked, key=lambda a: (a.night_total_ms or 0, a.package_name))

    purpose = profile.purposes.get(top.package_name)
    suffix = f" 이 앱의 사용 목적은 '{purpose}'로 설정되어 있습니다." if purpose in KNOWN_PURPOSES else ""
    share = f" 야간 사용의 {top.night_share_pct:.1f}%입니다." if top.night_share_pct is not None else ""
    return Insight(
        code=CODE_NIGHT_TOP_APP,
        evidence={
            "package_name": top.package_name,
            "night_total_ms": top.night_total_ms,
            "night_share_pct": top.night_share_pct,
        },
        text=(
            f"야간 구간에서 가장 많이 사용한 앱은 {top.package_name}이고 "
            f"{minutes(top.night_total_ms or 0)}분입니다.{share}{suffix}"
        ),
    )


def _daily_vs_night(metrics: WeeklyMetrics) -> Insight | None:
    """판정 가능한 미션이 있을 때만 성과를 나란히 설명한다."""
    if metrics.daily_evaluable_count == 0 and metrics.night_evaluable_count == 0:
        return None

    def phrase(success: int, evaluable: int, unknown_label: str) -> str:
        if evaluable == 0:
            return f"{unknown_label}은 판정 가능한 미션이 없습니다"
        return f"{unknown_label}은 {evaluable}개 중 {success}개 달성"

    text = (
        f"{phrase(metrics.daily_success_count, metrics.daily_evaluable_count, '일일 미션')}, "
        f"{phrase(metrics.night_success_count, metrics.night_evaluable_count, '야간 미션')}입니다."
    )
    return Insight(
        code=CODE_DAILY_NIGHT,
        evidence={
            "daily_success_count": metrics.daily_success_count,
            "daily_evaluable_count": metrics.daily_evaluable_count,
            "night_success_count": metrics.night_success_count,
            "night_evaluable_count": metrics.night_evaluable_count,
        },
        text=text,
    )


def _insufficient(metrics: WeeklyMetrics, has_active_target: bool) -> Insight | None:
    """최초 수집 단계와 기존 사용자의 기록 누락을 구분한다.

    이미 개인화 목표를 쓰고 있는 사용자에게 '임시 목표를 사용합니다'라고 안내하면
    사실과 다르다.
    """
    if metrics.valid_days >= DAYS_PER_WEEK and metrics.valid_nights >= DAYS_PER_WEEK:
        return None

    counts = (
        f"분석에 사용할 수 있는 날은 {metrics.valid_days}일, 야간 구간은 {metrics.valid_nights}개입니다. "
    )
    if has_active_target:
        tail = (
            f"{DAYS_PER_WEEK}개가 모이지 않아 이번 주 성과로는 다음 목표를 계산하지 않습니다. "
            "현재 목표는 그대로 유지됩니다."
        )
    else:
        tail = (
            f"각각 {DAYS_PER_WEEK}개가 모여야 개인 기준선을 계산합니다. "
            "그때까지는 처음 입력한 임시 목표를 사용합니다."
        )
    return Insight(
        code=CODE_INSUFFICIENT,
        evidence={
            "valid_days": metrics.valid_days,
            "valid_nights": metrics.valid_nights,
            "has_active_target": int(has_active_target),
        },
        text=counts + tail,
    )


def render_insights(
    metrics: WeeklyMetrics,
    profile: Profile,
    *,
    current_daily_target_ms: int | None = None,
    current_night_target_ms: int | None = None,
) -> list[Insight]:
    """근거 필드와 문장의 숫자가 항상 일치하도록 만든다.

    ``current_*_target_ms``는 사용자가 이미 수락한 개인화 목표다. 주어지면
    최초 수집 단계가 아니라는 뜻이므로 임시 목표 안내를 하지 않는다.
    """
    has_active_target = current_daily_target_ms is not None or current_night_target_ms is not None
    candidates = [
        _insufficient(metrics, has_active_target),
        _decreased(metrics),
        _other_apps_increased(metrics),
        _night_top_app(metrics, profile),
        _daily_vs_night(metrics),
    ]
    return [insight for insight in candidates if insight is not None]
