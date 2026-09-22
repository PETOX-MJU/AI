package com.petox.screentime

import java.math.BigDecimal
import java.math.RoundingMode

/**
 * Python `screentime/missions.py` 이식 — 목표 제안과 미션 판정.
 *
 * 전부 순수 함수다. 여기서 만든 [Proposal] 은 추천이며 활성 미션이 아니다.
 * 실제 수락·저장·활성화는 앱의 저장 계층(Room)이 한다.
 *
 * [nightObservation]/[observedForMission] 은 [weekTotals] 도 의존하는 관측 계산이라
 * `Analytics.kt` 에 이미 이식되어 있다 — 여기서는 재사용만 한다.
 */

const val BASELINE_SAMPLES: Long = 7L

/** 직전 주에 이만큼 판정 가능해야 추가 감축을 제안한다. */
const val REQUIRED_EVALUABLE: Long = 7L

/** 그중 이만큼 성공해야 한다. */
const val REQUIRED_SUCCESSES: Long = 5L

const val REASON_INITIAL_BASELINE: String = "INITIAL_BASELINE"
const val REASON_REDUCE_AFTER_SUCCESS: String = "REDUCE_AFTER_SUCCESS"
const val REASON_MAINTAIN_INSUFFICIENT_SUCCESS: String = "MAINTAIN_INSUFFICIENT_SUCCESS"
const val REASON_MAINTAIN_AT_FINAL_GOAL: String = "MAINTAIN_AT_FINAL_GOAL"
const val REASON_LOW_USAGE_NO_TARGET: String = "LOW_USAGE_NO_TARGET"

/**
 * 기준값에서 10% 낮춘 분 단위 목표. 최종 목표 아래로 내려가지 않는다.
 *
 * 작은 양수가 반올림만으로 0이 되지 않게 최소 1분을 유지한다.
 * 목표 0은 사용자가 최종 목표를 0으로 두고 명시적으로 선택한 경우에만 나온다.
 *
 * Python은 `Decimal("0.90")` 으로 정확히 0.90을 곱한다. `BigDecimal("0.90")` 을 써서
 * `Double` 리터럴(0.90의 이진 근사값)이 아니라 정확한 십진수 곱셈을 재현한다 — 더 큰
 * `referenceMs`(밀리초 상한 `2^53-1`)에서 갈릴 수 있고, `Double` 은 정밀도 손실이 소리 없이
 * 누적된다. `fixtures.json` 의 `reduce_target` 4케이스로 증명됨(0~20,000,000ms 범위
 * 334개 표본에서 Decimal/Double 결과가 100% 일치했지만 BigDecimal이 더 안전하다).
 */
fun reduceTarget(referenceMs: Long, finalGoalMs: Long): Long {
    if (referenceMs <= finalGoalMs) return referenceMs
    val reduced = BigDecimal(referenceMs).multiply(BigDecimal("0.90"))
    val minutes = reduced.divide(BigDecimal(MINUTE_MS), 0, RoundingMode.FLOOR).toLong()
    val candidate = maxOf(MINUTE_MS, minutes * MINUTE_MS)
    return minOf(referenceMs, maxOf(finalGoalMs, candidate))
}

/**
 * 계획서 8.3의 판정 순서를 그대로 따른다. 순서가 중요하다 — `not_applicable` 검사가
 * 가장 먼저다. 목표를 초과했더라도 구간이 안 끝났으면 `in_progress` 다. 미리 `failed` 로
 * 만들면 버그다.
 *
 * 데이터가 없다는 이유로 성공을 만들지 않는다. 확인 불가는 `unknown` 이다.
 */
fun evaluateMission(
    mission: Mission,
    observedMs: Long?,
    quality: Quality,
    asOfMs: Long,
): MissionResult {
    val status: MissionStatus
    val reported: Long?
    if (mission.acceptedAtMs > mission.windowStartMs) {
        // 구간이 시작한 뒤 수락된 미션은 그 구간의 공식 미션이 아니다 (F12/F16).
        status = MissionStatus.NOT_APPLICABLE
        reported = null
    } else if (asOfMs < mission.windowEndMs) {
        status = MissionStatus.IN_PROGRESS
        reported = observedMs
    } else if (quality != Quality.COMPLETE || observedMs == null) {
        status = MissionStatus.UNKNOWN
        reported = observedMs
    } else if (observedMs <= mission.targetMs) {
        status = MissionStatus.SUCCEEDED
        reported = observedMs
    } else {
        status = MissionStatus.FAILED
        reported = observedMs
    }
    return MissionResult(
        missionId = mission.id,
        status = status,
        observedMs = reported,
        evaluatedAtMs = asOfMs,
    )
}

/**
 * 요청 안의 유효 기록을 날짜순으로 정렬해 **처음 7개**의 평균 (마지막 7개가 아니다).
 *
 * 일일과 야간의 최초 기준선 확보 시점은 다를 수 있다. 7개 미만이면 `null` 을 돌려준다
 * (0이 아니다). 반환 타입이 `Double?` 이라 `sum / 7` 에서 정수 나눗셈이 되지 않게
 * `.toDouble()` 을 명시한다.
 */
fun baselineMs(request: AnalysisInput, kind: MissionKind): Double? {
    val packages = request.targetPackages
    val index = indexAggregates(request.aggregates)
    val dates = request.aggregates.map { it.anchorDate }.toSortedSet()
    val samples = mutableListOf<Long>()

    for (day in dates) {
        val value: Long?
        if (kind == MissionKind.DAILY) {
            val agg = index[day to WindowKind.DAILY]
            if (agg == null || agg.quality != Quality.COMPLETE) continue
            value = agg.totalMs(packages)
        } else {
            val (nightMs, quality) = nightObservation(
                index[day to WindowKind.PRE_BED],
                index[day to WindowKind.AFTER_BED],
                packages,
            )
            if (quality != Quality.COMPLETE) continue
            value = nightMs
        }
        if (value == null) continue // pragma: complete면 항상 값이 있다
        samples.add(value)
        if (samples.size.toLong() == BASELINE_SAMPLES) break
    }

    if (samples.size.toLong() < BASELINE_SAMPLES) return null
    return samples.sum().toDouble() / BASELINE_SAMPLES.toDouble()
}

/** [MissionKind] 에 따른 (판정가능, 성공) 카운트. */
private fun performance(metrics: WeeklyMetrics, kind: MissionKind): Pair<Long, Long> =
    if (kind == MissionKind.DAILY) {
        metrics.dailyEvaluableCount to metrics.dailySuccessCount
    } else {
        metrics.nightEvaluableCount to metrics.nightSuccessCount
    }

/** 유형별로 최대 한 개의 제안. 완화는 사용자 직접 수정으로만 가능하다. */
fun proposeTargets(request: AnalysisInput, metrics: WeeklyMetrics): List<Proposal> {
    val profile = request.profile
    data class Settings(val current: Long?, val finalGoal: Long, val temporary: Long)
    val settings = mapOf(
        MissionKind.DAILY to Settings(request.currentDailyTargetMs, profile.finalDailyMs, profile.temporaryDailyMs),
        MissionKind.NIGHT to Settings(request.currentNightTargetMs, profile.finalNightMs, profile.temporaryNightMs),
    )

    val proposals = mutableListOf<Proposal>()
    for (kind in listOf(MissionKind.DAILY, MissionKind.NIGHT)) {
        val s = settings.getValue(kind)
        val (target, reason) = proposeOne(request, metrics, kind, s.current, s.finalGoal, s.temporary)
        if (reason == null) continue // 기준선을 확보하지 못한 유형은 제안을 비워 둔다
        proposals.add(
            Proposal(
                kind = kind,
                targetMs = target,
                reasonCode = reason,
                basisWeek = request.weekStart,
                profileVersion = profile.version,
                rulesVersion = RULES_VERSION,
            )
        )
    }
    return proposals
}

private fun proposeOne(
    request: AnalysisInput,
    metrics: WeeklyMetrics,
    kind: MissionKind,
    current: Long?,
    finalGoal: Long,
    temporary: Long,
): Pair<Long?, String?> {
    if (current == null) {
        val baseline = baselineMs(request, kind)
            ?: return null to null // 유효 7개가 없으면 제안하지 않는다. 설명이 이유를 알린다.
        if (baseline < MINUTE_MS) {
            // 초 단위 기준선을 분 단위 목표로 강제 변환하지 않는다.
            return null to REASON_LOW_USAGE_NO_TARGET
        }
        val candidate = reduceTarget(baseline.toLong(), finalGoal)
        // 최초 제안은 임시 목표를 상한으로 삼는다.
        return minOf(candidate, temporary) to REASON_INITIAL_BASELINE
    }

    if (current <= finalGoal) {
        return current to REASON_MAINTAIN_AT_FINAL_GOAL
    }

    val (evaluable, successes) = performance(metrics, kind)
    if (evaluable >= REQUIRED_EVALUABLE && successes >= REQUIRED_SUCCESSES) {
        // 완화 금지: 어떤 경우에도 현재 목표보다 커지지 않는다 (F17).
        return minOf(reduceTarget(current, finalGoal), current) to REASON_REDUCE_AFTER_SUCCESS
    }
    return current to REASON_MAINTAIN_INSUFFICIENT_SUCCESS
}

/**
 * `Analytics.kt` 의 [MissionEvaluator] 인터페이스에 이 카드에서 구현한 [evaluateMission] 을
 * 꽂아 넣는 기본 구현체. 3단계에서는 스텁(noop) 평가자를 주입했지만, 4단계에서 실제
 * 판정 알고리즘이 완성됐으므로 `analyzeWeek(request, defaultMissionEvaluator)` 로
 * 전체 파이프라인을 완결시킬 수 있다.
 */
val defaultMissionEvaluator: MissionEvaluator =
    MissionEvaluator { mission, observedMs, quality, asOfMs -> evaluateMission(mission, observedMs, quality, asOfMs) }
