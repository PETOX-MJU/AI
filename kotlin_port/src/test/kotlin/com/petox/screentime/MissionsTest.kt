package com.petox.screentime

import java.time.LocalDate
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * `missions.py` parity 테스트.
 *
 * Python 이 정본이다 — 불일치가 나면 Kotlin 을 고친다.
 */
class MissionsTest {

    private val zone = "Asia/Seoul"
    private val monday: LocalDate = LocalDate.of(2026, 9, 7)

    private fun profile(version: Long = 1) = Profile(
        version = version,
        timezone = zone,
        targetPackages = listOf("com.example.video"),
        weekdayBed = "23:00",
        weekdayWake = "07:00",
        weekendBed = "23:00",
        weekendWake = "07:00",
        temporaryDailyMs = 120 * MINUTE_MS,
        temporaryNightMs = 60 * MINUTE_MS,
        finalDailyMs = 60 * MINUTE_MS,
        finalNightMs = 30 * MINUTE_MS,
        effectiveFrom = LocalDate.of(2026, 1, 1),
    )

    private fun dailyAgg(
        p: Profile,
        date: LocalDate,
        quality: Quality = Quality.COMPLETE,
        apps: List<AppDuration>? = emptyList(),
    ): WindowAggregate {
        val window = dailyWindow(date, p)
        return WindowAggregate(
            anchorDate = date,
            kind = WindowKind.DAILY,
            startMs = window.startMs,
            endMs = window.endMs,
            observedUntilMs = window.endMs,
            quality = quality,
            profileVersion = p.version,
            apps = apps,
            measurementVersion = "m1",
        )
    }

    private fun nightAggs(
        p: Profile,
        date: LocalDate,
        preApps: List<AppDuration>? = emptyList(),
        postApps: List<AppDuration>? = emptyList(),
        preQuality: Quality = Quality.COMPLETE,
        postQuality: Quality = Quality.COMPLETE,
    ): List<WindowAggregate> {
        val (pre, post) = nightWindows(date, p)
        return listOf(
            WindowAggregate(
                anchorDate = date,
                kind = WindowKind.PRE_BED,
                startMs = pre.startMs,
                endMs = pre.endMs,
                observedUntilMs = pre.endMs,
                quality = preQuality,
                profileVersion = p.version,
                apps = preApps,
                measurementVersion = "m1",
            ),
            WindowAggregate(
                anchorDate = date,
                kind = WindowKind.AFTER_BED,
                startMs = post.startMs,
                endMs = post.endMs,
                observedUntilMs = post.endMs,
                quality = postQuality,
                profileVersion = p.version,
                apps = postApps,
                measurementVersion = "m1",
            ),
        )
    }

    private fun input(
        p: Profile = profile(),
        aggregates: List<WindowAggregate> = emptyList(),
        missions: List<Mission> = emptyList(),
        weekStart: LocalDate = monday,
        asOfMs: Long,
        currentDailyTargetMs: Long? = null,
        currentNightTargetMs: Long? = null,
    ) = AnalysisInput(
        asOfMs = asOfMs,
        lastCollectionAttemptMs = null,
        weekStart = weekStart,
        profile = p,
        aggregates = aggregates,
        missions = missions,
        currentDailyTargetMs = currentDailyTargetMs,
        currentNightTargetMs = currentNightTargetMs,
    )

    private fun mission(
        id: String,
        day: LocalDate,
        p: Profile,
        targetMs: Long,
        acceptedAtMs: Long,
        windowStartMs: Long,
        windowEndMs: Long,
    ) = Mission(
        id = id,
        anchorDate = day,
        kind = MissionKind.DAILY,
        targetMs = targetMs,
        profileVersion = p.version,
        acceptedAtMs = acceptedAtMs,
        windowStartMs = windowStartMs,
        windowEndMs = windowEndMs,
    )

    // ---- fixtures.json reduce_target — 4케이스 전부 ----

    @Test
    fun `reduce_target fixtures 4케이스`() {
        assertEquals(6_480_000L, reduceTarget(7_200_000L, 3_600_000L))
        // F18
        assertEquals(3_600_000L, reduceTarget(3_900_000L, 3_600_000L))
        // 60,000 -> 54,000 이 되지만 최소 1분(MINUTE_MS)이라 60,000 이 된다.
        assertEquals(60_000L, reduceTarget(60_000L, 0L))
        // F17
        assertEquals(3_600_000L, reduceTarget(3_600_000L, 3_600_000L))
    }

    // ---- fixtures.json mission_judgement — 6케이스 전부 ----

    @Test
    fun `mission_judgement fixtures 6케이스`() {
        val p = profile()
        val day = monday
        val windowStart = dailyWindow(day, p).startMs
        val windowEnd = dailyWindow(day, p).endMs
        val acceptedBefore = windowStart - MINUTE_MS
        val acceptedAfter = windowStart + MINUTE_MS

        // F02: target == observed -> succeeded (경계는 <=)
        val f02 = mission("F02", day, p, 1_620_000L, acceptedBefore, windowStart, windowEnd)
        val r02 = evaluateMission(f02, 1_620_000L, Quality.COMPLETE, windowEnd + 1)
        assertEquals(MissionStatus.SUCCEEDED, r02.status)

        // F03: 1ms 초과 -> failed
        val f03 = mission("F03", day, p, 1_620_000L, acceptedBefore, windowStart, windowEnd)
        val r03 = evaluateMission(f03, 1_620_001L, Quality.COMPLETE, windowEnd + 1)
        assertEquals(MissionStatus.FAILED, r03.status)

        // F04: quality unavailable -> unknown
        val f04 = mission("F04", day, p, 1_620_000L, acceptedBefore, windowStart, windowEnd)
        val r04 = evaluateMission(f04, null, Quality.UNAVAILABLE, windowEnd + 1)
        assertEquals(MissionStatus.UNKNOWN, r04.status)

        // F05: observed 0, complete -> succeeded (확인된 0)
        val f05 = mission("F05", day, p, 1_620_000L, acceptedBefore, windowStart, windowEnd)
        val r05 = evaluateMission(f05, 0L, Quality.COMPLETE, windowEnd + 1)
        assertEquals(MissionStatus.SUCCEEDED, r05.status)

        // window_closed=false, 초과 관측값이라도 -> in_progress (failed 아님)
        val mid = mission("MID", day, p, 1_620_000L, acceptedBefore, windowStart, windowEnd)
        val rMid = evaluateMission(mid, 5_940_000L, Quality.COMPLETE, windowEnd - 1)
        assertEquals(MissionStatus.IN_PROGRESS, rMid.status)

        // F16: accepted_after_window_start -> not_applicable (observed/closed 무관)
        val f16 = mission("F16", day, p, 1_620_000L, acceptedAfter, windowStart, windowEnd)
        val r16 = evaluateMission(f16, 0L, Quality.COMPLETE, windowEnd + 1)
        assertEquals(MissionStatus.NOT_APPLICABLE, r16.status)
        assertNull(r16.observedMs)
    }

    // ---- evaluate_mission 경계: 정확히 같으면 succeeded, 1ms 초과면 failed ----

    @Test
    fun `evaluate_mission 경계는 부등호가 아니라 초과다`() {
        val p = profile()
        val day = monday
        val windowStart = dailyWindow(day, p).startMs
        val windowEnd = dailyWindow(day, p).endMs
        val accepted = windowStart - MINUTE_MS

        val exact = mission("X1", day, p, 1_000_000L, accepted, windowStart, windowEnd)
        assertEquals(
            MissionStatus.SUCCEEDED,
            evaluateMission(exact, 1_000_000L, Quality.COMPLETE, windowEnd + 1).status,
        )

        val over = mission("X2", day, p, 1_000_000L, accepted, windowStart, windowEnd)
        assertEquals(
            MissionStatus.FAILED,
            evaluateMission(over, 1_000_001L, Quality.COMPLETE, windowEnd + 1).status,
        )
    }

    // ---- 구간 미종료 + 목표 초과 -> in_progress (failed 아님) ----

    @Test
    fun `구간이 안 끝났으면 목표를 초과해도 in_progress`() {
        val p = profile()
        val day = monday
        val windowStart = dailyWindow(day, p).startMs
        val windowEnd = dailyWindow(day, p).endMs
        val accepted = windowStart - MINUTE_MS

        val m = mission("Y1", day, p, 100L, accepted, windowStart, windowEnd)
        val result = evaluateMission(m, 999_999L, Quality.COMPLETE, windowEnd - 1)
        assertEquals(MissionStatus.IN_PROGRESS, result.status)
    }

    // ---- 야간: pre 만 complete 면 합산 complete 아니다 ----

    @Test
    fun `야간은 pre 와 after 가 둘 다 complete 일 때만 complete`() {
        val p = profile()
        val aggs = nightAggs(
            p, monday,
            preApps = listOf(AppDuration("com.example.video", 10 * MINUTE_MS)),
            postApps = listOf(AppDuration("com.example.video", 5 * MINUTE_MS)),
            preQuality = Quality.COMPLETE,
            postQuality = Quality.PARTIAL,
        )
        val (pre, post) = aggs[0] to aggs[1]
        val (ms, quality) = nightObservation(pre, post, setOf("com.example.video"))
        assertEquals(Quality.PARTIAL, quality)
        assertEquals(15 * MINUTE_MS, ms)
    }

    // ---- baseline_ms: 유효 6개 -> null, 7개 -> 평균 ----

    @Test
    fun `baseline_ms 는 유효 6개면 null 7개면 평균`() {
        val p = profile()
        val start = monday.minusDays(20)
        val sixDays = (0 until 6).map { start.plusDays(it.toLong()) }
        val aggs6 = sixDays.map { dailyAgg(p, it, apps = listOf(AppDuration("com.example.video", 10 * MINUTE_MS))) }
        val req6 = input(p = p, aggregates = aggs6, asOfMs = dailyWindow(sixDays.last(), p).endMs + 1)
        assertNull(baselineMs(req6, MissionKind.DAILY))

        val sevenDays = (0 until 7).map { start.plusDays(it.toLong()) }
        val aggs7 = sevenDays.map { dailyAgg(p, it, apps = listOf(AppDuration("com.example.video", 10 * MINUTE_MS))) }
        val req7 = input(p = p, aggregates = aggs7, asOfMs = dailyWindow(sevenDays.last(), p).endMs + 1)
        assertEquals(10.0 * MINUTE_MS, baselineMs(req7, MissionKind.DAILY))
    }

    // ---- baseline_ms: 8개 이상일 때 처음 7개를 쓰는지 ----

    @Test
    fun `baseline_ms 는 유효 기록이 8개 이상이면 처음 7개만 쓴다`() {
        val p = profile()
        val start = monday.minusDays(30)
        val days = (0 until 8).map { start.plusDays(it.toLong()) }
        // 마지막 날만 값이 다르다. 처음 7개 평균이면 마지막 날 값의 영향이 없어야 한다.
        val aggs = days.mapIndexed { index, day ->
            val minutes = if (index == 7) 999L else 10L
            dailyAgg(p, day, apps = listOf(AppDuration("com.example.video", minutes * MINUTE_MS)))
        }
        val req = input(p = p, aggregates = aggs, asOfMs = dailyWindow(days.last(), p).endMs + 1)
        assertEquals(10.0 * MINUTE_MS, baselineMs(req, MissionKind.DAILY))
    }

    // ---- _propose_one: 감축 후 현재 목표보다 커지지 않는다 (F17) ----

    @Test
    fun `_propose_one 은 감축해도 현재 목표보다 커지지 않는다`() {
        val p = profile()
        val metrics = WeeklyMetrics(
            validDays = 7L, validNights = 7L,
            allAppsTotalMs = null, selectedTotalMs = null,
            selectedDailyMeanMs = null, selectedNightMeanMs = null,
            preBedTotalMs = null, afterBedTotalMs = null,
            dailySuccessCount = 5L, dailyEvaluableCount = 7L,
            nightSuccessCount = 0L, nightEvaluableCount = 0L,
            perDay = emptyList(), previousPerDay = emptyList(), perApp = emptyList(),
            comparison = Comparison(comparable = false, reason = "NO_PREVIOUS_WEEK_DATA", null, null, null),
        )
        // current > finalGoal, 판정가능 7 & 성공 5 -> REDUCE_AFTER_SUCCESS.
        // reduceTarget(current, finalGoal)이 이론상 current를 넘을 일은 없지만
        // min(..., current) wrapper가 실제로 존재하는지(빠뜨리지 않았는지) 확인한다.
        val current = p.finalDailyMs + MINUTE_MS // final보다 살짝 큰 값
        val req = input(p = p, asOfMs = dailyWindow(monday, p).endMs + 1, currentDailyTargetMs = current)
        val proposals = proposeTargets(req, metrics)
        val daily = proposals.first { it.kind == MissionKind.DAILY }
        assertEquals(REASON_REDUCE_AFTER_SUCCESS, daily.reasonCode)
        // reduceTarget(reference, goal) 은 정의상 항상 reference 이하이므로 min(..., current)
        // 클램프는 수학적으로는 항상 no-op이다. 그래도 Python과 1:1로 존재해야 하는 코드이므로
        // (F17 요구사항) 결과가 여전히 current를 넘지 않는지 직접 검증한다.
        val expected = reduceTarget(current, p.finalDailyMs)
        assertEquals(expected, daily.targetMs)
        assertTrue(daily.targetMs!! <= current)

        // F17: current == finalGoal 은 사실 MAINTAIN_AT_FINAL_GOAL 분기다(현재 <= 최종 목표).
        val reqAtGoal = input(p = p, asOfMs = dailyWindow(monday, p).endMs + 1, currentDailyTargetMs = p.finalDailyMs)
        val proposalsAtGoal = proposeTargets(reqAtGoal, metrics)
        val dailyAtGoal = proposalsAtGoal.first { it.kind == MissionKind.DAILY }
        assertEquals(REASON_MAINTAIN_AT_FINAL_GOAL, dailyAtGoal.reasonCode)
        assertEquals(p.finalDailyMs, dailyAtGoal.targetMs)
    }

    // ---- _propose_one: 최초 제안이 임시 목표를 넘지 않는지 ----

    @Test
    fun `_propose_one 의 최초 제안은 임시 목표를 상한으로 삼는다`() {
        val p = profile(version = 1)
        // temporaryDailyMs = 120분. baseline 을 아주 크게 만들어 reduceTarget 결과가
        // 임시 목표(120분)를 넘도록 유도한다.
        val start = monday.minusDays(20)
        val days = (0 until 7).map { start.plusDays(it.toLong()) }
        val aggs = days.map { dailyAgg(p, it, apps = listOf(AppDuration("com.example.video", 300 * MINUTE_MS))) }
        val req = input(p = p, aggregates = aggs, asOfMs = dailyWindow(days.last(), p).endMs + 1)
        val metrics = WeeklyMetrics(
            validDays = 0L, validNights = 0L,
            allAppsTotalMs = null, selectedTotalMs = null,
            selectedDailyMeanMs = null, selectedNightMeanMs = null,
            preBedTotalMs = null, afterBedTotalMs = null,
            dailySuccessCount = 0L, dailyEvaluableCount = 0L,
            nightSuccessCount = 0L, nightEvaluableCount = 0L,
            perDay = emptyList(), previousPerDay = emptyList(), perApp = emptyList(),
            comparison = Comparison(comparable = false, reason = "NO_PREVIOUS_WEEK_DATA", null, null, null),
        )
        val proposals = proposeTargets(req, metrics)
        val daily = proposals.first { it.kind == MissionKind.DAILY }
        assertEquals(REASON_INITIAL_BASELINE, daily.reasonCode)
        assertEquals(p.temporaryDailyMs, daily.targetMs)
    }

    // ---- reason_code 문자열 5종이 Python 과 일치 ----

    @Test
    fun `reason_code 문자열 5종은 Python 상수와 정확히 같다`() {
        assertEquals("INITIAL_BASELINE", REASON_INITIAL_BASELINE)
        assertEquals("REDUCE_AFTER_SUCCESS", REASON_REDUCE_AFTER_SUCCESS)
        assertEquals("MAINTAIN_INSUFFICIENT_SUCCESS", REASON_MAINTAIN_INSUFFICIENT_SUCCESS)
        assertEquals("MAINTAIN_AT_FINAL_GOAL", REASON_MAINTAIN_AT_FINAL_GOAL)
        assertEquals("LOW_USAGE_NO_TARGET", REASON_LOW_USAGE_NO_TARGET)
    }
}
