"""날짜·야간·주간 경계 (계획서 5절, F07/F08/F21)."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from screentime.windows import (
    daily_window,
    managed_window,
    night_windows,
    nights_overlap,
    previous_week_start,
    week_dates,
)

SEOUL = ZoneInfo("Asia/Seoul")
NY = ZoneInfo("America/New_York")
MINUTE = 60_000
HOUR_MS = 3_600_000


def iso(ms: int, zone: ZoneInfo) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, zone).isoformat()


def test_sunday_midnight_belongs_to_sunday(seoul_profile):
    """계획서 Task 1이 지정한 계약 테스트."""
    pre, post = night_windows(dt.date(2026, 9, 13), seoul_profile)
    assert iso(pre.start_ms, SEOUL) == "2026-09-13T23:30:00+09:00"
    assert iso(post.end_ms, SEOUL) == "2026-09-14T07:00:00+09:00"


def test_pre_bed_is_exactly_thirty_minutes(seoul_profile):
    pre, post = night_windows(dt.date(2026, 9, 13), seoul_profile)
    assert pre.duration_ms == 30 * MINUTE
    assert pre.end_ms == post.start_ms  # 경계가 붙어 있고 겹치지 않는다


def test_evening_bedtime_stays_on_anchor_date(seoul_profile):
    """22:00 취침은 anchor_date 당일이다."""
    evening = seoul_profile.model_copy(update={"weekday_bed": "22:00", "weekend_bed": "22:00"})
    pre, post = night_windows(dt.date(2026, 9, 13), evening)
    assert iso(pre.start_ms, SEOUL) == "2026-09-13T21:30:00+09:00"
    assert iso(post.start_ms, SEOUL) == "2026-09-13T22:00:00+09:00"
    assert iso(post.end_ms, SEOUL) == "2026-09-14T07:00:00+09:00"


def test_weekend_schedule_uses_weekend_times(seoul_profile):
    """토·일 저녁은 주말 일정을 쓴다."""
    profile = seoul_profile.model_copy(update={"weekend_bed": "01:00", "weekend_wake": "09:00"})
    saturday = dt.date(2026, 9, 12)
    friday = dt.date(2026, 9, 11)
    assert iso(night_windows(saturday, profile)[1].start_ms, SEOUL) == "2026-09-13T01:00:00+09:00"
    assert iso(night_windows(friday, profile)[1].start_ms, SEOUL) == "2026-09-12T00:00:00+09:00"


def test_daily_window_is_local_midnight_to_midnight(seoul_profile):
    window = daily_window(dt.date(2026, 9, 13), seoul_profile)
    assert iso(window.start_ms, SEOUL) == "2026-09-13T00:00:00+09:00"
    assert iso(window.end_ms, SEOUL) == "2026-09-14T00:00:00+09:00"
    assert window.duration_ms == 24 * HOUR_MS  # 서울은 DST가 없다


def test_managed_window_spans_pre_bed_to_wake(seoul_profile):
    window = managed_window(dt.date(2026, 9, 13), seoul_profile)
    pre, post = night_windows(dt.date(2026, 9, 13), seoul_profile)
    assert window.start_ms == pre.start_ms
    assert window.end_ms == post.end_ms


# --- F21: DST -------------------------------------------------------------


def test_dst_spring_forward_day_is_23_hours(ny_profile):
    """봄 전환일은 23시간이다. 86,400,000ms 상수로 계산하면 안 된다."""
    short = [
        day
        for day in (dt.date(2026, 3, offset) for offset in range(1, 32))
        if daily_window(day, ny_profile).duration_ms == 23 * HOUR_MS
    ]
    assert len(short) == 1, f"3월에 23시간인 날이 정확히 하나여야 합니다: {short}"


def test_dst_fall_back_day_is_25_hours(ny_profile):
    long_days = [
        day
        for day in (dt.date(2026, 11, offset) for offset in range(1, 31))
        if daily_window(day, ny_profile).duration_ms == 25 * HOUR_MS
    ]
    assert len(long_days) == 1, f"11월에 25시간인 날이 정확히 하나여야 합니다: {long_days}"


def test_nonexistent_local_time_moves_to_first_valid_moment(ny_profile):
    """봄 전환에서 02:30은 존재하지 않는다. 전환 후 첫 유효 시각으로 옮긴다."""
    profile = ny_profile.model_copy(update={"weekday_bed": "02:30", "weekend_bed": "02:30"})
    spring = next(
        day
        for day in (dt.date(2026, 3, offset) for offset in range(1, 32))
        if daily_window(day, profile).duration_ms == 23 * HOUR_MS
    )
    anchor = spring - dt.timedelta(days=1)  # 취침이 다음 날(전환일) 02:30
    _, post = night_windows(anchor, profile)
    local = dt.datetime.fromtimestamp(post.start_ms / 1000, NY)
    assert local.date() == spring
    assert (local.hour, local.minute) == (3, 0)  # 02:00 -> 03:00 으로 건너뛴 직후


def test_ambiguous_local_time_uses_earlier_offset(ny_profile):
    """가을 전환의 중복 시각은 먼저 오는 오프셋(EDT)을 쓴다."""
    profile = ny_profile.model_copy(update={"weekday_bed": "01:30", "weekend_bed": "01:30"})
    fall = next(
        day
        for day in (dt.date(2026, 11, offset) for offset in range(1, 31))
        if daily_window(day, profile).duration_ms == 25 * HOUR_MS
    )
    anchor = fall - dt.timedelta(days=1)
    _, post = night_windows(anchor, profile)
    local = dt.datetime.fromtimestamp(post.start_ms / 1000, NY)
    assert (local.hour, local.minute) == (1, 30)
    assert local.utcoffset() == dt.timedelta(hours=-4)  # EDT, 되돌리기 전


# --- 주간 경계 ------------------------------------------------------------


def test_week_dates_are_monday_to_sunday():
    days = week_dates(dt.date(2026, 9, 7))
    assert len(days) == 7
    assert days[0] == dt.date(2026, 9, 7)
    assert days[-1] == dt.date(2026, 9, 13)
    assert days[-1].weekday() == 6


def test_week_dates_rejects_non_monday():
    with pytest.raises(ValueError, match="월요일"):
        week_dates(dt.date(2026, 9, 8))


def test_previous_week_start():
    assert previous_week_start(dt.date(2026, 9, 7)) == dt.date(2026, 8, 31)


def test_overlapping_nights_detected(seoul_profile):
    """기상이 다음 밤의 pre_bed 안으로 들어가면 겹친다."""
    fine = seoul_profile
    assert not nights_overlap(fine, week_dates(dt.date(2026, 9, 7)))

    clashing = seoul_profile.model_copy(
        update={"weekday_wake": "23:45", "weekend_wake": "23:45"}
    )
    assert nights_overlap(clashing, week_dates(dt.date(2026, 9, 7)))
