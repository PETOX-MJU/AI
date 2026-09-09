"""주간 분석 (계획서 7.1, F01/F04/F05/F06/F08/F09/F11)."""

from __future__ import annotations

import datetime as dt

from screentime.analytics import analyze_week, get_week_status, week_totals
from screentime.models import AnalysisInput

from .conftest import (
    MINUTE,
    OTHER,
    PREV_WEEK_START,
    TARGET,
    WEEK_START,
    as_of_after,
    make_aggregate,
    make_missions,
    week_aggregates,
)


def test_complete_week_average(full_week_request):
    """계획서 Task 2가 지정한 계약 테스트."""
    result = analyze_week(full_week_request)
    assert result.valid_days == 7
    assert result.selected_total_ms == 840 * MINUTE
    assert result.selected_daily_mean_ms == 120 * MINUTE


def test_unknown_is_not_zero(unavailable_week_request):
    """F04: 데이터가 없다는 이유로 0이나 성공을 만들지 않는다."""
    result = analyze_week(unavailable_week_request)
    assert result.valid_days == 0
    assert result.selected_daily_mean_ms is None
    assert result.selected_total_ms is None
    assert result.all_apps_total_ms is None
    # 판정 가능한 미션이 없으므로 성공률 분모는 0이다.
    assert result.daily_evaluable_count == 0
    assert result.daily_success_count == 0


def test_night_totals_and_mean(full_week_request):
    result = analyze_week(full_week_request)
    assert result.valid_nights == 7
    assert result.pre_bed_total_ms == 7 * 20 * MINUTE
    assert result.after_bed_total_ms == 7 * 10 * MINUTE
    assert result.selected_night_mean_ms == 30 * MINUTE


def test_partial_day_is_excluded_from_totals_but_shown_per_day(seoul_profile):
    """F05 인접 규칙: partial의 확인된 값은 per_day에만 나온다."""
    aggregates = week_aggregates(
        WEEK_START, seoul_profile, daily_ms=120 * MINUTE, pre_bed_ms=20 * MINUTE, after_bed_ms=10 * MINUTE
    )
    sunday = WEEK_START + dt.timedelta(days=6)
    aggregates = [a for a in aggregates if not (a.anchor_date == sunday and a.kind == "daily")]
    aggregates.append(
        make_aggregate(sunday, "daily", seoul_profile, quality="partial", apps={TARGET: 45 * MINUTE},
                       observed_fraction=0.5)
    )
    as_of = as_of_after(WEEK_START, seoul_profile)
    request = AnalysisInput(
        as_of_ms=as_of,
        last_collection_attempt_ms=as_of,
        week_start=WEEK_START,
        profile=seoul_profile,
        aggregates=aggregates,
        missions=[],
        current_daily_target_ms=None,
        current_night_target_ms=None,
    )
    result = analyze_week(request)

    assert result.valid_days == 6
    assert result.selected_total_ms == 6 * 120 * MINUTE  # partial 45분은 섞이지 않는다
    assert result.selected_daily_mean_ms is None  # 7개가 아니면 평균을 내지 않는다

    row = next(d for d in result.per_day if d.date == sunday)
    assert row.daily_quality == "partial"
    assert row.selected_ms == 45 * MINUTE  # 확인된 값은 보여준다


def test_confirmed_zero_is_not_missing(seoul_profile):
    """F05: complete + 빈 배열은 '확인된 0'이며 유효 일수에 포함된다."""
    aggregates = week_aggregates(
        WEEK_START, seoul_profile, daily_ms=0, pre_bed_ms=0, after_bed_ms=0
    )
    as_of = as_of_after(WEEK_START, seoul_profile)
    request = AnalysisInput(
        as_of_ms=as_of,
        last_collection_attempt_ms=as_of,
        week_start=WEEK_START,
        profile=seoul_profile,
        aggregates=aggregates,
        missions=[],
        current_daily_target_ms=None,
        current_night_target_ms=None,
    )
    result = analyze_week(request)
    assert result.valid_days == 7
    assert result.selected_total_ms == 0
    assert result.selected_daily_mean_ms == 0


# --- 비교 (F06/F11) -------------------------------------------------------


def two_week_request(profile, *, prev_daily_ms: int, this_daily_ms: int, other_prev=0, other_this=0):
    as_of = as_of_after(WEEK_START, profile)
    aggregates = week_aggregates(
        PREV_WEEK_START, profile, daily_ms=prev_daily_ms, pre_bed_ms=0, after_bed_ms=0,
        other_daily_ms=other_prev,
    ) + week_aggregates(
        WEEK_START, profile, daily_ms=this_daily_ms, pre_bed_ms=0, after_bed_ms=0,
        other_daily_ms=other_this,
    )
    return AnalysisInput(
        as_of_ms=as_of,
        last_collection_attempt_ms=as_of,
        week_start=WEEK_START,
        profile=profile,
        aggregates=aggregates,
        missions=[],
        current_daily_target_ms=None,
        current_night_target_ms=None,
    )


def test_zero_denominator_gives_null_percentage(seoul_profile):
    """F06: 지난주 0분 -> 이번 주 20분이면 증감률은 null, 절대 증가만 표시."""
    request = two_week_request(seoul_profile, prev_daily_ms=0, this_daily_ms=20 * MINUTE)
    comparison = analyze_week(request).comparison
    assert comparison.comparable is True
    assert comparison.selected_delta_ms == 7 * 20 * MINUTE
    assert comparison.selected_delta_pct is None


def test_decrease_is_reported(seoul_profile):
    request = two_week_request(seoul_profile, prev_daily_ms=120 * MINUTE, this_daily_ms=108 * MINUTE)
    comparison = analyze_week(request).comparison
    assert comparison.selected_delta_ms == -7 * 12 * MINUTE
    assert comparison.selected_delta_pct == -10.0


def test_incomplete_week_is_not_comparable(seoul_profile, full_week_request):
    """F11: 완전한 두 주가 아니면 정식 증감률을 만들지 않는다."""
    comparison = analyze_week(full_week_request).comparison
    assert comparison.comparable is False
    assert comparison.reason == "NO_PREVIOUS_WEEK_DATA"
    assert comparison.selected_delta_pct is None


def test_share_and_night_share(seoul_profile):
    request = two_week_request(
        seoul_profile, prev_daily_ms=60 * MINUTE, this_daily_ms=60 * MINUTE,
        other_prev=60 * MINUTE, other_this=140 * MINUTE,
    )
    metrics = analyze_week(request)
    target_row = next(a for a in metrics.per_app if a.package_name == TARGET)
    other_row = next(a for a in metrics.per_app if a.package_name == OTHER)

    assert target_row.is_target is True
    assert other_row.is_target is False
    assert target_row.share_pct == 30.0  # 420 / 1400
    assert other_row.share_pct == 70.0
    # 비선택 앱의 야간 비중은 항상 null이다.
    assert other_row.night_share_pct is None
    assert other_row.delta_ms == 7 * 80 * MINUTE


# --- 주간 상태 (F08) ------------------------------------------------------


def test_status_ready(full_week_request):
    assert get_week_status(full_week_request) == "ready"


def test_status_in_progress_before_last_night_ends(seoul_profile):
    """F08: 월요일 00:01 요청, 일요일 야간 종료는 07:00 -> in_progress."""
    from screentime.windows import night_windows

    _, post = night_windows(WEEK_START + dt.timedelta(days=6), seoul_profile)
    request = AnalysisInput(
        as_of_ms=post.end_ms - 60 * MINUTE,
        last_collection_attempt_ms=post.end_ms - 60 * MINUTE,
        week_start=WEEK_START,
        profile=seoul_profile,
        aggregates=[],
        missions=[],
        current_daily_target_ms=None,
        current_night_target_ms=None,
    )
    assert get_week_status(request) == "in_progress"


def test_status_awaiting_data_when_no_collection_after_close(seoul_profile):
    """F08: 구간은 끝났으나 그 뒤 수집 시도가 없으면 awaiting_data."""
    from screentime.windows import night_windows

    _, post = night_windows(WEEK_START + dt.timedelta(days=6), seoul_profile)
    request = AnalysisInput(
        as_of_ms=post.end_ms + MINUTE,
        last_collection_attempt_ms=post.end_ms - MINUTE,
        week_start=WEEK_START,
        profile=seoul_profile,
        aggregates=[],
        missions=[],
        current_daily_target_ms=None,
        current_night_target_ms=None,
    )
    assert get_week_status(request) == "awaiting_data"


def test_status_insufficient_data(unavailable_week_request):
    assert get_week_status(unavailable_week_request) == "insufficient_data"


# --- 미션 집계 (F09) ------------------------------------------------------


def test_success_counts_exclude_unknown(seoul_profile):
    """F09: 성공 2, 실패 0, unknown 5 -> 분모는 2이며 감축 조건은 미충족."""
    complete_days = [WEEK_START, WEEK_START + dt.timedelta(days=1)]
    aggregates = []
    for offset in range(7):
        day = WEEK_START + dt.timedelta(days=offset)
        quality = "complete" if day in complete_days else "unavailable"
        aggregates.append(make_aggregate(day, "daily", seoul_profile, quality=quality, apps={TARGET: 30 * MINUTE}))
        aggregates.append(make_aggregate(day, "pre_bed", seoul_profile, quality=quality, apps={TARGET: 0}))
        aggregates.append(make_aggregate(day, "after_bed", seoul_profile, quality=quality, apps={TARGET: 0}))

    as_of = as_of_after(WEEK_START, seoul_profile)
    request = AnalysisInput(
        as_of_ms=as_of,
        last_collection_attempt_ms=as_of,
        week_start=WEEK_START,
        profile=seoul_profile,
        aggregates=aggregates,
        missions=make_missions(WEEK_START, seoul_profile, daily_target_ms=60 * MINUTE, night_target_ms=30 * MINUTE),
        current_daily_target_ms=60 * MINUTE,
        current_night_target_ms=30 * MINUTE,
    )
    metrics = analyze_week(request)
    assert metrics.daily_success_count == 2
    assert metrics.daily_evaluable_count == 2  # unknown 5개는 분모에서 빠진다


def test_week_totals_helper_is_reusable(full_week_request):
    totals = week_totals(full_week_request, WEEK_START)
    assert totals.is_full is True
    assert totals.per_app_day_ms[TARGET] == 840 * MINUTE
