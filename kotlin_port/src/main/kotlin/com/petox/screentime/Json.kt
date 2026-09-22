package com.petox.screentime

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.long
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.putJsonObject
import java.time.LocalDate

/**
 * `contracts/examples/` 의 `*.json` 파일과 대조하기 위한 최소 JSON 계층.
 *
 * kotlinx-serialization의 `@Serializable` 애노테이션을 [Models.kt] 도메인 클래스에 직접
 * 붙이지 않는다. 필드명이 camelCase인 Kotlin 클래스와 snake_case인 계약을 자동 매핑에
 * 맡기면 null과 필드 부재("확인 불가" vs "확인된 0")의 구분이 매핑 규칙 뒤로 숨는다.
 * 여기서 명시적으로 변환해 그 경계를 코드로 드러낸다.
 */
object AnalysisJson {
    private val json = Json { prettyPrint = true }

    fun parseInput(text: String): AnalysisInput = inputFromJson(json.parseToJsonElement(text).jsonObject)

    fun encodeOutput(output: AnalysisOutput): String {
        val element = outputToJson(output)
        return json.encodeToString(JsonElement.serializer(), element)
    }

    fun outputToJson(output: AnalysisOutput): JsonElement = buildJsonObject {
        put("schema_version", output.schemaVersion)
        put("week_status", output.weekStatus.wire)
        put("metrics", metricsToJson(output.metrics))
        putJsonArray("mission_results") { output.missionResults.forEach { add(missionResultToJson(it)) } }
        putJsonArray("proposals") { output.proposals.forEach { add(proposalToJson(it)) } }
        putJsonArray("insights") { output.insights.forEach { add(insightToJson(it)) } }
        put("rules_version", output.rulesVersion)
    }
}

// ---------------------------------------------------------------------------
// JsonElement 읽기 헬퍼.
//
// "키 자체가 없음"과 "키는 있고 값이 명시적 null"을 구분한다 — Python Pydantic의
// required-nullable 필드(`last_collection_attempt_ms` 등)와 정확히 대응해야 한다.
// 키가 없으면 예외(Python `ValidationError` 대응), 값이 null이면 그대로 null을 돌려준다.
// ---------------------------------------------------------------------------

private fun JsonObject.requireElement(key: String): JsonElement =
    this[key] ?: throw ValidationException("JSON 필드가 없습니다: $key")

/** 키가 있으면 그 값(없으면 null)을 돌려준다. optional 필드(기본값이 있는 필드)용. */
private fun JsonObject.optionalElement(key: String): JsonElement? = this[key]

private fun JsonObject.requireLong(key: String): Long = requirePrimitive(key).long
private fun JsonObject.requireLongOrNull(key: String): Long? {
    val element = requireElement(key)
    return if (element is JsonNull) null else (element as JsonPrimitive).long
}

private fun JsonObject.requireString(key: String): String = requirePrimitive(key).content
private fun JsonObject.optionalString(key: String): String? {
    val element = optionalElement(key) ?: return null
    if (element is JsonNull) throw ValidationException("$key 는 null일 수 없습니다")
    return (element as JsonPrimitive).content
}

private fun JsonObject.requireBoolean(key: String): Boolean = requirePrimitive(key).boolean
private fun JsonObject.requireDate(key: String): LocalDate = LocalDate.parse(requireString(key))

private fun JsonObject.requirePrimitive(key: String): JsonPrimitive = requireElement(key) as JsonPrimitive

private fun JsonObject.requireArray(key: String): JsonArray = requireElement(key) as JsonArray

/** 키는 반드시 있어야 하지만 값은 null일 수 있다 (`apps: list[AppDuration] | None`). */
private fun JsonObject.requireArrayOrNull(key: String): JsonArray? {
    val element = requireElement(key)
    return if (element is JsonNull) null else element as JsonArray
}

/** 키가 없으면 null(호출부에서 기본값 적용). 있는데 값이 null이면 타입 오류로 거부한다. */
private fun JsonObject.optionalArray(key: String): JsonArray? {
    val element = optionalElement(key) ?: return null
    if (element is JsonNull) throw ValidationException("$key 는 null일 수 없습니다")
    return element as JsonArray
}

private fun JsonObject.requireObject(key: String): JsonObject = requireElement(key) as JsonObject

/** 키가 없으면 null(호출부에서 기본값 적용). 있는데 값이 null이면 타입 오류로 거부한다. */
private fun JsonObject.optionalObject(key: String): JsonObject? {
    val element = optionalElement(key) ?: return null
    if (element is JsonNull) throw ValidationException("$key 는 null일 수 없습니다")
    return element as JsonObject
}

/**
 * Python `model_config = ConfigDict(extra="forbid")` 대응. 오탈자 필드명을 조용히
 * 삼키면 BE 연동에서 원인을 찾기 어렵다 — 모르는 키가 있으면 즉시 거부한다.
 */
private fun JsonObject.rejectUnknownKeys(allowed: Set<String>, modelName: String) {
    val unknown = keys - allowed
    if (unknown.isNotEmpty()) {
        throw ValidationException("$modelName 에 알 수 없는 필드가 있습니다: ${unknown.sorted()}")
    }
}

private val PROFILE_KEYS = setOf(
    "version", "timezone", "target_packages", "purposes",
    "weekday_bed", "weekday_wake", "weekend_bed", "weekend_wake",
    "temporary_daily_ms", "temporary_night_ms", "final_daily_ms", "final_night_ms",
    "effective_from",
)
private val APP_DURATION_KEYS = setOf("package_name", "duration_ms")
private val WINDOW_AGGREGATE_KEYS = setOf(
    "anchor_date", "kind", "start_ms", "end_ms", "observed_until_ms", "quality",
    "reason_codes", "profile_version", "apps", "measurement_version",
)
private val MISSION_KEYS = setOf(
    "id", "anchor_date", "kind", "target_ms", "profile_version",
    "accepted_at_ms", "window_start_ms", "window_end_ms",
)
private val ANALYSIS_INPUT_KEYS = setOf(
    "schema_version", "as_of_ms", "last_collection_attempt_ms", "week_start", "profile",
    "aggregates", "missions", "current_daily_target_ms", "current_night_target_ms",
)

// ---------------------------------------------------------------------------
// 입력 파싱 — Python `AnalysisInput.model_validate` 대응.
// ---------------------------------------------------------------------------

private fun profileFromJson(obj: JsonObject): Profile {
    obj.rejectUnknownKeys(PROFILE_KEYS, "profile")
    return Profile(
        version = obj.requireLong("version"),
        timezone = obj.requireString("timezone"),
        targetPackages = obj.requireArray("target_packages").map { (it as JsonPrimitive).content },
        purposes = obj.optionalObject("purposes")?.mapValues { (_, v) -> (v as JsonPrimitive).content }
            ?: emptyMap(),
        weekdayBed = obj.requireString("weekday_bed"),
        weekdayWake = obj.requireString("weekday_wake"),
        weekendBed = obj.requireString("weekend_bed"),
        weekendWake = obj.requireString("weekend_wake"),
        temporaryDailyMs = obj.requireLong("temporary_daily_ms"),
        temporaryNightMs = obj.requireLong("temporary_night_ms"),
        finalDailyMs = obj.requireLong("final_daily_ms"),
        finalNightMs = obj.requireLong("final_night_ms"),
        effectiveFrom = obj.requireDate("effective_from"),
    )
}

private fun appDurationFromJson(obj: JsonObject): AppDuration {
    obj.rejectUnknownKeys(APP_DURATION_KEYS, "app_duration")
    return AppDuration(
        packageName = obj.requireString("package_name"),
        durationMs = obj.requireLong("duration_ms"),
    )
}

private fun windowAggregateFromJson(obj: JsonObject): WindowAggregate {
    obj.rejectUnknownKeys(WINDOW_AGGREGATE_KEYS, "window_aggregate")
    return WindowAggregate(
        anchorDate = obj.requireDate("anchor_date"),
        kind = WindowKind.fromWire(obj.requireString("kind")),
        startMs = obj.requireLong("start_ms"),
        endMs = obj.requireLong("end_ms"),
        observedUntilMs = obj.requireLong("observed_until_ms"),
        quality = Quality.fromWire(obj.requireString("quality")),
        reasonCodes = obj.optionalArray("reason_codes")?.map { (it as JsonPrimitive).content } ?: emptyList(),
        profileVersion = obj.requireLong("profile_version"),
        // apps == null 은 "확인 불가", 빈 배열은 "확인된 0". 키는 필수이고 값만 null일 수 있다.
        apps = obj.requireArrayOrNull("apps")?.map { appDurationFromJson(it as JsonObject) },
        measurementVersion = obj.requireString("measurement_version"),
    )
}

private fun missionFromJson(obj: JsonObject): Mission {
    obj.rejectUnknownKeys(MISSION_KEYS, "mission")
    return Mission(
        id = obj.requireString("id"),
        anchorDate = obj.requireDate("anchor_date"),
        kind = MissionKind.fromWire(obj.requireString("kind")),
        targetMs = obj.requireLong("target_ms"),
        profileVersion = obj.requireLong("profile_version"),
        acceptedAtMs = obj.requireLong("accepted_at_ms"),
        windowStartMs = obj.requireLong("window_start_ms"),
        windowEndMs = obj.requireLong("window_end_ms"),
    )
}

private fun inputFromJson(obj: JsonObject): AnalysisInput {
    obj.rejectUnknownKeys(ANALYSIS_INPUT_KEYS, "analysis_input")

    // Python `Literal["1"]` 대응. schema_version 은 기본값이 있는 optional 필드지만
    // 값이 오면 반드시 "1" 이어야 한다.
    val schemaVersion = obj.optionalString("schema_version") ?: SCHEMA_VERSION
    if (schemaVersion != SCHEMA_VERSION) {
        throw ValidationException("schema_version 은 \"$SCHEMA_VERSION\" 이어야 합니다: $schemaVersion")
    }

    return AnalysisInput(
        asOfMs = obj.requireLong("as_of_ms"),
        lastCollectionAttemptMs = obj.requireLongOrNull("last_collection_attempt_ms"),
        weekStart = obj.requireDate("week_start"),
        profile = profileFromJson(obj.requireObject("profile")),
        aggregates = obj.requireArray("aggregates").map { windowAggregateFromJson(it as JsonObject) },
        missions = obj.requireArray("missions").map { missionFromJson(it as JsonObject) },
        currentDailyTargetMs = obj.requireLongOrNull("current_daily_target_ms"),
        currentNightTargetMs = obj.requireLongOrNull("current_night_target_ms"),
    )
}

// ---------------------------------------------------------------------------
// 출력 직렬화 — Python `AnalysisOutput.model_dump(mode="json")` 대응.
// ---------------------------------------------------------------------------

private fun JsonObjectBuilderScope.putLongOrNull(key: String, value: Long?) {
    put(key, value?.let { JsonPrimitive(it) } ?: JsonNull)
}

private fun JsonObjectBuilderScope.putDoubleOrNull(key: String, value: Double?) {
    put(key, value?.let { JsonPrimitive(it) } ?: JsonNull)
}

private fun JsonObjectBuilderScope.putStringOrNull(key: String, value: String?) {
    put(key, value?.let { JsonPrimitive(it) } ?: JsonNull)
}

private typealias JsonObjectBuilderScope = kotlinx.serialization.json.JsonObjectBuilder

private fun dayMetricsToJson(day: DayMetrics): JsonElement = buildJsonObject {
    put("date", day.date.toString())
    putStringOrNull("daily_quality", day.dailyQuality?.wire)
    putStringOrNull("pre_bed_quality", day.preBedQuality?.wire)
    putStringOrNull("after_bed_quality", day.afterBedQuality?.wire)
    putLongOrNull("all_apps_ms", day.allAppsMs)
    putLongOrNull("selected_ms", day.selectedMs)
    putLongOrNull("pre_bed_ms", day.preBedMs)
    putLongOrNull("after_bed_ms", day.afterBedMs)
}

private fun appMetricsToJson(app: AppMetrics): JsonElement = buildJsonObject {
    put("package_name", app.packageName)
    put("is_target", app.isTarget)
    putLongOrNull("total_ms", app.totalMs)
    putDoubleOrNull("share_pct", app.sharePct)
    putLongOrNull("night_total_ms", app.nightTotalMs)
    putDoubleOrNull("night_share_pct", app.nightSharePct)
    putLongOrNull("delta_ms", app.deltaMs)
    putDoubleOrNull("delta_pct", app.deltaPct)
}

private fun comparisonToJson(comparison: Comparison): JsonElement = buildJsonObject {
    put("comparable", comparison.comparable)
    putStringOrNull("reason", comparison.reason)
    putLongOrNull("selected_delta_ms", comparison.selectedDeltaMs)
    putDoubleOrNull("selected_delta_pct", comparison.selectedDeltaPct)
    putLongOrNull("all_apps_delta_ms", comparison.allAppsDeltaMs)
}

private fun metricsToJson(metrics: WeeklyMetrics): JsonElement = buildJsonObject {
    put("valid_days", metrics.validDays)
    put("valid_nights", metrics.validNights)
    putLongOrNull("all_apps_total_ms", metrics.allAppsTotalMs)
    putLongOrNull("selected_total_ms", metrics.selectedTotalMs)
    putDoubleOrNull("selected_daily_mean_ms", metrics.selectedDailyMeanMs)
    putDoubleOrNull("selected_night_mean_ms", metrics.selectedNightMeanMs)
    putLongOrNull("pre_bed_total_ms", metrics.preBedTotalMs)
    putLongOrNull("after_bed_total_ms", metrics.afterBedTotalMs)
    put("daily_success_count", metrics.dailySuccessCount)
    put("daily_evaluable_count", metrics.dailyEvaluableCount)
    put("night_success_count", metrics.nightSuccessCount)
    put("night_evaluable_count", metrics.nightEvaluableCount)
    putJsonArray("per_day") { metrics.perDay.forEach { add(dayMetricsToJson(it)) } }
    putJsonArray("previous_per_day") { metrics.previousPerDay.forEach { add(dayMetricsToJson(it)) } }
    putJsonArray("per_app") { metrics.perApp.forEach { add(appMetricsToJson(it)) } }
    put("comparison", comparisonToJson(metrics.comparison))
}

private fun missionResultToJson(result: MissionResult): JsonElement = buildJsonObject {
    put("mission_id", result.missionId)
    put("status", result.status.wire)
    putLongOrNull("observed_ms", result.observedMs)
    put("evaluated_at_ms", result.evaluatedAtMs)
}

private fun proposalToJson(proposal: Proposal): JsonElement = buildJsonObject {
    put("kind", proposal.kind.wire)
    putLongOrNull("target_ms", proposal.targetMs)
    put("reason_code", proposal.reasonCode)
    put("basis_week", proposal.basisWeek.toString())
    put("profile_version", proposal.profileVersion)
    put("rules_version", proposal.rulesVersion)
}

/** [Insight.evidence] 는 `Map<String, Any?>` 다. 여기서만 값 타입을 분기해 JSON으로 내린다. */
private fun evidenceValueToJson(value: Any?): JsonElement = when (value) {
    null -> JsonNull
    is Long -> JsonPrimitive(value)
    is Int -> JsonPrimitive(value.toLong())
    is Double -> JsonPrimitive(value)
    is Boolean -> JsonPrimitive(value)
    is String -> JsonPrimitive(value)
    else -> throw IllegalArgumentException("evidence 값 타입을 직렬화할 수 없습니다: ${value::class}")
}

private fun insightToJson(insight: Insight): JsonElement = buildJsonObject {
    put("code", insight.code)
    putJsonObject("evidence") { insight.evidence.forEach { (k, v) -> put(k, evidenceValueToJson(v)) } }
    put("text", insight.text)
    put("source", insight.source)
}
