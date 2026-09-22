package com.petox.screentime

import java.time.Duration
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime

/**
 * 날짜·야간·주간 경계 계산 (Python `screentime/windows.py` 이식).
 *
 * 하루를 86,400,000ms로 가정하지 않는다. 로컬 시간대에서 경계를 만든 뒤 UTC로 변환해
 * 실제 경과 밀리초를 얻는다. DST 전환일의 하루는 23시간 또는 25시간이다.
 *
 * 이 파일 안에서 `LocalDate.now()` / `System.currentTimeMillis()` 를 호출하지 않는다.
 * 무상태 계약이다 — 시각은 전부 파라미터로 들어온다.
 */

val PRE_BED_LEAD: Duration = Duration.ofMinutes(30)

fun zoneOf(profile: Profile): ZoneId = ZoneId.of(profile.timezone)

/** 시간대 인식 시각을 UTC epoch milliseconds로. */
fun toMs(moment: ZonedDateTime): Long = moment.toInstant().toEpochMilli()

/**
 * 벽시계 시각을 그 시간대의 실제 순간으로 해석한다.
 *
 * DST 정책:
 * - 중복 시각(가을 되돌림)은 **먼저 오는 오프셋**을 쓴다. Python `fold=0` 에 해당한다.
 * - 존재하지 않는 시각(봄 건너뜀)은 **전환 후 첫 유효 시각**으로 옮긴다.
 *
 * `ZonedDateTime.of()` 의 기본 동작을 쓰면 안 된다. 겹침은 먼저 오는 오프셋이라 같지만,
 * 갭에서는 java.time 이 벽시계를 갭 길이만큼 밀어버린다(02:30 → 03:30). Python 은
 * 1분씩 전진해 첫 유효 벽시계(03:00)를 찾으므로 결과 instant 가 30분 어긋난다.
 * 그래서 전환 규칙을 직접 본다.
 */
fun localize(naive: LocalDateTime, zone: ZoneId): ZonedDateTime {
    val rules = zone.rules
    val offsets = rules.getValidOffsets(naive)
    if (offsets.isNotEmpty()) {
        // 겹침이면 [먼저 오는 오프셋, 나중 오프셋] 순이다. 첫 번째가 fold=0 이다.
        return ZonedDateTime.ofInstant(naive.toInstant(offsets[0]), zone)
    }
    // 갭이다. 전환 순간이 곧 '전환 후 첫 유효 시각'이다.
    val transition = rules.getTransition(naive)
        ?: throw IllegalStateException("${naive}를 ${zone}에서 해석할 수 없습니다")
    return ZonedDateTime.ofInstant(transition.instant, zone)
}

private fun at(day: LocalDate, clock: String, zone: ZoneId): ZonedDateTime {
    val parts = clock.split(":")
    val hour = parts[0].toInt()
    val minute = parts[1].toInt()
    return localize(LocalDateTime.of(day, LocalTime.of(hour, minute)), zone)
}

/** 로컬 자정부터 다음 로컬 자정까지. DST일에는 24시간이 아니다. */
fun dailyWindow(anchorDate: LocalDate, profile: Profile): Window {
    val zone = zoneOf(profile)
    val start = localize(anchorDate.atStartOfDay(), zone)
    val end = localize(anchorDate.plusDays(1).atStartOfDay(), zone)
    return Window(startMs = toMs(start), endMs = toMs(end))
}

/**
 * anchorDate 저녁에 시작하는 밤의 취침 시각.
 *
 * 12:00~23:59 입력은 anchorDate 당일, 00:00~11:59 입력은 다음 날로 해석한다.
 */
fun bedtimeOf(anchorDate: LocalDate, profile: Profile): ZonedDateTime {
    val zone = zoneOf(profile)
    val (bedClock, _) = profile.bedWakeFor(anchorDate)
    val bedHour = bedClock.split(":")[0].toInt()
    val bedDay = if (bedHour >= 12) anchorDate else anchorDate.plusDays(1)
    return at(bedDay, bedClock, zone)
}

/** 취침 시각보다 뒤에 오는 최초의 기상 시각. */
fun wakeAfter(bedtime: ZonedDateTime, anchorDate: LocalDate, profile: Profile): ZonedDateTime {
    val zone = zoneOf(profile)
    val (_, wakeClock) = profile.bedWakeFor(anchorDate)
    val day = bedtime.withZoneSameInstant(zone).toLocalDate()
    var candidate = at(day, wakeClock, zone)
    if (!candidate.toInstant().isAfter(bedtime.toInstant())) {
        candidate = at(day.plusDays(1), wakeClock, zone)
    }
    return candidate
}

/**
 * `(preBed, afterBed)`.
 *
 * preBed는 `[취침-30분, 취침)`, afterBed는 `[취침, 기상)`이다.
 * 30분은 벽시계가 아니라 실제 경과 시간으로 뺀다.
 */
fun nightWindows(anchorDate: LocalDate, profile: Profile): Pair<Window, Window> {
    val bedtime = bedtimeOf(anchorDate, profile)
    val wake = wakeAfter(bedtime, anchorDate, profile)
    val bedMs = toMs(bedtime)
    // 절대 시각에서 뺀다. 벽시계 연산을 하면 DST 갭에서 시작이 끝보다 뒤로 갈 수 있다.
    return Pair(
        Window(startMs = bedMs - PRE_BED_LEAD.toMillis(), endMs = bedMs),
        Window(startMs = bedMs, endMs = toMs(wake)),
    )
}

/** `[취침-30분, 기상)` 전체 관리 구간. */
fun managedWindow(anchorDate: LocalDate, profile: Profile): Window {
    val (pre, post) = nightWindows(anchorDate, profile)
    return Window(startMs = pre.startMs, endMs = post.endMs)
}

/** 월요일부터 일요일까지 7일. */
fun weekDates(weekStart: LocalDate): List<LocalDate> {
    if (weekStart.dayOfWeek.value != 1) {
        throw ValidationException("week_start는 월요일이어야 합니다")
    }
    return (0L until 7L).map { weekStart.plusDays(it) }
}

fun previousWeekStart(weekStart: LocalDate): LocalDate = weekStart.minusDays(7)

/** 연속한 야간 구간이 겹치면 일정이 잘못된 것이다. */
fun nightsOverlap(profile: Profile, dates: List<LocalDate>): Boolean {
    val ordered = dates.sorted()
    var previousEnd: Long? = null
    for (day in ordered) {
        val window = managedWindow(day, profile)
        val end = previousEnd
        if (end != null && window.startMs < end) {
            return true
        }
        previousEnd = window.endMs
    }
    return false
}
