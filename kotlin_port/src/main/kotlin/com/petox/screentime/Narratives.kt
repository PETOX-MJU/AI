package com.petox.screentime

import java.math.BigDecimal
import java.math.RoundingMode
import java.time.LocalDate

/**
 * Python `screentime/narratives.py` 이식 — 근거 기반 한국어 설명 템플릿 (계획서 7.2, 9절).
 *
 * 경계:
 * - 숫자는 **코드가 계산해서 문장 슬롯에 넣는다.** 모델이 다시 계산하지 않는다.
 * - 통계적 유의성, 중독, 불안·우울, 실제 잠든 시각, 의지 부족을 판단하지 않는다.
 * - 확인 불가를 성공으로 설명하지 않는다.
 * - [Insight.source] 는 항상 `"template"` 이다. 규칙 기반 문장을 생성형 AI 호출 결과로 표시하지 않는다.
 *
 * 문장 다양화:
 * - 매주 같은 문장이 반복되면 사용자가 읽지 않게 된다. 도입부를 여러 개 두고 주차로 회전시킨다.
 * - **무작위를 쓰지 않는다.** 같은 입력과 같은 rules_version은 항상 같은 출력을 내야 한다.
 * - 회전은 도입부 표현만 바꾼다. 숫자와 사실을 담은 **고정 절은 모든 변형에서 동일**하다.
 *   덕분에 변형이 늘어도 의미 보장이 깨지지 않는다.
 *
 * 외부 AI는 도입하지 않기로 확정했다. 이 모듈이 설명 생성의 유일한 경로다.
 */

/** 사용 목적은 온보딩의 고정 선택지만 문장에 넣는다. 자유 입력은 신뢰하지 않는 데이터다. */
val KNOWN_PURPOSES: Set<String> = setOf("학습", "업무", "여가", "연락", "기타")

const val CODE_DECREASED: String = "SELECTED_USAGE_DECREASED"
const val CODE_OTHER_INCREASED: String = "OTHER_APPS_INCREASED"
const val CODE_NIGHT_TOP_APP: String = "NIGHT_TOP_APP"
const val CODE_DAILY_NIGHT: String = "DAILY_NIGHT_DIFFERENCE"
const val CODE_INSUFFICIENT: String = "INSUFFICIENT_DATA"

// 도입부 변형. 사실을 담은 고정 절은 각 빌더 안에 있고 여기서는 표현만 바꾼다.
private val LEAD_DECREASED: List<String> = listOf(
    "그 전주보다",
    "전주 대비",
    "지난주와 견주면",
)
private val LEAD_OTHER_INCREASED: List<String> = listOf(
    "선택한 앱은 줄었지만",
    "선택한 앱 사용은 감소했고",
    "선택한 앱 사용량은 줄었지만",
)
private val LEAD_NIGHT_TOP: List<String> = listOf(
    "야간 구간에서 가장 많이 사용한 앱은",
    "취침 전후로 가장 오래 사용한 앱은",
    "밤 시간대 사용이 가장 많았던 앱은",
)
private val TEMPLATE_DAILY_NIGHT: List<String> = listOf(
    "이번 주 일일 미션은 {daily}, 야간 미션은 {night}입니다.",
    "이번 주 판정 결과는 일일 {daily}, 야간 {night}입니다.",
    "이번 주 성적은 일일 {daily}, 야간 {night}입니다.",
)
private val LEAD_INSUFFICIENT: List<String> = listOf(
    "분석에 사용할 수 있는 날은",
    "이번 주 확인된 날은",
    "복원에 성공한 날은",
)

/**
 * 표시용 분. 내부 계산은 계속 밀리초를 쓴다.
 *
 * Python은 `round(ms / MINUTE_MS)` 다 — `int()` 절단이 아니라 반올림(banker's rounding)이다.
 * [bankersRound] (Analytics.kt) 가 Python `round()` 와 같은 half-to-even 을 재현하므로 재사용한다.
 */
fun minutes(ms: Double): Long = bankersRound(ms / MINUTE_MS.toDouble(), 0).toLong()

/**
 * Python `f"{value:.1f}"` 대응. [bankersRound] 로 half-to-even 반올림한 뒤 그 값을 포맷한다.
 * `String.format`을 원본 값에 직접 쓰면 HALF_UP 규칙이 섞여 Python과 어긋날 수 있다.
 */
private fun formatOneDecimal(value: Double): String =
    BigDecimal(bankersRound(value, 1)).setScale(1, RoundingMode.HALF_EVEN).toPlainString()

/**
 * 주차 기준 회전값. 연속한 주가 서로 다른 도입부를 쓰게 한다.
 *
 * 무작위가 아니라 날짜의 함수이므로 같은 주를 몇 번 분석해도 결과가 같다.
 *
 * Python `date.toordinal()` 은 0001-01-01 을 1로 세는 값이고, Kotlin `LocalDate.toEpochDay()`
 * 는 1970-01-01 을 0으로 센다. 실측(2026-09-07): toordinal() = 739866, toEpochDay() = 20703,
 * 차이 = 719163. `toEpochDay()` 를 그대로 쓰면 `seed % options.size` 결과가 달라져 다른
 * 문장이 나오므로 오프셋을 더해 Python 값과 맞춘다.
 */
fun rotationSeed(basisWeek: LocalDate?): Long =
    if (basisWeek == null) 0L else basisWeek.toEpochDay() + 719163L

/** Kotlin `%` 는 음수에서 음수를 반환할 수 있어 [Math.floorMod] 로 방어한다. */
private fun lead(options: List<String>, seed: Long): String =
    options[Math.floorMod(seed, options.size.toLong()).toInt()]

private fun decreased(metrics: WeeklyMetrics, seed: Long): Insight? {
    val comparison = metrics.comparison
    if (!comparison.comparable || comparison.selectedDeltaMs == null) return null
    if (comparison.selectedDeltaMs >= 0L) return null

    val dropped = minutes((-comparison.selectedDeltaMs).toDouble())
    val dailyMean = metrics.selectedDailyMeanMs
    val opening = if (dailyMean != null) {
        "지난주 선택한 앱 사용량은 하루 평균 ${minutes(dailyMean)}분입니다. "
    } else {
        ""
    }
    // 고정 절: 숫자와 "줄었습니다"는 어떤 변형에서도 유지된다.
    var text = "$opening${lead(LEAD_DECREASED, seed)} 주간 합계가 ${dropped}분 줄었습니다."
    if (comparison.selectedDeltaPct != null) {
        text += " 변화율은 ${formatOneDecimal(Math.abs(comparison.selectedDeltaPct))}%입니다."
    }
    return Insight(
        code = CODE_DECREASED,
        evidence = mapOf(
            "selected_delta_ms" to comparison.selectedDeltaMs,
            "selected_delta_pct" to comparison.selectedDeltaPct,
            "selected_daily_mean_ms" to dailyMean,
        ),
        text = text,
    )
}

/** 선택 앱이 줄면서 비선택 앱이 늘어난 사실까지만 말한다. 대체 사용의 원인을 확정하지 않는다. */
private fun otherAppsIncreased(metrics: WeeklyMetrics, seed: Long): Insight? {
    val comparison = metrics.comparison
    if (!comparison.comparable || comparison.selectedDeltaMs == null) return null
    if (comparison.selectedDeltaMs >= 0L || comparison.allAppsDeltaMs == null) return null

    val othersDelta = comparison.allAppsDeltaMs - comparison.selectedDeltaMs
    if (othersDelta <= 0L) return null
    return Insight(
        code = CODE_OTHER_INCREASED,
        evidence = mapOf(
            "other_apps_delta_ms" to othersDelta,
            "selected_delta_ms" to comparison.selectedDeltaMs,
        ),
        text = (
            "${lead(LEAD_OTHER_INCREASED, seed)} 나머지 앱 사용이 ${minutes(othersDelta.toDouble())}분 늘었습니다. " +
                "다른 앱 사용이 늘었다는 사실만 확인된 것이며 이유는 기록으로 알 수 없습니다."
        ),
    )
}

private fun nightTopApp(metrics: WeeklyMetrics, profile: Profile, seed: Long): Insight? {
    val ranked = metrics.perApp.filter {
        it.isTarget && it.nightTotalMs != null && it.nightTotalMs > 0L
    }
    if (ranked.isEmpty()) return null
    val top = ranked.maxWithOrNull(
        compareBy({ it.nightTotalMs ?: 0L }, { it.packageName })
    )!!

    val purpose = profile.purposes[top.packageName]
    val suffix = if (purpose != null && purpose in KNOWN_PURPOSES) {
        " 이 앱의 사용 목적은 '$purpose'로 설정되어 있습니다."
    } else {
        ""
    }
    val share = if (top.nightSharePct != null) {
        " 야간 사용의 ${formatOneDecimal(top.nightSharePct)}%입니다."
    } else {
        ""
    }
    return Insight(
        code = CODE_NIGHT_TOP_APP,
        evidence = mapOf(
            "package_name" to top.packageName,
            "night_total_ms" to top.nightTotalMs,
            "night_share_pct" to top.nightSharePct,
        ),
        text = (
            "${lead(LEAD_NIGHT_TOP, seed)} ${top.packageName}이고 " +
                "${minutes((top.nightTotalMs ?: 0L).toDouble())}분입니다.$share$suffix"
        ),
    )
}

/** 판정 가능한 미션이 있을 때만 성과를 나란히 설명한다. */
private fun dailyVsNight(metrics: WeeklyMetrics, seed: Long): Insight? {
    if (metrics.dailyEvaluableCount == 0L && metrics.nightEvaluableCount == 0L) return null

    // 분모가 0이면 비율 대신 사실을 적는다 (계획서 7.1).
    fun phrase(success: Long, evaluable: Long): String =
        if (evaluable == 0L) "판정 가능한 미션 없음" else "${evaluable}개 중 ${success}개 달성"

    val text = lead(TEMPLATE_DAILY_NIGHT, seed)
        .replace("{daily}", phrase(metrics.dailySuccessCount, metrics.dailyEvaluableCount))
        .replace("{night}", phrase(metrics.nightSuccessCount, metrics.nightEvaluableCount))
    return Insight(
        code = CODE_DAILY_NIGHT,
        evidence = mapOf(
            "daily_success_count" to metrics.dailySuccessCount,
            "daily_evaluable_count" to metrics.dailyEvaluableCount,
            "night_success_count" to metrics.nightSuccessCount,
            "night_evaluable_count" to metrics.nightEvaluableCount,
        ),
        text = text,
    )
}

/**
 * 최초 수집 단계와 기존 사용자의 기록 누락을 구분한다.
 *
 * 이미 개인화 목표를 쓰고 있는 사용자에게 '임시 목표를 사용합니다'라고 안내하면 사실과 다르다.
 */
private fun insufficient(metrics: WeeklyMetrics, hasActiveTarget: Boolean, seed: Long): Insight? {
    if (metrics.validDays >= DAYS_PER_WEEK && metrics.validNights >= DAYS_PER_WEEK) return null

    val counts = (
        "${lead(LEAD_INSUFFICIENT, seed)} ${metrics.validDays}일, " +
            "야간 구간은 ${metrics.validNights}개입니다. "
    )
    // 고정 절: 목표 안내 문구는 변형에 관계없이 동일해야 한다.
    val tail = if (hasActiveTarget) {
        "${DAYS_PER_WEEK}개가 모이지 않아 이번 주 성과로는 다음 목표를 계산하지 않습니다. " +
            "현재 목표는 그대로 유지됩니다."
    } else {
        "각각 ${DAYS_PER_WEEK}개가 모여야 개인 기준선을 계산합니다. " +
            "그때까지는 처음 입력한 임시 목표를 사용합니다."
    }
    return Insight(
        code = CODE_INSUFFICIENT,
        evidence = mapOf(
            "valid_days" to metrics.validDays,
            "valid_nights" to metrics.validNights,
            "has_active_target" to (if (hasActiveTarget) 1L else 0L),
        ),
        text = counts + tail,
    )
}

/**
 * 근거 필드와 문장의 숫자가 항상 일치하도록 만든다.
 *
 * `current*TargetMs` 는 사용자가 이미 수락한 개인화 목표다. 주어지면 최초 수집 단계가
 * 아니라는 뜻이므로 임시 목표 안내를 하지 않는다.
 *
 * [basisWeek] 는 도입부 회전에만 쓴다. 사실이나 수치를 바꾸지 않는다.
 */
fun renderInsights(
    metrics: WeeklyMetrics,
    profile: Profile,
    currentDailyTargetMs: Long? = null,
    currentNightTargetMs: Long? = null,
    basisWeek: LocalDate? = null,
): List<Insight> {
    val hasActiveTarget = currentDailyTargetMs != null || currentNightTargetMs != null
    val seed = rotationSeed(basisWeek)
    val candidates = listOf(
        insufficient(metrics, hasActiveTarget, seed),
        decreased(metrics, seed),
        otherAppsIncreased(metrics, seed),
        nightTopApp(metrics, profile, seed),
        dailyVsNight(metrics, seed),
    )
    return candidates.filterNotNull()
}
