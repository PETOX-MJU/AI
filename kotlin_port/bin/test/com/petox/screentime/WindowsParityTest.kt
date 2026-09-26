package com.petox.screentime

import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * `contracts/fixtures.json` 의 `night_windows`·`daily_window_dst` 블록을 **직접 읽어** 대조한다.
 * 기대값은 이식 당시 Python 실행값이다. 규칙을 바꿀 때는 README 「규칙을 바꿀 때」를 따른다.
 */
class WindowsParityTest {

    /** DST 검사용 프로필. 야간 값은 이 케이스에서 쓰이지 않는다. */
    private fun profileIn(
        timezone: String,
        bed: String = "23:00",
        wake: String = "07:00",
    ) = Profile(
        version = 1,
        timezone = timezone,
        targetPackages = listOf("com.example.app"),
        weekdayBed = bed,
        weekdayWake = wake,
        weekendBed = bed,
        weekendWake = wake,
        temporaryDailyMs = 120 * MINUTE_MS,
        temporaryNightMs = 60 * MINUTE_MS,
        finalDailyMs = 60 * MINUTE_MS,
        finalNightMs = 30 * MINUTE_MS,
        effectiveFrom = LocalDate.of(2026, 1, 1),
    )

    // ---- fixtures.json: night_windows ----

    @Test
    fun `night_windows fixtures`() {
        for (case in Fixtures.cases("night_windows")) {
            val profile = profileIn(case.str("timezone"), bed = case.str("bed"), wake = case.str("wake"))
            val (preBed, afterBed) = nightWindows(LocalDate.parse(case.str("anchor_date")), profile)
            val pre = case.obj("expected_pre_bed")
            val after = case.obj("expected_after_bed")

            assertEquals(pre.long("start_ms"), preBed.startMs, "${case.id()} pre_bed.start_ms")
            assertEquals(pre.long("end_ms"), preBed.endMs, "${case.id()} pre_bed.end_ms")
            assertEquals(after.long("start_ms"), afterBed.startMs, "${case.id()} after_bed.start_ms")
            assertEquals(after.long("end_ms"), afterBed.endMs, "${case.id()} after_bed.end_ms")

            // expected_local 은 같은 순간을 사람이 읽는 형태로 적어 둔 것이다.
            val local = case.obj("expected_local")
            assertEquals(
                java.time.ZonedDateTime.parse(local.str("pre_start")).toInstant().toEpochMilli(),
                preBed.startMs,
                "${case.id()} expected_local.pre_start",
            )
            assertEquals(
                java.time.ZonedDateTime.parse(local.str("after_end")).toInstant().toEpochMilli(),
                afterBed.endMs,
                "${case.id()} expected_local.after_end",
            )
        }
    }

    // ---- fixtures.json: daily_window_dst ----

    @Test
    fun `daily_window_dst fixtures`() {
        for (case in Fixtures.cases("daily_window_dst")) {
            val window = dailyWindow(LocalDate.parse(case.str("date")), profileIn(case.str("timezone")))
            assertEquals(
                case.long("expected_duration_ms"),
                window.durationMs,
                "${case.id()} ${case.str("date")} 하루 길이",
            )
        }
    }

    // ---- localize() DST 정책 (windows.py docstring) ----

    @Test
    fun `중복 시각은 먼저 오는 오프셋을 쓴다`() {
        val zone = ZoneId.of("America/New_York")
        // 2026-11-01 01:30 은 EDT(-04:00)와 EST(-05:00) 두 번 존재한다.
        val moment = localize(LocalDateTime.of(2026, 11, 1, 1, 30), zone)
        assertEquals("-04:00", moment.offset.id, "먼저 오는 오프셋(EDT)이어야 한다")
    }

    @Test
    fun `존재하지 않는 시각은 전환 후 첫 유효 시각으로 옮긴다`() {
        val zone = ZoneId.of("America/New_York")
        // 2026-03-08 02:00~02:59 는 존재하지 않는다. 전환 후 첫 유효 시각은 03:00 EDT.
        val moment = localize(LocalDateTime.of(2026, 3, 8, 2, 30), zone)
        assertEquals("2026-03-08T03:00-04:00[America/New_York]", moment.toString())
    }

    // ---- 나머지 windows.py 함수 ----

    @Test
    fun `week_dates 는 월요일부터 7일이다`() {
        val monday = LocalDate.of(2026, 9, 7)
        val dates = weekDates(monday)
        assertEquals(7, dates.size)
        assertEquals(monday, dates.first())
        assertEquals(LocalDate.of(2026, 9, 13), dates.last())
        assertEquals(LocalDate.of(2026, 8, 31), previousWeekStart(monday))
    }

    @Test
    fun `week_dates 는 월요일이 아니면 거부한다`() {
        var raised = false
        try {
            weekDates(LocalDate.of(2026, 9, 8))
        } catch (exc: ValidationException) {
            raised = true
        }
        assertTrue(raised, "월요일이 아닌 week_start는 예외여야 한다")
    }

    @Test
    fun `정상 일정은 야간 구간이 겹치지 않는다`() {
        val profile = profileIn("Asia/Seoul", bed = "23:00", wake = "07:00")
        assertFalse(nightsOverlap(profile, weekDates(LocalDate.of(2026, 9, 7))))
    }

    @Test
    fun `관리 구간이 하루를 거의 채우면 연속한 밤이 겹친다`() {
        // 취침 12:00 → 관리 시작 11:30, 기상 11:50 은 취침보다 뒤라 같은 날 → 관리 종료 11:50.
        // 다음 날 관리 시작(11:30)이 전날 종료(11:50)보다 앞서므로 겹친다.
        // (Python 교차 확인: bed=12:00/wake=07:00 은 겹치지 않는다 — 기상이 다음 날 07:00 이다)
        val profile = profileIn("Asia/Seoul", bed = "12:00", wake = "11:50")
        assertTrue(nightsOverlap(profile, weekDates(LocalDate.of(2026, 9, 7))))
    }

    @Test
    fun `취침 12시 기상 7시는 겹치지 않는다`() {
        val profile = profileIn("Asia/Seoul", bed = "12:00", wake = "07:00")
        assertFalse(nightsOverlap(profile, weekDates(LocalDate.of(2026, 9, 7))))
    }

    @Test
    fun `managed_window 는 취침 30분 전부터 기상까지다`() {
        val profile = profileIn("Asia/Seoul", bed = "00:00", wake = "07:00")
        val managed = managedWindow(LocalDate.of(2026, 9, 13), profile)
        assertEquals(1789309800000L, managed.startMs)
        assertEquals(1789336800000L, managed.endMs)
        assertEquals(7 * 3_600_000L + 1_800_000L, managed.durationMs)
    }
}
