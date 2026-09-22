"""Generate synthetic dashboard data through the real analysis pipeline."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from screentime import AnalysisInput, analyze
from screentime.models import AppDuration, Profile, WindowAggregate
from screentime.windows import daily_window, night_windows

MINUTE_MS = 60_000
WEEK_START = dt.date(2026, 9, 14)
PREVIOUS_WEEK_START = WEEK_START - dt.timedelta(days=7)
PACKAGES = (
    "com.google.android.youtube",
    "com.instagram.android",
    "com.zhiliaoapp.musically",
)

PREVIOUS_MINUTES = (
    (80, 45, 20),
    (75, 55, 25),
    (95, 50, 18),
    (85, 60, 22),
    (90, 48, 30),
    (100, 65, 26),
    (90, 55, 24),
)
CURRENT_MINUTES = (
    (70, 42, 25),
    (68, 50, 28),
    (82, 47, 22),
    (76, 52, 26),
    (72, 44, 32),
    (88, 58, 30),
    (74, 49, 29),
)


def _apps(minutes: tuple[int, int, int]) -> list[AppDuration]:
    return [
        AppDuration(package_name=package, duration_ms=value * MINUTE_MS)
        for package, value in zip(PACKAGES, minutes, strict=True)
    ]


def _aggregate(
    day: dt.date,
    kind: str,
    profile: Profile,
    minutes: tuple[int, int, int],
) -> WindowAggregate:
    if kind == "daily":
        window = daily_window(day, profile)
    else:
        pre_bed, after_bed = night_windows(day, profile)
        window = pre_bed if kind == "pre_bed" else after_bed
    return WindowAggregate(
        anchor_date=day,
        kind=kind,
        start_ms=window.start_ms,
        end_ms=window.end_ms,
        observed_until_ms=window.end_ms,
        quality="complete",
        profile_version=profile.version,
        apps=_apps(minutes),
        measurement_version="preview-v1",
    )


def build_preview() -> AnalysisInput:
    profile = Profile(
        version=1,
        timezone="Asia/Seoul",
        target_packages=list(PACKAGES),
        purposes={package: "줄이고 싶은 앱" for package in PACKAGES},
        weekday_bed="00:00",
        weekday_wake="07:00",
        weekend_bed="01:00",
        weekend_wake="08:00",
        temporary_daily_ms=180 * MINUTE_MS,
        temporary_night_ms=45 * MINUTE_MS,
        final_daily_ms=120 * MINUTE_MS,
        final_night_ms=20 * MINUTE_MS,
        effective_from=PREVIOUS_WEEK_START,
    )

    aggregates: list[WindowAggregate] = []
    for week_start, rows in (
        (PREVIOUS_WEEK_START, PREVIOUS_MINUTES),
        (WEEK_START, CURRENT_MINUTES),
    ):
        for offset, daily_minutes in enumerate(rows):
            day = week_start + dt.timedelta(days=offset)
            aggregates.extend(
                (
                    _aggregate(day, "daily", profile, daily_minutes),
                    _aggregate(day, "pre_bed", profile, (8, 5, 3)),
                    _aggregate(day, "after_bed", profile, (5, 3, 2)),
                )
            )

    _, final_window = night_windows(WEEK_START + dt.timedelta(days=6), profile)
    as_of_ms = final_window.end_ms + MINUTE_MS
    return AnalysisInput(
        as_of_ms=as_of_ms,
        last_collection_attempt_ms=as_of_ms,
        week_start=WEEK_START,
        profile=profile,
        aggregates=aggregates,
        missions=[],
        current_daily_target_ms=180 * MINUTE_MS,
        current_night_target_ms=45 * MINUTE_MS,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    # DashboardUiState(dashboard-api-spec.md 3.4)의 analysis 자리에 들어가는 값
    result = {"analysis": analyze(build_preview()).model_dump(mode="json")}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
