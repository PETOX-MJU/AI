package com.petox.screentime

import java.math.BigDecimal
import java.math.RoundingMode
import java.time.LocalDate

/**
 * Python `screentime/analytics.py` 이식 — 주간 집계·평균·비교.
 *
 * 핵심 규칙:
 * - `*_total_ms` 는 **complete 구간만** 합산한다. partial의 확인된 값은 per_day에만 보인다.
 * - 유효 구간이 하나도 없으면 합계는 0이 아니라 `null` 이다.
 * - 평균은 해당 주의 complete 구간이 7개일 때만 반환한다.
 *
 * 판정 알고리즘 자체([evaluateMission])는 `Missions.kt` 에 있다. 다만 "무엇이 관측되었는가"
 * ([nightObservation], [observedForMission])는 주간 합계([weekTotals])가 그대로 의존하는
 * 핵심 산술이라 여기서 다룬다.
 */

const val DAYS_PER_WEEK: Long = 7L

/** 한 주의 확정 집계. 비교를 위해 현재 주와 이전 주에 같은 계산을 쓴다. */
class WeekTotals(
    var validDays: Long = 0L,
    var validNights: Long = 0L,
    var selectedTotalMs: Long? = null,
    var allAppsTotalMs: Long? = null,
    var preBedTotalMs: Long? = null,
    var afterBedTotalMs: Long? = null,
    var nightTotalMs: Long? = null,
    val perAppDayMs: LinkedHashMap<String, Long> = LinkedHashMap(),
    val perAppNightMs: LinkedHashMap<String, Long> = LinkedHashMap(),
) {
    val isFull: Boolean
        get() = validDays == DAYS_PER_WEEK
}

fun indexAggregates(aggregates: List<WindowAggregate>): Map<Pair<LocalDate, WindowKind>, WindowAggregate> =
    aggregates.associateBy { it.anchorDate to it.kind }

private fun accumulate(totals: MutableMap<String, Long>, aggregate: WindowAggregate) {
    for (app in aggregate.apps ?: emptyList()) {
        totals[app.packageName] = (totals[app.packageName] ?: 0L) + app.durationMs
    }
}

/** complete 구간만 사용해 한 주를 합산한다. */
fun weekTotals(request: AnalysisInput, weekStart: LocalDate): WeekTotals {
    val index = indexAggregates(request.aggregates)
    val packages = request.targetPackages
    val result = WeekTotals()

    var selected = 0L
    var allApps = 0L
    var preBed = 0L
    var afterBed = 0L
    var night = 0L
    var hasDaily = false
    var hasPre = false
    var hasAfter = false
    var hasNight = false

    for (day in weekDates(weekStart)) {
        val daily = index[day to WindowKind.DAILY]
        if (daily != null && daily.quality == Quality.COMPLETE) {
            result.validDays += 1
            hasDaily = true
            selected += daily.totalMs(packages) ?: 0L
            allApps += daily.totalMs() ?: 0L
            accumulate(result.perAppDayMs, daily)
        }

        val pre = index[day to WindowKind.PRE_BED]
        if (pre != null && pre.quality == Quality.COMPLETE) {
            hasPre = true
            preBed += pre.totalMs(packages) ?: 0L
        }

        val post = index[day to WindowKind.AFTER_BED]
        if (post != null && post.quality == Quality.COMPLETE) {
            hasAfter = true
            afterBed += post.totalMs(packages) ?: 0L
        }

        val (nightMs, nightQuality) = nightObservation(pre, post, packages)
        if (nightQuality == Quality.COMPLETE && nightMs != null) {
            result.validNights += 1
            hasNight = true
            night += nightMs
            for (window in listOf(pre, post)) {
                if (window != null) accumulate(result.perAppNightMs, window)
            }
        }
    }

    result.selectedTotalMs = if (hasDaily) selected else null
    result.allAppsTotalMs = if (hasDaily) allApps else null
    result.preBedTotalMs = if (hasPre) preBed else null
    result.afterBedTotalMs = if (hasAfter) afterBed else null
    result.nightTotalMs = if (hasNight) night else null
    return result
}

/**
 * 야간은 pre_bed와 after_bed가 **둘 다** complete일 때만 complete다.
 *
 * Python `missions.night_observation` 이식. 미션 판정 전용이 아니라 [weekTotals] 자체가
 * 의존하는 관측 계산이라 여기서 옮긴다 (판정 알고리즘 [evaluateMission]과는 별개).
 */
fun nightObservation(
    pre: WindowAggregate?,
    post: WindowAggregate?,
    packages: Set<String>,
): Pair<Long?, Quality> {
    if (pre == null || post == null) return null to Quality.UNAVAILABLE

    if (pre.quality == Quality.COMPLETE && post.quality == Quality.COMPLETE) {
        val preMs = pre.totalMs(packages)
        val postMs = post.totalMs(packages)
        if (preMs == null || postMs == null) return null to Quality.UNAVAILABLE
        return (preMs + postMs) to Quality.COMPLETE
    }

    val quality = if (pre.quality == Quality.UNAVAILABLE || post.quality == Quality.UNAVAILABLE) {
        Quality.UNAVAILABLE
    } else {
        Quality.PARTIAL
    }
    val preMs = pre.totalMs(packages)
    val postMs = post.totalMs(packages)
    if (preMs == null || postMs == null) return null to quality
    return (preMs + postMs) to quality
}

/** Python `missions.observed_for_mission` 이식. 미션 구간에서 확인된 선택 앱 사용량과 품질. */
fun observedForMission(request: AnalysisInput, mission: Mission): Pair<Long?, Quality> {
    val index = indexAggregates(request.aggregates)
    val packages = request.targetPackages
    if (mission.kind == MissionKind.DAILY) {
        val agg = index[mission.anchorDate to WindowKind.DAILY] ?: return null to Quality.UNAVAILABLE
        return agg.totalMs(packages) to agg.quality
    }
    return nightObservation(
        index[mission.anchorDate to WindowKind.PRE_BED],
        index[mission.anchorDate to WindowKind.AFTER_BED],
        packages,
    )
}

/** Python `get_week_status`. 계획서 5.3의 네 가지 상태. */
fun getWeekStatus(request: AnalysisInput): WeekStatus {
    val profile = request.profile
    var lastEnd = 0L
    for (day in weekDates(request.weekStart)) {
        val (_, post) = nightWindows(day, profile)
        lastEnd = maxOf(lastEnd, dailyWindow(day, profile).endMs, post.endMs)
    }

    if (request.asOfMs < lastEnd) return WeekStatus.IN_PROGRESS

    val attempt = request.lastCollectionAttemptMs
    if (attempt == null || attempt < lastEnd) {
        // 구간은 끝났지만 그 뒤로 수집을 시도한 적이 없다.
        return WeekStatus.AWAITING_DATA
    }

    val totals = weekTotals(request, request.weekStart)
    return if (totals.validDays == DAYS_PER_WEEK && totals.validNights == DAYS_PER_WEEK) {
        WeekStatus.READY
    } else {
        WeekStatus.INSUFFICIENT_DATA
    }
}

/**
 * Python `round(x, ndigits)` 과 동일한 banker's rounding(half-to-even)을 재현한다.
 *
 * `BigDecimal(Double)` (== [BigDecimal.valueOf] 이 아님)로 이중 정밀도 값의 **정확한** 이진
 * 표현을 그대로 가져온 뒤 반올림한다. Python `round()`도 같은 방식으로 이중 정밀도의 정확한
 * 값을 기준으로 반올림하므로, `Decimal.valueOf`(문자열 기반, 반올림된 표현을 씀)를 쓰면
 * 12.345/12.355 같은 값에서 어긋난다.
 */
fun bankersRound(value: Double, scale: Int): Double =
    BigDecimal(value).setScale(scale, RoundingMode.HALF_EVEN).toDouble()

/** Python `_pct`. 분모가 0이거나 없으면 null. `0분 -> 20분`을 무한대로 만들지 않는다. */
fun pct(numerator: Long, denominator: Long?): Double? {
    if (denominator == null || denominator == 0L) return null
    val value = numerator.toDouble() / denominator.toDouble() * 100.0
    return bankersRound(value, 2)
}

/** Python `_build_comparison`. 전주 대비. */
fun buildComparison(current: WeekTotals, previous: WeekTotals, hasPrevious: Boolean): Comparison {
    if (!hasPrevious) {
        return Comparison(
            comparable = false,
            reason = "NO_PREVIOUS_WEEK_DATA",
            selectedDeltaMs = null,
            selectedDeltaPct = null,
            allAppsDeltaMs = null,
        )
    }
    if (!(current.isFull && previous.isFull)) {
        // 완전한 두 주가 아니면 정식 증감률을 만들지 않는다.
        return Comparison(
            comparable = false,
            reason = "INCOMPLETE_WEEK",
            selectedDeltaMs = null,
            selectedDeltaPct = null,
            allAppsDeltaMs = null,
        )
    }

    val delta = (current.selectedTotalMs ?: 0L) - (previous.selectedTotalMs ?: 0L)
    return Comparison(
        comparable = true,
        reason = null,
        selectedDeltaMs = delta,
        selectedDeltaPct = pct(delta, previous.selectedTotalMs),
        allAppsDeltaMs = (current.allAppsTotalMs ?: 0L) - (previous.allAppsTotalMs ?: 0L),
    )
}

/** Python `_day_metrics`. per_day는 partial의 확인된 값도 품질과 함께 보여준다. */
fun dayMetrics(request: AnalysisInput, weekStart: LocalDate = request.weekStart): List<DayMetrics> {
    val index = indexAggregates(request.aggregates)
    val packages = request.targetPackages
    val rows = mutableListOf<DayMetrics>()

    for (day in weekDates(weekStart)) {
        val daily = index[day to WindowKind.DAILY]
        val pre = index[day to WindowKind.PRE_BED]
        val post = index[day to WindowKind.AFTER_BED]
        rows.add(
            DayMetrics(
                date = day,
                dailyQuality = daily?.quality,
                preBedQuality = pre?.quality,
                afterBedQuality = post?.quality,
                allAppsMs = daily?.totalMs(),
                selectedMs = daily?.totalMs(packages),
                preBedMs = pre?.totalMs(packages),
                afterBedMs = post?.totalMs(packages),
            )
        )
    }
    return rows
}

/** Python `_app_metrics`. */
fun appMetrics(
    request: AnalysisInput,
    current: WeekTotals,
    previous: WeekTotals,
    comparison: Comparison,
): List<AppMetrics> {
    val packages = request.targetPackages
    // 이전 주에만 쓰인 앱과 선택한 앱도 포함한다. 사용을 완전히 끊은 앱의
    // 0분·-100% 변화가 비교 화면에서 사라지면 안 된다.
    val names = sortedSetOf<String>().apply {
        addAll(current.perAppDayMs.keys)
        addAll(current.perAppNightMs.keys)
        addAll(previous.perAppDayMs.keys)
        addAll(previous.perAppNightMs.keys)
        addAll(packages)
    }
    // complete 구간이 하나라도 있으면 기록에 없는 앱은 '확인된 0'이다.
    val dayDefault: Long? = if (current.allAppsTotalMs != null) 0L else null
    val nightDefault: Long? = if (current.validNights > 0L) 0L else null
    val rows = mutableListOf<AppMetrics>()

    for (name in names) {
        val isTarget = name in packages
        val total = current.perAppDayMs[name] ?: dayDefault
        val nightTotal = current.perAppNightMs[name] ?: nightDefault
        var deltaMs: Long? = null
        var deltaPct: Double? = null
        if (comparison.comparable) {
            val before = previous.perAppDayMs[name] ?: 0L
            deltaMs = (total ?: 0L) - before
            deltaPct = pct(deltaMs, before)
        }

        rows.add(
            AppMetrics(
                packageName = name,
                isTarget = isTarget,
                totalMs = total,
                sharePct = if (total != null) pct(total, current.allAppsTotalMs) else null,
                nightTotalMs = nightTotal,
                // 야간 비중의 분모는 선택 앱 야간 합계다. 비선택 앱에서는 null이다.
                nightSharePct = if (isTarget && nightTotal != null) pct(nightTotal, current.nightTotalMs) else null,
                deltaMs = deltaMs,
                deltaPct = deltaPct,
            )
        )
    }
    return rows
}

/** 입력으로 받은 미션 스냅샷만 판정한다. 미션을 새로 만들지 않는다. */
fun missionResults(request: AnalysisInput): List<MissionResult> {
    val sorted = request.missions.sortedWith(
        compareBy<Mission> { it.anchorDate }.thenBy { it.kind.wire }.thenBy { it.id }
    )
    return sorted.map { mission ->
        val (observed, quality) = observedForMission(request, mission)
        evaluateMission(mission, observed, quality, request.asOfMs)
    }
}

/** [_mission_counts]의 반환값. 성공률 분모·분자 카운트. */
data class MissionCounts(
    val dailySuccess: Long,
    val dailyEvaluable: Long,
    val nightSuccess: Long,
    val nightEvaluable: Long,
)

/**
 * Python `_mission_counts`. **보고서 주간의** 미션만 센다. 성공률 분모에서
 * unknown·in_progress·not_applicable은 제외한다.
 *
 * 입력에는 이전 주 미션도 함께 올 수 있다. 주간으로 거르지 않으면 여러 주의 성적이
 * 합산되어 감축 조건(판정 7개·성공 5개)을 잘못 통과시킨다.
 */
fun missionCounts(results: List<MissionResult>, request: AnalysisInput): MissionCounts {
    val inWeek = weekDates(request.weekStart).toSet()
    val kinds = request.missions.filter { it.anchorDate in inWeek }.associate { it.id to it.kind }

    var dailySuccess = 0L
    var dailyEvaluable = 0L
    var nightSuccess = 0L
    var nightEvaluable = 0L

    for (result in results) {
        val kind = kinds[result.missionId] ?: continue
        if (result.status != MissionStatus.SUCCEEDED && result.status != MissionStatus.FAILED) continue
        when (kind) {
            MissionKind.DAILY -> {
                dailyEvaluable += 1
                if (result.status == MissionStatus.SUCCEEDED) dailySuccess += 1
            }
            MissionKind.NIGHT -> {
                nightEvaluable += 1
                if (result.status == MissionStatus.SUCCEEDED) nightSuccess += 1
            }
        }
    }
    return MissionCounts(dailySuccess, dailyEvaluable, nightSuccess, nightEvaluable)
}

/**
 * 주간 지표. [missionResults] 는 호출자가 이미 계산한 판정 결과다 — 같은 판정을
 * 두 번 돌리지 않으려고 넘겨받는다 (`analyze` 가 출력에도 그대로 쓴다).
 */
fun analyzeWeek(request: AnalysisInput, missionResults: List<MissionResult>): WeeklyMetrics {
    val current = weekTotals(request, request.weekStart)
    val prevStart = previousWeekStart(request.weekStart)
    val prevDates = weekDates(prevStart).toSet()
    val hasPrevious = request.aggregates.any { it.anchorDate in prevDates }
    val previous = if (hasPrevious) weekTotals(request, prevStart) else WeekTotals()

    val comparison = buildComparison(current, previous, hasPrevious)
    val counts = missionCounts(missionResults, request)

    val fullDays = current.validDays == DAYS_PER_WEEK
    val fullNights = current.validNights == DAYS_PER_WEEK

    return WeeklyMetrics(
        validDays = current.validDays,
        validNights = current.validNights,
        allAppsTotalMs = current.allAppsTotalMs,
        selectedTotalMs = current.selectedTotalMs,
        // 평균은 7개가 다 모였을 때만 낸다. 부분 주의 평균은 오해를 만든다.
        selectedDailyMeanMs = if (fullDays) (current.selectedTotalMs ?: 0L).toDouble() / DAYS_PER_WEEK else null,
        selectedNightMeanMs = if (fullNights) (current.nightTotalMs ?: 0L).toDouble() / DAYS_PER_WEEK else null,
        preBedTotalMs = current.preBedTotalMs,
        afterBedTotalMs = current.afterBedTotalMs,
        dailySuccessCount = counts.dailySuccess,
        dailyEvaluableCount = counts.dailyEvaluable,
        nightSuccessCount = counts.nightSuccess,
        nightEvaluableCount = counts.nightEvaluable,
        perDay = dayMetrics(request),
        previousPerDay = if (hasPrevious) dayMetrics(request, prevStart) else emptyList(),
        perApp = appMetrics(request, current, previous, comparison),
        comparison = comparison,
    )
}
