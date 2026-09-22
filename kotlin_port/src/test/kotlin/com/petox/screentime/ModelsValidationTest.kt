package com.petox.screentime

import java.time.LocalDate
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull

/**
 * `models.py` 검증 규칙 parity 테스트.
 *
 * 기대값은 이식 당시 Python 실행값이다. 규칙을 바꿀 때는 README 「규칙을 바꿀 때」를 따른다.
 * 가장 중요한 건 경계 위조 방지다: 1분짜리 구간에 빈 앱 목록을 넣어 하루 전체를
 * '확인된 0'으로 만드는 공격을 막는다.
 */
class ModelsValidationTest {

    private val zone = "Asia/Seoul"
    private val anchor: LocalDate = LocalDate.of(2026, 9, 8) // 화요일 (평일)
    private val monday: LocalDate = LocalDate.of(2026, 9, 7)

    private fun profile(version: Long = 1) = Profile(
        version = version,
        timezone = zone,
        targetPackages = listOf("com.example.app"),
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

    /** 프로필로 계산한 진짜 daily 경계 위에 올라간 집계. */
    private fun dailyAgg(
        p: Profile = profile(),
        date: LocalDate = anchor,
        quality: Quality = Quality.COMPLETE,
        apps: List<AppDuration>? = emptyList(),
        startMs: Long? = null,
        endMs: Long? = null,
        observedUntilMs: Long? = null,
        measurementVersion: String = "m1",
    ): WindowAggregate {
        val window = dailyWindow(date, p)
        val s = startMs ?: window.startMs
        val e = endMs ?: window.endMs
        return WindowAggregate(
            anchorDate = date,
            kind = WindowKind.DAILY,
            startMs = s,
            endMs = e,
            observedUntilMs = observedUntilMs ?: e,
            quality = quality,
            profileVersion = p.version,
            apps = apps,
            measurementVersion = measurementVersion,
        )
    }

    private fun input(
        p: Profile = profile(),
        aggregates: List<WindowAggregate> = emptyList(),
        missions: List<Mission> = emptyList(),
        weekStart: LocalDate = monday,
        asOfMs: Long = dailyWindow(anchor, profile()).endMs,
    ) = AnalysisInput(
        asOfMs = asOfMs,
        lastCollectionAttemptMs = null,
        weekStart = weekStart,
        profile = p,
        aggregates = aggregates,
        missions = missions,
        currentDailyTargetMs = null,
        currentNightTargetMs = null,
    )

    // ---- 1. 경계 위조 거부 (models.py:314-325) ----

    @Test
    fun `올바른 daily 경계는 통과한다`() {
        val result = input(aggregates = listOf(dailyAgg()))
        assertEquals(1, result.aggregates.size)
    }

    @Test
    fun `경계를 1분짜리로 위조하면 거부한다`() {
        val p = profile()
        val window = dailyWindow(anchor, p)
        val forged = dailyAgg(
            p = p,
            endMs = window.startMs + MINUTE_MS,
            observedUntilMs = window.startMs + MINUTE_MS,
        )
        // 집계 자체는 유효하다 — AnalysisInput 이 프로필 경계와 대조해서 잡아야 한다.
        val exc = assertFailsWith<ValidationException> { input(aggregates = listOf(forged)) }
        assertEquals(true, exc.message!!.contains("경계"))
    }

    @Test
    fun `야간 구간도 프로필 경계와 대조한다`() {
        val p = profile()
        val (pre, _) = nightWindows(anchor, p)
        val ok = WindowAggregate(
            anchorDate = anchor,
            kind = WindowKind.PRE_BED,
            startMs = pre.startMs,
            endMs = pre.endMs,
            observedUntilMs = pre.endMs,
            quality = Quality.COMPLETE,
            profileVersion = p.version,
            apps = emptyList(),
            measurementVersion = "m1",
        )
        input(aggregates = listOf(ok), asOfMs = pre.endMs)

        val shifted = ok.copy(startMs = pre.startMs + MINUTE_MS)
        assertFailsWith<ValidationException> { input(aggregates = listOf(shifted), asOfMs = pre.endMs) }
    }

    @Test
    fun `pre_bed end_ms 를 1분짜리로 줄이면 거부한다`() {
        val p = profile()
        val (pre, _) = nightWindows(anchor, p)
        // 위조 공격의 실제 형태: 1분짜리 구간 + 빈 앱 목록 = 야간 전체가 '확인된 0'.
        val forged = WindowAggregate(
            anchorDate = anchor,
            kind = WindowKind.PRE_BED,
            startMs = pre.startMs,
            endMs = pre.startMs + MINUTE_MS,
            observedUntilMs = pre.startMs + MINUTE_MS,
            quality = Quality.COMPLETE,
            profileVersion = p.version,
            apps = emptyList(),
            measurementVersion = "m1",
        )
        assertFailsWith<ValidationException> {
            input(aggregates = listOf(forged), asOfMs = pre.endMs)
        }
    }

    @Test
    fun `after_bed 경계도 프로필과 대조한다`() {
        val p = profile()
        val (_, after) = nightWindows(anchor, p)
        val ok = WindowAggregate(
            anchorDate = anchor,
            kind = WindowKind.AFTER_BED,
            startMs = after.startMs,
            endMs = after.endMs,
            observedUntilMs = after.endMs,
            quality = Quality.COMPLETE,
            profileVersion = p.version,
            apps = emptyList(),
            measurementVersion = "m1",
        )
        input(aggregates = listOf(ok), asOfMs = after.endMs)

        val shifted = ok.copy(startMs = after.startMs + MINUTE_MS)
        assertFailsWith<ValidationException> {
            input(aggregates = listOf(shifted), asOfMs = after.endMs)
        }

        val shrunk = ok.copy(
            endMs = after.startMs + MINUTE_MS,
            observedUntilMs = after.startMs + MINUTE_MS,
        )
        assertFailsWith<ValidationException> {
            input(aggregates = listOf(shrunk), asOfMs = after.endMs)
        }
    }

    @Test
    fun `apps 는 200개까지 허용하고 201개는 거부한다`() {
        // package_name 중복이나 개별 앱 초과에 먼저 걸리면 안 되므로 고유 이름 + 0ms 를 쓴다.
        fun apps(n: Int) = (0 until n).map { AppDuration("app.p$it", 0L) }

        assertEquals(MAX_APPS_PER_WINDOW, dailyAgg(apps = apps(MAX_APPS_PER_WINDOW)).apps!!.size)
        assertFailsWith<ValidationException> { dailyAgg(apps = apps(MAX_APPS_PER_WINDOW + 1)) }
    }

    // ---- 2~7. WindowAggregate 자체 검증 ----

    @Test
    fun `unavailable 인데 apps 가 있으면 거부한다`() {
        assertFailsWith<ValidationException> {
            dailyAgg(quality = Quality.UNAVAILABLE, apps = emptyList())
        }
    }

    @Test
    fun `complete 인데 apps 가 null 이면 거부한다`() {
        assertFailsWith<ValidationException> { dailyAgg(quality = Quality.COMPLETE, apps = null) }
    }

    @Test
    fun `complete 인데 observed_until 이 end 와 다르면 거부한다`() {
        val window = dailyWindow(anchor, profile())
        assertFailsWith<ValidationException> {
            dailyAgg(observedUntilMs = window.endMs - MINUTE_MS)
        }
    }

    @Test
    fun `complete 인데 구간이 아직 안 끝났으면 거부한다`() {
        val window = dailyWindow(anchor, profile())
        assertFailsWith<ValidationException> {
            input(aggregates = listOf(dailyAgg()), asOfMs = window.endMs - MINUTE_MS)
        }
    }

    @Test
    fun `개별 앱이 구간 길이를 넘으면 거부한다`() {
        val window = dailyWindow(anchor, profile())
        assertFailsWith<ValidationException> {
            dailyAgg(apps = listOf(AppDuration("com.example.app", window.durationMs + 1)))
        }
    }

    @Test
    fun `앱 합계가 구간 길이를 넘어도 허용한다 - 멀티윈도우`() {
        val window = dailyWindow(anchor, profile())
        val two = window.durationMs * 2 / 3
        val agg = dailyAgg(
            apps = listOf(
                AppDuration("com.example.a", two),
                AppDuration("com.example.b", two),
            ),
        )
        // 합계는 구간 길이를 초과하지만 유효하다.
        assertEquals(two * 2, agg.totalMs())
        assertEquals(true, two * 2 > window.durationMs)
    }

    @Test
    fun `같은 집계 안의 package_name 중복은 거부한다`() {
        assertFailsWith<ValidationException> {
            dailyAgg(
                apps = listOf(
                    AppDuration("com.example.a", MINUTE_MS),
                    AppDuration("com.example.a", MINUTE_MS),
                ),
            )
        }
    }

    @Test
    fun `observed_until 이 구간 밖이면 거부한다`() {
        val window = dailyWindow(anchor, profile())
        assertFailsWith<ValidationException> {
            dailyAgg(
                quality = Quality.PARTIAL,
                observedUntilMs = window.startMs - MINUTE_MS,
            )
        }
    }

    // ---- 8~10. AnalysisInput 검증 ----

    @Test
    fun `week_start 가 월요일이 아니면 거부한다`() {
        assertFailsWith<ValidationException> { input(weekStart = LocalDate.of(2026, 9, 8)) }
    }

    @Test
    fun `aggregates key 중복은 거부한다`() {
        val agg = dailyAgg()
        assertFailsWith<ValidationException> { input(aggregates = listOf(agg, agg.copy())) }
    }

    @Test
    fun `anchor date 22개는 거부한다 - aggregates 와 missions 합집합`() {
        val p = profile()
        // aggregates 11일 + missions 11일 = 22개 (겹치지 않는 날짜)
        val aggDates = (0L until 11L).map { LocalDate.of(2026, 9, 1).plusDays(it) }
        val missionDates = (0L until 11L).map { LocalDate.of(2026, 9, 12).plusDays(it) }

        val aggregates = aggDates.map { date ->
            val w = dailyWindow(date, p)
            WindowAggregate(
                anchorDate = date,
                kind = WindowKind.DAILY,
                startMs = w.startMs,
                endMs = w.endMs,
                observedUntilMs = w.startMs,
                quality = Quality.PARTIAL,
                profileVersion = p.version,
                apps = emptyList(),
                measurementVersion = "m1",
            )
        }
        val missions = missionDates.mapIndexed { i, date ->
            val w = dailyWindow(date, p)
            Mission(
                id = "mission-$i",
                anchorDate = date,
                kind = MissionKind.DAILY,
                targetMs = 60 * MINUTE_MS,
                profileVersion = p.version,
                acceptedAtMs = w.startMs,
                windowStartMs = w.startMs,
                windowEndMs = w.endMs,
            )
        }
        assertEquals(22, (aggDates + missionDates).toSet().size)
        assertFailsWith<ValidationException> {
            input(aggregates = aggregates, missions = missions, asOfMs = EPOCH_MAX_MS)
        }

        // 21개(aggregates 11 + missions 10)는 통과한다.
        input(aggregates = aggregates, missions = missions.dropLast(1), asOfMs = EPOCH_MAX_MS)
    }

    @Test
    fun `measurement_version 이 둘 이상이면 거부한다`() {
        val p = profile()
        val a = dailyAgg(p = p, date = anchor, measurementVersion = "m1")
        val b = dailyAgg(p = p, date = anchor.minusDays(1), measurementVersion = "m2")
        assertFailsWith<ValidationException> { input(aggregates = listOf(a, b)) }
    }

    @Test
    fun `집계 profile_version 이 프로필과 다르면 거부한다`() {
        val p = profile(version = 1)
        val agg = dailyAgg(p = p).copy(profileVersion = 2)
        assertFailsWith<ValidationException> { input(p = p, aggregates = listOf(agg)) }
    }

    @Test
    fun `mission id 중복은 거부한다`() {
        val p = profile()
        val w = dailyWindow(anchor, p)
        val m = Mission(
            id = "same",
            anchorDate = anchor,
            kind = MissionKind.DAILY,
            targetMs = 60 * MINUTE_MS,
            profileVersion = p.version,
            acceptedAtMs = w.startMs,
            windowStartMs = w.startMs,
            windowEndMs = w.endMs,
        )
        assertFailsWith<ValidationException> {
            input(missions = listOf(m, m.copy(anchorDate = anchor.minusDays(1))))
        }
    }

    @Test
    fun `anchor_date 와 kind 가 같은 미션이 둘이면 거부한다`() {
        val p = profile()
        val w = dailyWindow(anchor, p)
        val m = Mission(
            id = "a",
            anchorDate = anchor,
            kind = MissionKind.DAILY,
            targetMs = 60 * MINUTE_MS,
            profileVersion = p.version,
            acceptedAtMs = w.startMs,
            windowStartMs = w.startMs,
            windowEndMs = w.endMs,
        )
        assertFailsWith<ValidationException> { input(missions = listOf(m, m.copy(id = "b"))) }
    }

    @Test
    fun `미션 profile_version 이 프로필과 다르면 거부한다`() {
        val p = profile(version = 1)
        val w = dailyWindow(anchor, p)
        val m = Mission(
            id = "a",
            anchorDate = anchor,
            kind = MissionKind.DAILY,
            targetMs = 60 * MINUTE_MS,
            profileVersion = 9,
            acceptedAtMs = w.startMs,
            windowStartMs = w.startMs,
            windowEndMs = w.endMs,
        )
        assertFailsWith<ValidationException> { input(p = p, missions = listOf(m)) }
    }

    // ---- 11~12. null 과 0 구분 ----

    @Test
    fun `apps 가 null 이면 total_ms 는 null 이다`() {
        val agg = dailyAgg(quality = Quality.UNAVAILABLE, apps = null)
        assertNull(agg.totalMs())
        assertNull(agg.totalMs(setOf("com.example.app")))
    }

    @Test
    fun `빈 배열은 확인된 0이라 total_ms 는 0L 이다`() {
        val agg = dailyAgg(quality = Quality.COMPLETE, apps = emptyList())
        assertEquals(0L, agg.totalMs())
        assertEquals(0L, agg.totalMs(setOf("com.example.app")))
    }

    @Test
    fun `total_ms 는 packages 로 거른다`() {
        val agg = dailyAgg(
            apps = listOf(
                AppDuration("com.example.a", 10 * MINUTE_MS),
                AppDuration("com.example.b", 5 * MINUTE_MS),
            ),
        )
        assertEquals(15 * MINUTE_MS, agg.totalMs())
        assertEquals(10 * MINUTE_MS, agg.totalMs(setOf("com.example.a")))
        assertEquals(0L, agg.totalMs(emptySet()))
    }

    // ---- 파생 프로퍼티 ----

    @Test
    fun `measurement_version 은 없으면 unknown 이다`() {
        assertEquals("unknown", input().measurementVersion)
        assertEquals("m1", input(aggregates = listOf(dailyAgg())).measurementVersion)
    }

    @Test
    fun `target_packages 는 프로필 목록의 Set 이다`() {
        assertEquals(setOf("com.example.app"), input().targetPackages)
    }

    // ---- enum wire 문자열 ----

    @Test
    fun `enum 직렬화 문자열은 Python Literal 과 같다`() {
        assertEquals("pre_bed", WindowKind.PRE_BED.wire)
        assertEquals("after_bed", WindowKind.AFTER_BED.wire)
        assertEquals("not_applicable", MissionStatus.NOT_APPLICABLE.wire)
        assertEquals("insufficient_data", WeekStatus.INSUFFICIENT_DATA.wire)
        assertEquals(Quality.COMPLETE, Quality.fromWire("complete"))
        assertEquals(MissionKind.NIGHT, MissionKind.fromWire("night"))
        assertFailsWith<ValidationException> { Quality.fromWire("COMPLETE") }
    }

    @Test
    fun `insight source 는 항상 template 이다`() {
        assertEquals("template", Insight(code = "C1", evidence = mapOf("a" to 1L), text = "x").source)
    }

    @Test
    fun `schema_version 은 1 이다`() {
        assertEquals("1", input().schemaVersion)
    }
}
