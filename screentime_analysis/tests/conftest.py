"""합성 프로필·사용량 fixture.

여기 있는 값은 전부 합성 데이터다. 실제 사용 기록을 테스트에 넣지 않는다.
"""

from __future__ import annotations

import datetime as dt

import pytest

from screentime.models import AnalysisInput, AppDuration, Mission, Profile, WindowAggregate
from screentime.windows import daily_window, night_windows, to_ms

MINUTE = 60_000
TARGET = "com.example.video"
OTHER = "com.example.chat"
MEASUREMENT = "m1"

WEEK_START = dt.date(2026, 9, 7)  # 월요일
PREV_WEEK_START = dt.date(2026, 8, 31)


@pytest.fixture
def seoul_profile() -> Profile:
    """계획서 Task 1이 지정한 기준 프로필."""
    return Profile(
        version=1,
        timezone="Asia/Seoul",
        target_packages=[TARGET],
        purposes={TARGET: "여가"},
        weekday_bed="00:00",
        weekday_wake="07:00",
        weekend_bed="00:00",
        weekend_wake="07:00",
        temporary_daily_ms=120 * MINUTE,
        temporary_night_ms=30 * MINUTE,
        final_daily_ms=60 * MINUTE,
        final_night_ms=0,
        effective_from=dt.date(2026, 9, 7),
    )


def make_aggregate(
    anchor_date: dt.date,
    kind: str,
    profile: Profile,
    *,
    quality: str = "complete",
    apps: dict[str, int] | None = None,
    observed_fraction: float = 1.0,
) -> WindowAggregate:
    """프로필로 계산한 실제 경계 위에 집계를 만든다. 경계를 손으로 쓰지 않는다."""
    if kind == "daily":
        window = daily_window(anchor_date, profile)
    else:
        pre, post = night_windows(anchor_date, profile)
        window = pre if kind == "pre_bed" else post

    if quality == "complete":
        observed_until = window.end_ms
    else:
        span = window.end_ms - window.start_ms
        observed_until = window.start_ms + int(span * observed_fraction)

    payload = None if quality == "unavailable" else [
        AppDuration(package_name=name, duration_ms=ms) for name, ms in (apps or {}).items()
    ]
    return WindowAggregate(
        anchor_date=anchor_date,
        kind=kind,
        start_ms=window.start_ms,
        end_ms=window.end_ms,
        observed_until_ms=observed_until,
        quality=quality,
        reason_codes=[],
        profile_version=profile.version,
        apps=payload,
        measurement_version=MEASUREMENT,
    )


def week_aggregates(
    week_start: dt.date,
    profile: Profile,
    *,
    daily_ms: int,
    pre_bed_ms: int,
    after_bed_ms: int,
    quality: str = "complete",
    other_daily_ms: int = 0,
) -> list[WindowAggregate]:
    """F01 형태의 완전한 한 주. 요일마다 같은 사용량을 넣는다."""
    out: list[WindowAggregate] = []
    for offset in range(7):
        day = week_start + dt.timedelta(days=offset)
        daily_apps: dict[str, int] = {TARGET: daily_ms}
        if other_daily_ms:
            daily_apps[OTHER] = other_daily_ms
        out.append(make_aggregate(day, "daily", profile, quality=quality, apps=daily_apps))
        out.append(make_aggregate(day, "pre_bed", profile, quality=quality, apps={TARGET: pre_bed_ms}))
        out.append(make_aggregate(day, "after_bed", profile, quality=quality, apps={TARGET: after_bed_ms}))
    return out


def as_of_after(week_start: dt.date, profile: Profile) -> int:
    """마지막 야간 구간이 끝난 뒤의 시각."""
    _, post = night_windows(week_start + dt.timedelta(days=6), profile)
    return post.end_ms + 60 * MINUTE


def make_missions(
    week_start: dt.date,
    profile: Profile,
    *,
    daily_target_ms: int,
    night_target_ms: int,
    accept_before: bool = True,
) -> list[Mission]:
    missions: list[Mission] = []
    for offset in range(7):
        day = week_start + dt.timedelta(days=offset)
        daily = daily_window(day, profile)
        pre, post = night_windows(day, profile)
        lead = 60 * MINUTE if accept_before else -60 * MINUTE
        missions.append(
            Mission(
                id=f"d-{day.isoformat()}",
                anchor_date=day,
                kind="daily",
                target_ms=daily_target_ms,
                profile_version=profile.version,
                accepted_at_ms=daily.start_ms - lead,
                window_start_ms=daily.start_ms,
                window_end_ms=daily.end_ms,
            )
        )
        missions.append(
            Mission(
                id=f"n-{day.isoformat()}",
                anchor_date=day,
                kind="night",
                target_ms=night_target_ms,
                profile_version=profile.version,
                accepted_at_ms=pre.start_ms - lead,
                window_start_ms=pre.start_ms,
                window_end_ms=post.end_ms,
            )
        )
    return missions


@pytest.fixture
def full_week_request(seoul_profile: Profile) -> AnalysisInput:
    """F01: 7일 selected 120분, 야간 30분(pre 20 + after 10), 전부 complete."""
    as_of = as_of_after(WEEK_START, seoul_profile)
    return AnalysisInput(
        as_of_ms=as_of,
        last_collection_attempt_ms=as_of,
        week_start=WEEK_START,
        profile=seoul_profile,
        aggregates=week_aggregates(
            WEEK_START, seoul_profile, daily_ms=120 * MINUTE, pre_bed_ms=20 * MINUTE, after_bed_ms=10 * MINUTE
        ),
        missions=[],
        current_daily_target_ms=None,
        current_night_target_ms=None,
    )


@pytest.fixture
def unavailable_week_request(seoul_profile: Profile) -> AnalysisInput:
    """F04: 같은 경계에 모든 집계가 unavailable."""
    as_of = as_of_after(WEEK_START, seoul_profile)
    return AnalysisInput(
        as_of_ms=as_of,
        last_collection_attempt_ms=as_of,
        week_start=WEEK_START,
        profile=seoul_profile,
        aggregates=week_aggregates(
            WEEK_START, seoul_profile, daily_ms=0, pre_bed_ms=0, after_bed_ms=0, quality="unavailable"
        ),
        missions=make_missions(WEEK_START, seoul_profile, daily_target_ms=120 * MINUTE, night_target_ms=30 * MINUTE),
        current_daily_target_ms=None,
        current_night_target_ms=None,
    )


@pytest.fixture
def ny_profile() -> Profile:
    """F21: DST가 있는 시간대."""
    return Profile(
        version=1,
        timezone="America/New_York",
        target_packages=[TARGET],
        purposes={},
        weekday_bed="23:00",
        weekday_wake="07:00",
        weekend_bed="23:00",
        weekend_wake="07:00",
        temporary_daily_ms=120 * MINUTE,
        temporary_night_ms=30 * MINUTE,
        final_daily_ms=60 * MINUTE,
        final_night_ms=0,
        effective_from=dt.date(2026, 3, 2),
    )


__all__ = [
    "MEASUREMENT",
    "MINUTE",
    "OTHER",
    "PREV_WEEK_START",
    "TARGET",
    "WEEK_START",
    "as_of_after",
    "make_aggregate",
    "make_missions",
    "to_ms",
    "week_aggregates",
]
