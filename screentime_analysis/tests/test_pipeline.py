"""analyze 통합 (계획서 6.3, Task 4)."""

from __future__ import annotations

import datetime as dt

from screentime import AnalysisInput, AnalysisOutput, analyze
from screentime.models import RULES_VERSION

from .conftest import MINUTE, TARGET, WEEK_START, as_of_after, make_aggregate, make_missions


def test_pipeline_has_deterministic_proposals(full_week_request):
    """계획서 Task 4가 지정한 계약 테스트."""
    result = analyze(full_week_request)
    daily = next(p for p in result.proposals if p.kind == "daily")
    assert daily.target_ms == 108 * MINUTE
    assert result == analyze(full_week_request)


def test_output_shape(full_week_request):
    result = analyze(full_week_request)
    assert isinstance(result, AnalysisOutput)
    assert result.schema_version == "1"
    assert result.rules_version == RULES_VERSION
    assert result.week_status == "ready"
    assert result.metrics.valid_days == 7


def test_json_round_trip_is_stable(full_week_request):
    """BE가 dict로 주고받아도 결과가 같아야 한다."""
    payload = full_week_request.model_dump(mode="json")
    again = AnalysisInput.model_validate(payload)
    assert analyze(again).model_dump(mode="json") == analyze(full_week_request).model_dump(mode="json")


def test_missing_data_does_not_invent_success(unavailable_week_request):
    """F04: 확인 불가에서 목표나 성공을 만들어내지 않는다."""
    result = analyze(unavailable_week_request)
    assert result.week_status == "insufficient_data"
    assert all(r.status == "unknown" for r in result.mission_results)
    assert all(r.observed_ms is None for r in result.mission_results)
    assert result.proposals == []  # 기준선이 없으므로 제안하지 않는다
    assert result.metrics.selected_total_ms is None


def test_insight_numbers_match_metrics(full_week_request):
    """설명의 수치는 계산 결과와 일치해야 한다."""
    result = analyze(full_week_request)
    night = next(i for i in result.insights if i.code == "NIGHT_TOP_APP")
    row = next(a for a in result.metrics.per_app if a.package_name == TARGET)
    assert night.evidence["night_total_ms"] == row.night_total_ms
    assert night.evidence["night_share_pct"] == row.night_share_pct


def test_mission_results_cover_every_input_mission(seoul_profile):
    """입력받은 미션만 판정하고 하나도 빠뜨리지 않는다."""
    as_of = as_of_after(WEEK_START, seoul_profile)
    missions = make_missions(WEEK_START, seoul_profile, daily_target_ms=120 * MINUTE, night_target_ms=30 * MINUTE)
    aggregates = []
    for offset in range(7):
        day = WEEK_START + dt.timedelta(days=offset)
        aggregates.append(make_aggregate(day, "daily", seoul_profile, apps={TARGET: 60 * MINUTE}))
        aggregates.append(make_aggregate(day, "pre_bed", seoul_profile, apps={TARGET: 5 * MINUTE}))
        aggregates.append(make_aggregate(day, "after_bed", seoul_profile, apps={TARGET: 5 * MINUTE}))

    request = AnalysisInput(
        as_of_ms=as_of,
        last_collection_attempt_ms=as_of,
        week_start=WEEK_START,
        profile=seoul_profile,
        aggregates=aggregates,
        missions=missions,
        current_daily_target_ms=120 * MINUTE,
        current_night_target_ms=30 * MINUTE,
    )
    result = analyze(request)
    assert len(result.mission_results) == len(missions)
    assert {r.mission_id for r in result.mission_results} == {m.id for m in missions}
    assert all(r.status == "succeeded" for r in result.mission_results)


def test_repeated_sync_does_not_double_count(full_week_request):
    """F10: 같은 범위를 두 번 동기화해도 값이 2배가 되지 않는다.

    같은 집계 키의 중복은 입력 단계에서 거부되므로, BE가 upsert한 뒤 재호출하면
    같은 결과가 나온다.
    """
    first = analyze(full_week_request).model_dump(mode="json")
    second = analyze(full_week_request).model_dump(mode="json")
    assert first == second
    assert first["metrics"]["selected_total_ms"] == 840 * MINUTE


def test_two_week_end_to_end(seoul_profile):
    """합성 2주 데이터로 전체·선택 앱·야간·비교·미션·설명 흐름을 한 번에 확인한다."""
    from .conftest import OTHER, PREV_WEEK_START, week_aggregates

    as_of = as_of_after(WEEK_START, seoul_profile)
    aggregates = week_aggregates(
        PREV_WEEK_START, seoul_profile,
        daily_ms=120 * MINUTE, pre_bed_ms=20 * MINUTE, after_bed_ms=10 * MINUTE,
        other_daily_ms=30 * MINUTE,
    ) + week_aggregates(
        WEEK_START, seoul_profile,
        daily_ms=100 * MINUTE, pre_bed_ms=15 * MINUTE, after_bed_ms=5 * MINUTE,
        other_daily_ms=60 * MINUTE,
    )
    request = AnalysisInput(
        as_of_ms=as_of,
        last_collection_attempt_ms=as_of,
        week_start=WEEK_START,
        profile=seoul_profile,
        aggregates=aggregates,
        missions=make_missions(WEEK_START, seoul_profile, daily_target_ms=110 * MINUTE, night_target_ms=25 * MINUTE),
        current_daily_target_ms=110 * MINUTE,
        current_night_target_ms=25 * MINUTE,
    )
    result = analyze(request)

    assert result.week_status == "ready"
    assert result.metrics.valid_days == 7
    assert result.metrics.selected_daily_mean_ms == 100 * MINUTE
    assert result.metrics.selected_night_mean_ms == 20 * MINUTE

    # 선택 앱은 줄고 비선택 앱은 늘었다.
    assert result.metrics.comparison.comparable is True
    assert result.metrics.comparison.selected_delta_ms == -7 * 20 * MINUTE
    other = next(a for a in result.metrics.per_app if a.package_name == OTHER)
    assert other.delta_ms == 7 * 30 * MINUTE

    # 7개 판정, 7개 성공 -> 감축 제안.
    assert result.metrics.daily_evaluable_count == 7
    assert all(r.status == "succeeded" for r in result.mission_results)
    daily = next(p for p in result.proposals if p.kind == "daily")
    assert daily.target_ms == 99 * MINUTE
    assert daily.reason_code == "REDUCE_AFTER_SUCCESS"

    codes = {i.code for i in result.insights}
    assert "SELECTED_USAGE_DECREASED" in codes
    assert "OTHER_APPS_INCREASED" in codes
    assert "DAILY_NIGHT_DIFFERENCE" in codes
    assert "INSUFFICIENT_DATA" not in codes
