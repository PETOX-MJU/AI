package com.petox.screentime

import java.time.LocalDate
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * `analytics.py` parity 테스트.
 *
 * 기대값은 이식 당시 Python 실행값이다. 규칙을 바꿀 때는 README 「규칙을 바꿀 때」를 따른다.
 * 미션 판정 알고리즘([evaluateMission])은 4단계 범위라 이 파일에서는 스텁
 * [MissionEvaluator] 를 주입해 검증한다.
 */
class AnalyticsTest {

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
        quality: Quality = Quality.COMPLETE,
    ): List<WindowAggregate> {
        val (pre, post) = nightWindows(date, p)
        return listOf(
            WindowAggregate(
                anchorDate = date,
                kind = WindowKind.PRE_BED,
                startMs = pre.startMs,
                endMs = pre.endMs,
                observedUntilMs = pre.endMs,
                quality = quality,
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
                quality = quality,
                profileVersion = p.version,
                apps = postApps,
                measurementVersion = "m1",
            ),
        )
    }

    /** 한 주 전체(7일 daily+night, complete)를 만든다. */
    private fun fullWeek(
        p: Profile,
        weekStart: LocalDate,
        dayApps: (LocalDate) -> List<AppDuration>,
        preApps: (LocalDate) -> List<AppDuration> = { emptyList() },
        postApps: (LocalDate) -> List<AppDuration> = { emptyList() },
    ): List<WindowAggregate> {
        val result = mutableListOf<WindowAggregate>()
        for (day in weekDates(weekStart)) {
            result.add(dailyAgg(p, day, apps = dayApps(day)))
            result.addAll(nightAggs(p, day, preApps = preApps(day), postApps = postApps(day)))
        }
        return result
    }

    private fun input(
        p: Profile = profile(),
        aggregates: List<WindowAggregate> = emptyList(),
        missions: List<Mission> = emptyList(),
        weekStart: LocalDate = monday,
        asOfMs: Long,
        lastCollectionAttemptMs: Long? = null,
    ) = AnalysisInput(
        asOfMs = asOfMs,
        lastCollectionAttemptMs = lastCollectionAttemptMs,
        weekStart = weekStart,
        profile = p,
        aggregates = aggregates,
        missions = missions,
        currentDailyTargetMs = null,
        currentNightTargetMs = null,
    )

    private fun weekEndMs(p: Profile, weekStart: LocalDate): Long {
        var last = 0L
        for (day in weekDates(weekStart)) {
            val (_, post) = nightWindows(day, p)
            last = maxOf(last, dailyWindow(day, p).endMs, post.endMs)
        }
        return last
    }

    private val noopEvaluator = MissionEvaluator { mission, observed, quality, asOfMs ->
        MissionResult(mission.id, MissionStatus.UNKNOWN, observed, asOfMs)
    }

    // ---- 1. _pct 반올림 경계 (banker's rounding) ----

    @Test
    fun `pct 는 Python round 와 같은 banker's rounding 을 쓴다`() {
        // Python: round(12.345, 2) == 12.35 (12.345 의 실제 이진값은 12.34500...064 라 위로 반올림)
        assertEquals(12.35, pct(12345L, 100000L))
        // pct 는 `numerator/denominator*100` 을 계산한 뒤 반올림한다. 12355/100000*100 의
        // 실제 부동소수 연산 결과는 12.354999999999999(리터럴 12.355 와는 다른 이진값)이라
        // Python `_pct(12355, 100000)` 도 12.35 를 낸다 (round(12.355, 2) 자체는 12.36 이지만
        // 이 케이스는 나눗셈 경로를 거치므로 다르다).
        assertEquals(12.35, pct(12355L, 100000L))
        // Python round() 를 직접 거는 케이스(과제 함정 1의 예시값)는 bankersRound 로 검증한다.
        assertEquals(12.35, bankersRound(12.345, 2))
        assertEquals(12.36, bankersRound(12.355, 2))
        // Python: round(2.5) == 2 (half-to-even, 2가 짝수)
        assertEquals(2.0, bankersRound(2.5, 0))
        // Python: round(0.5) == 0
        assertEquals(0.0, bankersRound(0.5, 0))
        // Python: round(1.5) == 2
        assertEquals(2.0, bankersRound(1.5, 0))
    }

    // ---- 2. _pct 분모 0/null -> null ----

    @Test
    fun `pct 분모가 0 이거나 null 이면 null`() {
        assertNull(pct(10L, 0L))
        assertNull(pct(10L, null))
    }

    @Test
    fun `0분에서 20분으로 증가한 delta_pct 는 null 이다`() {
        // 분모가 0(이전 값 0)이면 무한대가 아니라 null. delta_ms 는 절대 증가로 그대로 보인다.
        val p = profile()
        val current = fullWeek(p, monday, dayApps = { listOf(AppDuration("com.example.video", 20 * MINUTE_MS)) })
        val prevStart = previousWeekStart(monday)
        val previous = fullWeek(p, prevStart, dayApps = { listOf(AppDuration("com.example.video", 0L)) })
        // duration_ms=0 이면 앱 자체가 누적되지 않으므로(딕셔너리에 등장 안 함) 전주 before=0.
        val req = input(p = p, aggregates = current + previous, asOfMs = weekEndMs(p, monday) + 1)
        val metrics = analyzeWeek(req, noopEvaluator)
        val app = metrics.perApp.first { it.packageName == "com.example.video" }
        val expectedTotal = 20 * 7 * MINUTE_MS
        assertEquals(expectedTotal, app.totalMs)
        assertEquals(7, metrics.previousPerDay.size)
        assertTrue(metrics.previousPerDay.all { it.selectedMs == 0L })
        // before=0 이므로 절대 증가분은 전체 합계와 같고, 퍼센트는 분모 0이라 null.
        assertEquals(expectedTotal, app.deltaMs)
        assertNull(app.deltaPct)
    }

    // ---- 3. 평균은 Double, 정수 나눗셈으로 잘리지 않는다 ----

    @Test
    fun `selected_daily_mean_ms 는 정수 나눗셈으로 잘리지 않는다`() {
        val p = profile()
        // 7일 * 10분 = 70분. 나누어떨어지지 않는 값을 만들기 위해 1ms 를 더한다.
        var first = true
        val aggregates = fullWeek(p, monday, dayApps = { day ->
            val extra = if (first.also { first = false }) 1L else 0L
            listOf(AppDuration("com.example.video", 10 * MINUTE_MS + extra))
        })
        val req = input(p = p, aggregates = aggregates, asOfMs = weekEndMs(p, monday) + 1)
        val metrics = analyzeWeek(req, noopEvaluator)
        val expectedTotal = 10 * 7 * MINUTE_MS + 1
        assertEquals(expectedTotal, metrics.selectedTotalMs)
        assertEquals(expectedTotal.toDouble() / 7.0, metrics.selectedDailyMeanMs)
        // 정수 나눗셈이었다면 소수점이 사라져 다른 값이 나왔을 것이다.
        assertTrue(metrics.selectedDailyMeanMs!! % 1.0 != 0.0)
    }

    // ---- 4. full_days 아님 -> 평균 null (0 아님) ----

    @Test
    fun `전체 7일이 아니면 평균은 null 이고 0 이 아니다`() {
        val p = profile()
        val days = weekDates(monday)
        val aggregates = days.dropLast(1).flatMap { day ->
            listOf(dailyAgg(p, day, apps = listOf(AppDuration("com.example.video", 5 * MINUTE_MS))))
        }
        val req = input(p = p, aggregates = aggregates, asOfMs = weekEndMs(p, monday) + 1)
        val metrics = analyzeWeek(req, noopEvaluator)
        assertEquals(6L, metrics.validDays)
        assertNull(metrics.selectedDailyMeanMs)
        assertNull(metrics.selectedNightMeanMs)
    }

    // ---- 5. week_status 4가지 전부 ----

    @Test
    fun `week_status in_progress -- 주가 아직 안 끝났다`() {
        val p = profile()
        val req = input(p = p, aggregates = emptyList(), asOfMs = weekEndMs(p, monday) - 1)
        assertEquals(WeekStatus.IN_PROGRESS, getWeekStatus(req))
    }

    @Test
    fun `week_status awaiting_data -- 주는 끝났지만 수집 시도가 없다`() {
        val p = profile()
        val req = input(p = p, aggregates = emptyList(), asOfMs = weekEndMs(p, monday) + 1, lastCollectionAttemptMs = null)
        assertEquals(WeekStatus.AWAITING_DATA, getWeekStatus(req))
    }

    @Test
    fun `week_status ready -- 7일 7야간 모두 complete`() {
        val p = profile()
        val aggregates = fullWeek(p, monday, dayApps = { listOf(AppDuration("com.example.video", 5 * MINUTE_MS)) })
        val end = weekEndMs(p, monday)
        val req = input(p = p, aggregates = aggregates, asOfMs = end + 1, lastCollectionAttemptMs = end + 1)
        assertEquals(WeekStatus.READY, getWeekStatus(req))
    }

    @Test
    fun `week_status insufficient_data -- 수집은 했지만 유효 구간이 모자란다`() {
        val p = profile()
        val end = weekEndMs(p, monday)
        // daily 만 3일치, night 없음 -> valid_nights 0
        val aggregates = weekDates(monday).take(3).map { dailyAgg(p, it, apps = listOf(AppDuration("com.example.video", 1L))) }
        val req = input(p = p, aggregates = aggregates, asOfMs = end + 1, lastCollectionAttemptMs = end + 1)
        assertEquals(WeekStatus.INSUFFICIENT_DATA, getWeekStatus(req))
    }

    // ---- 6. per_app 에 이전 주에만 쓰인 앱이 포함되는지 ----

    @Test
    fun `이전 주에만 쓰인 앱도 per_app 에 포함된다`() {
        val p = profile()
        val current = fullWeek(p, monday, dayApps = { listOf(AppDuration("com.example.video", 5 * MINUTE_MS)) })
        val prevStart = previousWeekStart(monday)
        val previous = fullWeek(p, prevStart, dayApps = { listOf(AppDuration("com.example.abandoned", 5 * MINUTE_MS)) })
        val req = input(p = p, aggregates = current + previous, asOfMs = weekEndMs(p, monday) + 1)
        val metrics = analyzeWeek(req, noopEvaluator)
        val names = metrics.perApp.map { it.packageName }
        assertTrue("com.example.abandoned" in names)
        val abandoned = metrics.perApp.first { it.packageName == "com.example.abandoned" }
        // 이번 주엔 전혀 안 썼고 daily complete 구간이 있으므로 '확인된 0'이다.
        assertEquals(0L, abandoned.totalMs)
        assertEquals(-100.0, abandoned.deltaPct)
    }

    // ---- 7. per_app 에 target_packages 가 포함되는지 ----

    @Test
    fun `사용 기록이 전혀 없는 target_package 도 per_app 에 포함된다`() {
        val p = profile() // targetPackages = ["com.example.video"]
        val aggregates = fullWeek(p, monday, dayApps = { listOf(AppDuration("com.example.other", 5 * MINUTE_MS)) })
        val req = input(p = p, aggregates = aggregates, asOfMs = weekEndMs(p, monday) + 1)
        val metrics = analyzeWeek(req, noopEvaluator)
        val target = metrics.perApp.firstOrNull { it.packageName == "com.example.video" }
        assertTrue(target != null)
        assertEquals(true, target!!.isTarget)
        assertEquals(0L, target.totalMs)
    }

    // ---- 8. 미션 카운트 분모에서 unknown/in_progress/not_applicable 제외 ----

    @Test
    fun `미션 성공률 분모는 unknown, in_progress, not_applicable 을 제외한다`() {
        val p = profile()
        fun mission(id: String, day: LocalDate) = Mission(
            id = id,
            anchorDate = day,
            kind = MissionKind.DAILY,
            targetMs = 10 * MINUTE_MS,
            profileVersion = p.version,
            acceptedAtMs = dailyWindow(day, p).startMs - MINUTE_MS,
            windowStartMs = dailyWindow(day, p).startMs,
            windowEndMs = dailyWindow(day, p).endMs,
        )
        val days = weekDates(monday)
        val missions = listOf(
            mission("succeeded", days[0]),
            mission("failed", days[1]),
            mission("unknown", days[2]),
            mission("in_progress", days[3]),
            mission("not_applicable", days[4]),
        )
        val statusById = mapOf(
            "succeeded" to MissionStatus.SUCCEEDED,
            "failed" to MissionStatus.FAILED,
            "unknown" to MissionStatus.UNKNOWN,
            "in_progress" to MissionStatus.IN_PROGRESS,
            "not_applicable" to MissionStatus.NOT_APPLICABLE,
        )
        val evaluator = MissionEvaluator { mission, observed, _, asOfMs ->
            MissionResult(mission.id, statusById.getValue(mission.id), observed, asOfMs)
        }
        val req = input(p = p, aggregates = emptyList(), missions = missions, asOfMs = weekEndMs(p, monday) + 1)
        val metrics = analyzeWeek(req, evaluator)
        // succeeded + failed 만 평가 가능 -> 분모 2, 성공 1
        assertEquals(2L, metrics.dailyEvaluableCount)
        assertEquals(1L, metrics.dailySuccessCount)
        assertEquals(0L, metrics.nightEvaluableCount)
        assertEquals(0L, metrics.nightSuccessCount)
    }

    @Test
    fun `이전 주 미션은 카운트에서 제외된다`() {
        val p = profile()
        val prevStart = previousWeekStart(monday)
        val prevDay = weekDates(prevStart)[0]
        val thisDay = weekDates(monday)[0]
        fun mission(id: String, day: LocalDate) = Mission(
            id = id,
            anchorDate = day,
            kind = MissionKind.DAILY,
            targetMs = 10 * MINUTE_MS,
            profileVersion = p.version,
            acceptedAtMs = dailyWindow(day, p).startMs - MINUTE_MS,
            windowStartMs = dailyWindow(day, p).startMs,
            windowEndMs = dailyWindow(day, p).endMs,
        )
        val missions = listOf(mission("prev", prevDay), mission("this", thisDay))
        val evaluator = MissionEvaluator { mission, observed, _, asOfMs ->
            MissionResult(mission.id, MissionStatus.SUCCEEDED, observed, asOfMs)
        }
        val req = input(p = p, aggregates = emptyList(), missions = missions, asOfMs = weekEndMs(p, monday) + 1)
        val metrics = analyzeWeek(req, evaluator)
        // mission_results 에는 둘 다 들어가지만 카운트는 이번 주(this)만.
        assertEquals(1L, metrics.dailyEvaluableCount)
        assertEquals(1L, metrics.dailySuccessCount)
    }

    // ---- 9. complete-week 예제와 metrics 부분 대조 ----

    @Test
    fun `complete-week 예제의 metrics 핵심 값과 일치한다`() {
        val p = Profile(
            version = 1,
            timezone = "Asia/Seoul",
            targetPackages = listOf("com.example.video"),
            purposes = mapOf("com.example.video" to "여가"),
            weekdayBed = "00:00",
            weekdayWake = "07:00",
            weekendBed = "00:00",
            weekendWake = "07:00",
            temporaryDailyMs = 7_200_000L,
            temporaryNightMs = 1_800_000L,
            finalDailyMs = 3_600_000L,
            finalNightMs = 0L,
            effectiveFrom = LocalDate.of(2026, 9, 7),
        )
        val weekStart = LocalDate.of(2026, 9, 7)
        val aggregates = fullWeek(
            p,
            weekStart,
            dayApps = {
                listOf(
                    AppDuration("com.example.video", 7_200_000L),
                    AppDuration("com.example.chat", 2_400_000L),
                )
            },
            preApps = { listOf(AppDuration("com.example.video", 1_200_000L)) },
            postApps = { listOf(AppDuration("com.example.video", 600_000L)) },
        )
        val req = input(p = p, aggregates = aggregates, weekStart = weekStart, asOfMs = weekEndMs(p, weekStart) + 1)
        val metrics = analyzeWeek(req, noopEvaluator)

        // contracts/examples/complete-week.output.json 의 metrics 블록과 대조.
        assertEquals(7L, metrics.validDays)
        assertEquals(7L, metrics.validNights)
        assertEquals(67_200_000L, metrics.allAppsTotalMs)
        assertEquals(50_400_000L, metrics.selectedTotalMs)
        assertEquals(7_200_000.0, metrics.selectedDailyMeanMs)
        assertEquals(1_800_000.0, metrics.selectedNightMeanMs)
        assertEquals(8_400_000L, metrics.preBedTotalMs)
        assertEquals(4_200_000L, metrics.afterBedTotalMs)
        assertEquals(false, metrics.comparison.comparable)
        assertEquals("NO_PREVIOUS_WEEK_DATA", metrics.comparison.reason)

        val video = metrics.perApp.first { it.packageName == "com.example.video" }
        assertEquals(50_400_000L, video.totalMs)
        assertEquals(75.0, video.sharePct)
        assertEquals(12_600_000L, video.nightTotalMs)
        assertEquals(100.0, video.nightSharePct)

        val chat = metrics.perApp.first { it.packageName == "com.example.chat" }
        assertEquals(16_800_000L, chat.totalMs)
        assertEquals(25.0, chat.sharePct)
        assertEquals(0L, chat.nightTotalMs)
        assertNull(chat.nightSharePct)
    }
}
