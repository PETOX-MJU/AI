"""날짜·야간·주간 경계 계산 (계획서 5절).

하루를 86,400,000ms로 가정하지 않는다. 로컬 시간대에서 경계를 만든 뒤 UTC로 변환해
실제 경과 밀리초를 얻는다. DST 전환일의 하루는 23시간 또는 25시간이다.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from .models import Profile, Window

PRE_BED_LEAD = dt.timedelta(minutes=30)
_UTC = dt.UTC


def zone_of(profile: Profile) -> ZoneInfo:
    return ZoneInfo(profile.timezone)


def to_ms(moment: dt.datetime) -> int:
    """시간대 인식 datetime을 UTC epoch milliseconds로."""
    if moment.tzinfo is None:
        raise ValueError("시간대 없는 datetime은 변환할 수 없습니다")
    return round(moment.timestamp() * 1000)


def localize(naive: dt.datetime, zone: ZoneInfo) -> dt.datetime:
    """벽시계 시각을 그 시간대의 실제 순간으로 해석한다.

    DST 정책 (계획서 5.1):
    - 중복 시각(가을 되돌림)은 **먼저 오는 오프셋**을 쓴다. ``fold=0``이 그 동작이다.
    - 존재하지 않는 시각(봄 건너뜀)은 **전환 후 첫 유효 시각**으로 옮긴다.
    """
    aware = naive.replace(tzinfo=zone, fold=0)
    if aware.astimezone(_UTC).astimezone(zone).replace(tzinfo=None) == naive:
        return aware

    # 존재하지 않는 벽시계 시각이다. 유효해질 때까지 1분씩 전진한다.
    # 알려진 전환 폭은 최대 몇 시간이므로 하루면 충분히 안전하다.
    for step in range(1, 24 * 60 + 1):
        candidate = naive + dt.timedelta(minutes=step)
        aware = candidate.replace(tzinfo=zone, fold=0)
        if aware.astimezone(_UTC).astimezone(zone).replace(tzinfo=None) == candidate:
            return aware
    raise ValueError(f"{naive}를 {zone}에서 해석할 수 없습니다")


def _at(day: dt.date, clock: str, zone: ZoneInfo) -> dt.datetime:
    hour, minute = (int(part) for part in clock.split(":"))
    return localize(dt.datetime(day.year, day.month, day.day, hour, minute), zone)


def daily_window(anchor_date: dt.date, profile: Profile) -> Window:
    """로컬 자정부터 다음 로컬 자정까지. DST일에는 24시간이 아니다."""
    zone = zone_of(profile)
    start = localize(dt.datetime(anchor_date.year, anchor_date.month, anchor_date.day), zone)
    nxt = anchor_date + dt.timedelta(days=1)
    end = localize(dt.datetime(nxt.year, nxt.month, nxt.day), zone)
    return Window(start_ms=to_ms(start), end_ms=to_ms(end))


def bedtime_of(anchor_date: dt.date, profile: Profile) -> dt.datetime:
    """anchor_date 저녁에 시작하는 밤의 취침 시각.

    12:00~23:59 입력은 anchor_date 당일, 00:00~11:59 입력은 다음 날로 해석한다.
    """
    zone = zone_of(profile)
    bed_clock, _ = profile.bed_wake_for(anchor_date)
    bed_hour = int(bed_clock.split(":")[0])
    bed_day = anchor_date if bed_hour >= 12 else anchor_date + dt.timedelta(days=1)
    return _at(bed_day, bed_clock, zone)


def wake_after(bedtime: dt.datetime, anchor_date: dt.date, profile: Profile) -> dt.datetime:
    """취침 시각보다 뒤에 오는 최초의 기상 시각."""
    zone = zone_of(profile)
    _, wake_clock = profile.bed_wake_for(anchor_date)
    day = bedtime.astimezone(zone).date()
    candidate = _at(day, wake_clock, zone)
    if candidate <= bedtime:
        candidate = _at(day + dt.timedelta(days=1), wake_clock, zone)
    return candidate


def night_windows(anchor_date: dt.date, profile: Profile) -> tuple[Window, Window]:
    """``(pre_bed, after_bed)``.

    pre_bed는 ``[취침-30분, 취침)``, after_bed는 ``[취침, 기상)``이다.
    30분은 벽시계가 아니라 실제 경과 시간으로 뺀다.
    """
    bedtime = bedtime_of(anchor_date, profile)
    wake = wake_after(bedtime, anchor_date, profile)
    bed_ms = to_ms(bedtime)
    # 절대 시각에서 뺀다. aware datetime에 timedelta를 더하면 벽시계 연산이라
    # DST 갭에서 시작이 끝보다 뒤로 갈 수 있다.
    return (
        Window(start_ms=bed_ms - round(PRE_BED_LEAD.total_seconds() * 1000), end_ms=bed_ms),
        Window(start_ms=bed_ms, end_ms=to_ms(wake)),
    )


def managed_window(anchor_date: dt.date, profile: Profile) -> Window:
    """``[취침-30분, 기상)`` 전체 관리 구간."""
    pre, post = night_windows(anchor_date, profile)
    return Window(start_ms=pre.start_ms, end_ms=post.end_ms)


def week_dates(week_start: dt.date) -> list[dt.date]:
    """월요일부터 일요일까지 7일."""
    if week_start.weekday() != 0:
        raise ValueError("week_start는 월요일이어야 합니다")
    return [week_start + dt.timedelta(days=offset) for offset in range(7)]


def previous_week_start(week_start: dt.date) -> dt.date:
    return week_start - dt.timedelta(days=7)


def nights_overlap(profile: Profile, dates: list[dt.date]) -> bool:
    """연속한 야간 구간이 겹치면 일정이 잘못된 것이다 (계획서 5.2)."""
    ordered = sorted(dates)
    previous_end: int | None = None
    for day in ordered:
        window = managed_window(day, profile)
        if previous_end is not None and window.start_ms < previous_end:
            return True
        previous_end = window.end_ms
    return False
