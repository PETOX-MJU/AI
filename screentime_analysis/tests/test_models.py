"""입력 검증 (계획서 6.2, F19).

잘못된 입력은 빈 성공 결과로 치환하지 않고 ValidationError를 낸다.
"""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from screentime.models import AnalysisInput, AppDuration, Mission, Profile, WindowAggregate
from screentime.windows import daily_window, night_windows

from .conftest import (
    MEASUREMENT,
    MINUTE,
    TARGET,
    WEEK_START,
    as_of_after,
    make_aggregate,
    week_aggregates,
)


def build_request(profile: Profile, **overrides) -> AnalysisInput:
    as_of = as_of_after(WEEK_START, profile)
    payload = {
        "as_of_ms": as_of,
        "last_collection_attempt_ms": as_of,
        "week_start": WEEK_START,
        "profile": profile,
        "aggregates": week_aggregates(
            WEEK_START, profile, daily_ms=120 * MINUTE, pre_bed_ms=20 * MINUTE, after_bed_ms=10 * MINUTE
        ),
        "missions": [],
        "current_daily_target_ms": None,
        "current_night_target_ms": None,
    }
    payload.update(overrides)
    return AnalysisInput(**payload)


# --- 스칼라 검증 ----------------------------------------------------------


def test_negative_duration_rejected():
    with pytest.raises(ValidationError):
        AppDuration(package_name=TARGET, duration_ms=-1)


def test_bool_is_not_a_valid_integer():
    """bool은 int의 하위 타입이라 명시적으로 막지 않으면 통과한다."""
    with pytest.raises(ValidationError, match="bool"):
        AppDuration(package_name=TARGET, duration_ms=True)


def test_timestamp_out_of_range_rejected(seoul_profile):
    with pytest.raises(ValidationError):
        build_request(seoul_profile, as_of_ms=1)  # 초 단위를 밀리초로 잘못 보낸 경우


def test_extra_field_rejected(seoul_profile):
    with pytest.raises(ValidationError):
        build_request(seoul_profile, typo_field=1)


# --- Profile --------------------------------------------------------------


def test_unknown_timezone_rejected(seoul_profile):
    with pytest.raises(ValidationError, match="시간대"):
        seoul_profile.model_copy(update={"timezone": "Mars/Olympus"}).model_validate(
            seoul_profile.model_dump() | {"timezone": "Mars/Olympus"}
        )


def test_duplicate_target_packages_rejected(seoul_profile):
    with pytest.raises(ValidationError, match="중복"):
        Profile.model_validate(seoul_profile.model_dump() | {"target_packages": [TARGET, TARGET]})


def test_empty_target_packages_rejected(seoul_profile):
    with pytest.raises(ValidationError):
        Profile.model_validate(seoul_profile.model_dump() | {"target_packages": []})


def test_temporary_target_below_final_rejected(seoul_profile):
    with pytest.raises(ValidationError, match="final_daily_ms 이상"):
        Profile.model_validate(seoul_profile.model_dump() | {"temporary_daily_ms": 30 * MINUTE})


def test_sub_minute_target_rejected(seoul_profile):
    with pytest.raises(ValidationError, match="분 단위"):
        Profile.model_validate(seoul_profile.model_dump() | {"final_daily_ms": 1500})


def test_bad_clock_format_rejected(seoul_profile):
    with pytest.raises(ValidationError):
        Profile.model_validate(seoul_profile.model_dump() | {"weekday_bed": "24:00"})


# --- WindowAggregate ------------------------------------------------------


def test_duplicate_package_in_one_window_rejected(seoul_profile):
    window = daily_window(WEEK_START, seoul_profile)
    with pytest.raises(ValidationError, match="package_name 중복"):
        WindowAggregate(
            anchor_date=WEEK_START,
            kind="daily",
            start_ms=window.start_ms,
            end_ms=window.end_ms,
            observed_until_ms=window.end_ms,
            quality="complete",
            profile_version=1,
            apps=[AppDuration(package_name=TARGET, duration_ms=1), AppDuration(package_name=TARGET, duration_ms=2)],
            measurement_version=MEASUREMENT,
        )


def test_app_duration_cannot_exceed_window(seoul_profile):
    pre, _ = night_windows(WEEK_START, seoul_profile)
    with pytest.raises(ValidationError, match="구간 길이를 초과"):
        WindowAggregate(
            anchor_date=WEEK_START,
            kind="pre_bed",
            start_ms=pre.start_ms,
            end_ms=pre.end_ms,
            observed_until_ms=pre.end_ms,
            quality="complete",
            profile_version=1,
            apps=[AppDuration(package_name=TARGET, duration_ms=31 * MINUTE)],  # 구간은 30분
            measurement_version=MEASUREMENT,
        )


def test_unavailable_must_have_null_apps(seoul_profile):
    window = daily_window(WEEK_START, seoul_profile)
    base = {
        "anchor_date": WEEK_START,
        "kind": "daily",
        "start_ms": window.start_ms,
        "end_ms": window.end_ms,
        "observed_until_ms": window.start_ms,
        "profile_version": 1,
        "measurement_version": MEASUREMENT,
    }
    with pytest.raises(ValidationError, match="null이어야"):
        WindowAggregate(**base, quality="unavailable", apps=[])
    with pytest.raises(ValidationError, match="배열이어야"):
        WindowAggregate(**base, quality="partial", apps=None)


def test_complete_requires_observed_until_equals_end(seoul_profile):
    window = daily_window(WEEK_START, seoul_profile)
    with pytest.raises(ValidationError, match="observed_until_ms == end_ms"):
        WindowAggregate(
            anchor_date=WEEK_START,
            kind="daily",
            start_ms=window.start_ms,
            end_ms=window.end_ms,
            observed_until_ms=window.end_ms - 1,
            quality="complete",
            profile_version=1,
            apps=[],
            measurement_version=MEASUREMENT,
        )


def test_complete_with_empty_apps_is_confirmed_zero(seoul_profile):
    """F05: 빈 배열은 '확인된 0'이며 유효한 입력이다."""
    agg = make_aggregate(WEEK_START, "daily", seoul_profile, apps={})
    assert agg.apps == []
    assert agg.total_ms({TARGET}) == 0


def test_unavailable_total_is_none(seoul_profile):
    agg = make_aggregate(WEEK_START, "daily", seoul_profile, quality="unavailable")
    assert agg.total_ms({TARGET}) is None


# --- AnalysisInput 교차 검증 ----------------------------------------------


def test_week_start_must_be_monday(seoul_profile):
    with pytest.raises(ValidationError, match="월요일"):
        build_request(seoul_profile, week_start=dt.date(2026, 9, 8))


def test_in_progress_window_cannot_be_complete(seoul_profile):
    """F19: 아직 끝나지 않은 구간의 complete는 거부한다."""
    aggregates = week_aggregates(
        WEEK_START, seoul_profile, daily_ms=120 * MINUTE, pre_bed_ms=20 * MINUTE, after_bed_ms=10 * MINUTE
    )
    early = min(a.end_ms for a in aggregates)
    with pytest.raises(ValidationError, match="끝나지 않은"):
        build_request(seoul_profile, aggregates=aggregates, as_of_ms=early - 1)


def test_duplicate_aggregate_key_rejected(seoul_profile):
    aggregates = week_aggregates(
        WEEK_START, seoul_profile, daily_ms=120 * MINUTE, pre_bed_ms=20 * MINUTE, after_bed_ms=10 * MINUTE
    )
    with pytest.raises(ValidationError, match="중복"):
        build_request(seoul_profile, aggregates=[*aggregates, aggregates[0]])


def test_profile_version_mismatch_rejected(seoul_profile):
    aggregates = week_aggregates(
        WEEK_START, seoul_profile, daily_ms=120 * MINUTE, pre_bed_ms=20 * MINUTE, after_bed_ms=10 * MINUTE
    )
    stale = aggregates[0].model_copy(update={"profile_version": 2})
    with pytest.raises(ValidationError, match="profile_version"):
        build_request(seoul_profile, aggregates=[stale, *aggregates[1:]])


def test_mixed_measurement_versions_rejected(seoul_profile):
    aggregates = week_aggregates(
        WEEK_START, seoul_profile, daily_ms=120 * MINUTE, pre_bed_ms=20 * MINUTE, after_bed_ms=10 * MINUTE
    )
    other = aggregates[0].model_copy(update={"measurement_version": "m2"})
    with pytest.raises(ValidationError, match="measurement_version"):
        build_request(seoul_profile, aggregates=[other, *aggregates[1:]])


def test_duplicate_mission_id_rejected(seoul_profile):
    window = daily_window(WEEK_START, seoul_profile)
    mission = Mission(
        id="m1",
        anchor_date=WEEK_START,
        kind="daily",
        target_ms=120 * MINUTE,
        profile_version=1,
        accepted_at_ms=window.start_ms - MINUTE,
        window_start_ms=window.start_ms,
        window_end_ms=window.end_ms,
    )
    with pytest.raises(ValidationError, match="mission.id 중복"):
        build_request(seoul_profile, missions=[mission, mission])


def test_duplicate_anchor_kind_mission_rejected(seoul_profile):
    window = daily_window(WEEK_START, seoul_profile)
    base = {
        "anchor_date": WEEK_START,
        "kind": "daily",
        "target_ms": 120 * MINUTE,
        "profile_version": 1,
        "accepted_at_ms": window.start_ms - MINUTE,
        "window_start_ms": window.start_ms,
        "window_end_ms": window.end_ms,
    }
    with pytest.raises(ValidationError, match="anchor_date, kind"):
        build_request(seoul_profile, missions=[Mission(id="a", **base), Mission(id="b", **base)])


def test_too_many_anchor_dates_rejected(seoul_profile):
    aggregates = []
    for week in range(4):  # 4주 = 28 anchor dates > 21
        start = WEEK_START - dt.timedelta(days=7 * week)
        aggregates += [make_aggregate(start + dt.timedelta(days=i), "daily", seoul_profile, apps={}) for i in range(7)]
    with pytest.raises(ValidationError, match="anchor date"):
        build_request(seoul_profile, aggregates=aggregates)
