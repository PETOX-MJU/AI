"""목표 제안과 판정 (계획서 8절, F02/F03/F09/F12/F16/F17/F18)."""

from __future__ import annotations

import datetime as dt

from screentime.analytics import analyze_week
from screentime.missions import (
    REASON_INITIAL_BASELINE,
    REASON_LOW_USAGE_NO_TARGET,
    REASON_MAINTAIN_AT_FINAL_GOAL,
    REASON_MAINTAIN_INSUFFICIENT_SUCCESS,
    REASON_REDUCE_AFTER_SUCCESS,
    baseline_ms,
    evaluate_mission,
    propose_targets,
    reduce_target,
)
from screentime.models import AnalysisInput, Mission
from screentime.windows import daily_window, night_windows

from .conftest import (
    MINUTE,
    TARGET,
    WEEK_START,
    as_of_after,
    make_aggregate,
    make_missions,
    week_aggregates,
)


def build(profile, *, aggregates=None, missions=None, daily_target=None, night_target=None, as_of=None):
    resolved_as_of = as_of if as_of is not None else as_of_after(WEEK_START, profile)
    return AnalysisInput(
        as_of_ms=resolved_as_of,
        last_collection_attempt_ms=resolved_as_of,
        week_start=WEEK_START,
        profile=profile,
        aggregates=aggregates if aggregates is not None else [],
        missions=missions if missions is not None else [],
        current_daily_target_ms=daily_target,
        current_night_target_ms=night_target,
    )


def daily_mission(profile, day, target_ms, *, accepted_offset_ms=-MINUTE):
    window = daily_window(day, profile)
    return Mission(
        id=f"d-{day.isoformat()}",
        anchor_date=day,
        kind="daily",
        target_ms=target_ms,
        profile_version=profile.version,
        accepted_at_ms=window.start_ms + accepted_offset_ms,
        window_start_ms=window.start_ms,
        window_end_ms=window.end_ms,
    )


# --- reduce_target --------------------------------------------------------


def test_target_reduction_and_floor():
    """계획서 Task 3이 지정한 계약 테스트."""
    assert reduce_target(120 * MINUTE, 60 * MINUTE) == 108 * MINUTE
    assert reduce_target(65 * MINUTE, 60 * MINUTE) == 60 * MINUTE  # F18
    assert reduce_target(MINUTE, 0) == MINUTE  # 반올림만으로 0이 되지 않는다


def test_reduce_target_never_increases():
    """F17: 사용량이 늘어도 목표를 완화하지 않는다."""
    assert reduce_target(60 * MINUTE, 60 * MINUTE) == 60 * MINUTE
    assert reduce_target(30 * MINUTE, 60 * MINUTE) == 30 * MINUTE  # 이미 최종 목표 이하


def test_reduce_target_floors_to_whole_minutes():
    assert reduce_target(100 * MINUTE, 0) == 90 * MINUTE
    assert reduce_target(7 * MINUTE, 0) == 6 * MINUTE  # 6.3분 -> 내림 6분


# --- evaluate_mission -----------------------------------------------------


def test_exact_target_succeeds(seoul_profile):
    """F02: 목표와 같은 사용량은 성공이다."""
    mission = daily_mission(seoul_profile, WEEK_START, 27 * MINUTE)
    result = evaluate_mission(mission, 27 * MINUTE, "complete", mission.window_end_ms + 1)
    assert result.status == "succeeded"


def test_one_millisecond_over_fails(seoul_profile):
    """F03: 1ms 초과는 실패다."""
    mission = daily_mission(seoul_profile, WEEK_START, 27 * MINUTE)
    result = evaluate_mission(mission, 27 * MINUTE + 1, "complete", mission.window_end_ms + 1)
    assert result.status == "failed"


def test_in_progress_before_window_end(seoul_profile):
    """구간이 끝나기 전에는 초과했어도 in_progress다."""
    mission = daily_mission(seoul_profile, WEEK_START, 27 * MINUTE)
    result = evaluate_mission(mission, 999 * MINUTE, "complete", mission.window_end_ms - 1)
    assert result.status == "in_progress"
    assert result.observed_ms == 999 * MINUTE  # 초과 사실 자체는 전달한다


def test_incomplete_quality_is_unknown_not_zero(seoul_profile):
    """F04: 확인 불가를 0분 성공으로 만들지 않는다."""
    mission = daily_mission(seoul_profile, WEEK_START, 27 * MINUTE)
    after = mission.window_end_ms + 1
    assert evaluate_mission(mission, None, "unavailable", after).status == "unknown"
    assert evaluate_mission(mission, 5 * MINUTE, "partial", after).status == "unknown"


def test_mission_accepted_after_window_start_is_not_applicable(seoul_profile):
    """F12/F16: 구간이 시작한 뒤 수락된 미션은 그 구간의 공식 미션이 아니다."""
    mission = daily_mission(seoul_profile, WEEK_START, 27 * MINUTE, accepted_offset_ms=+MINUTE)
    result = evaluate_mission(mission, 0, "complete", mission.window_end_ms + 1)
    assert result.status == "not_applicable"
    assert result.observed_ms is None


def test_night_requires_both_windows_complete(seoul_profile):
    """야간은 pre_bed와 after_bed가 둘 다 complete일 때만 판정한다."""
    from screentime.missions import observed_for_mission

    day = WEEK_START
    pre, post = night_windows(day, seoul_profile)
    mission = Mission(
        id="n1",
        anchor_date=day,
        kind="night",
        target_ms=30 * MINUTE,
        profile_version=1,
        accepted_at_ms=pre.start_ms - MINUTE,
        window_start_ms=pre.start_ms,
        window_end_ms=post.end_ms,
    )
    request = build(
        seoul_profile,
        aggregates=[
            make_aggregate(day, "pre_bed", seoul_profile, apps={TARGET: 10 * MINUTE}),
            make_aggregate(day, "after_bed", seoul_profile, quality="partial", apps={TARGET: 5 * MINUTE},
                           observed_fraction=0.5),
        ],
        missions=[mission],
    )
    observed, quality = observed_for_mission(request, mission)
    assert quality == "partial"
    assert evaluate_mission(mission, observed, quality, request.as_of_ms).status == "unknown"


# --- 기준선과 제안 --------------------------------------------------------


def test_baseline_needs_seven_records(seoul_profile):
    six_days = [
        make_aggregate(WEEK_START + dt.timedelta(days=i), "daily", seoul_profile, apps={TARGET: 120 * MINUTE})
        for i in range(6)
    ]
    assert baseline_ms(build(seoul_profile, aggregates=six_days), "daily") is None


def test_initial_proposal_from_baseline(full_week_request):
    """F01: 기준선 120분/30분 -> 제안 108분/27분."""
    metrics = analyze_week(full_week_request)
    proposals = propose_targets(full_week_request, metrics)
    daily = next(p for p in proposals if p.kind == "daily")
    night = next(p for p in proposals if p.kind == "night")

    assert daily.target_ms == 108 * MINUTE
    assert daily.reason_code == REASON_INITIAL_BASELINE
    assert night.target_ms == 27 * MINUTE
    assert night.basis_week == WEEK_START


def test_no_proposal_without_baseline(seoul_profile):
    """유효 7개가 없으면 그 유형의 제안을 비워 둔다."""
    request = build(seoul_profile, aggregates=[
        make_aggregate(WEEK_START, "daily", seoul_profile, apps={TARGET: 120 * MINUTE})
    ])
    proposals = propose_targets(request, analyze_week(request))
    assert [p for p in proposals if p.kind == "daily"] == []


def test_initial_proposal_capped_by_temporary_target(seoul_profile):
    """최초 제안은 임시 목표보다 커지지 않는다."""
    aggregates = week_aggregates(
        WEEK_START, seoul_profile, daily_ms=600 * MINUTE, pre_bed_ms=0, after_bed_ms=0
    )
    request = build(seoul_profile, aggregates=aggregates)
    daily = next(p for p in propose_targets(request, analyze_week(request)) if p.kind == "daily")
    assert daily.target_ms == seoul_profile.temporary_daily_ms  # 540분이 아니라 120분


def test_sub_minute_baseline_gives_no_numeric_target(seoul_profile):
    """초 단위 기준선을 분 단위 목표로 강제 변환하지 않는다."""
    aggregates = week_aggregates(WEEK_START, seoul_profile, daily_ms=500, pre_bed_ms=0, after_bed_ms=0)
    request = build(seoul_profile, aggregates=aggregates)
    daily = next(p for p in propose_targets(request, analyze_week(request)) if p.kind == "daily")
    assert daily.target_ms is None
    assert daily.reason_code == REASON_LOW_USAGE_NO_TARGET


def test_reduce_after_successful_week(seoul_profile):
    """판정 가능 7개, 성공 5개 이상이면 감축을 제안한다."""
    aggregates = week_aggregates(
        WEEK_START, seoul_profile, daily_ms=100 * MINUTE, pre_bed_ms=0, after_bed_ms=0
    )
    request = build(
        seoul_profile,
        aggregates=aggregates,
        missions=make_missions(WEEK_START, seoul_profile, daily_target_ms=120 * MINUTE, night_target_ms=30 * MINUTE),
        daily_target=120 * MINUTE,
        night_target=30 * MINUTE,
    )
    metrics = analyze_week(request)
    assert metrics.daily_evaluable_count == 7
    assert metrics.daily_success_count == 7

    daily = next(p for p in propose_targets(request, metrics) if p.kind == "daily")
    assert daily.target_ms == 108 * MINUTE
    assert daily.reason_code == REASON_REDUCE_AFTER_SUCCESS


def test_maintain_when_not_enough_successes(seoul_profile):
    """F09: 판정 가능 7개 미만이면 감축하지 않고 유지한다."""
    aggregates = []
    for offset in range(7):
        day = WEEK_START + dt.timedelta(days=offset)
        quality = "complete" if offset < 2 else "unavailable"
        aggregates.append(make_aggregate(day, "daily", seoul_profile, quality=quality, apps={TARGET: 30 * MINUTE}))
    request = build(
        seoul_profile,
        aggregates=aggregates,
        missions=make_missions(WEEK_START, seoul_profile, daily_target_ms=120 * MINUTE, night_target_ms=30 * MINUTE),
        daily_target=120 * MINUTE,
        night_target=30 * MINUTE,
    )
    daily = next(p for p in propose_targets(request, analyze_week(request)) if p.kind == "daily")
    assert daily.target_ms == 120 * MINUTE
    assert daily.reason_code == REASON_MAINTAIN_INSUFFICIENT_SUCCESS


def test_never_loosens_when_usage_grows(seoul_profile):
    """F17: 현재 목표 60분에서 사용량이 100분으로 늘어도 90분으로 완화하지 않는다."""
    aggregates = week_aggregates(
        WEEK_START, seoul_profile, daily_ms=100 * MINUTE, pre_bed_ms=0, after_bed_ms=0
    )
    request = build(
        seoul_profile,
        aggregates=aggregates,
        missions=make_missions(WEEK_START, seoul_profile, daily_target_ms=60 * MINUTE, night_target_ms=0),
        daily_target=60 * MINUTE,
        night_target=0,
    )
    daily = next(p for p in propose_targets(request, analyze_week(request)) if p.kind == "daily")
    assert daily.target_ms == 60 * MINUTE
    assert daily.reason_code == REASON_MAINTAIN_AT_FINAL_GOAL


def test_daily_and_night_conditions_are_independent(seoul_profile):
    """일일은 성공, 야간은 확인 불가인 주에서 일일만 감축된다."""
    aggregates = []
    for offset in range(7):
        day = WEEK_START + dt.timedelta(days=offset)
        aggregates.append(make_aggregate(day, "daily", seoul_profile, apps={TARGET: 50 * MINUTE}))
        aggregates.append(make_aggregate(day, "pre_bed", seoul_profile, quality="unavailable"))
        aggregates.append(make_aggregate(day, "after_bed", seoul_profile, quality="unavailable"))

    request = build(
        seoul_profile,
        aggregates=aggregates,
        missions=make_missions(WEEK_START, seoul_profile, daily_target_ms=120 * MINUTE, night_target_ms=30 * MINUTE),
        daily_target=120 * MINUTE,
        night_target=30 * MINUTE,
    )
    proposals = {p.kind: p for p in propose_targets(request, analyze_week(request))}
    assert proposals["daily"].reason_code == REASON_REDUCE_AFTER_SUCCESS
    assert proposals["night"].reason_code == REASON_MAINTAIN_INSUFFICIENT_SUCCESS
    assert proposals["night"].target_ms == 30 * MINUTE


def test_at_most_one_proposal_per_kind(full_week_request):
    proposals = propose_targets(full_week_request, analyze_week(full_week_request))
    kinds = [p.kind for p in proposals]
    assert len(kinds) == len(set(kinds))
