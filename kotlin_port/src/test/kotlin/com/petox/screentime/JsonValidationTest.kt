package com.petox.screentime

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

/**
 * `Json.kt` 입력 검증 parity 테스트 — 6단계 감사 FAIL 해소용.
 *
 * Python `AnalysisInput.model_validate` (Pydantic `extra="forbid"`)과 정확히 같은 경계를
 * `Json.kt` 가 지키는지 확인한다. 계산 로직(`analyze()`)이 아니라 **JSON → 도메인 객체**
 * 변환 단계의 방어만 다룬다.
 *
 * 핵심 구분: "키 없음"(ValidationError) vs "키 있고 값이 null"(정상 통과).
 * null = 확인 불가, 0 = 확인된 0 — 이 둘을 섞으면 안 된다.
 */
class JsonValidationTest {

    private val json = Json { prettyPrint = true }

    private fun examplesDir(): File {
        val candidates = listOf(
            File("contracts/examples"),
            File("kotlin_port/contracts/examples"),
        )
        return candidates.firstOrNull { it.isDirectory }
            ?: error("contracts/examples 디렉터리를 찾을 수 없습니다: ${candidates.map { it.absolutePath }}")
    }

    private fun baseInput(): JsonObject {
        val text = File(examplesDir(), "complete-week.input.json").readText()
        return json.parseToJsonElement(text).jsonObject
    }

    private fun JsonObject.withField(key: String, value: JsonElement): JsonObject =
        JsonObject(toMutableMap().apply { put(key, value) })

    private fun JsonObject.withoutField(key: String): JsonObject =
        JsonObject(toMutableMap().apply { remove(key) })

    private fun render(obj: JsonObject): String = json.encodeToString(JsonElement.serializer(), obj)

    private fun parse(obj: JsonObject): AnalysisInput = AnalysisJson.parseInput(render(obj))

    // ---- 1. current_daily_target_ms 키 없음 → 거부 ----

    @Test
    fun `current_daily_target_ms 키가 없으면 거부한다`() {
        val broken = baseInput().withoutField("current_daily_target_ms")
        assertFailsWith<ValidationException> { parse(broken) }
    }

    @Test
    fun `current_daily_target_ms 가 명시적 null 이면 통과한다`() {
        val ok = baseInput().withField("current_daily_target_ms", JsonNull)
        val result = parse(ok)
        assertEquals(null, result.currentDailyTargetMs)
    }

    // ---- 2. current_night_target_ms 키 없음 → 거부 ----

    @Test
    fun `current_night_target_ms 키가 없으면 거부한다`() {
        val broken = baseInput().withoutField("current_night_target_ms")
        assertFailsWith<ValidationException> { parse(broken) }
    }

    @Test
    fun `current_night_target_ms 가 명시적 null 이면 통과한다`() {
        val ok = baseInput().withField("current_night_target_ms", JsonNull)
        val result = parse(ok)
        assertEquals(null, result.currentNightTargetMs)
    }

    // ---- 3. last_collection_attempt_ms 키 없음 → 거부 ----

    @Test
    fun `last_collection_attempt_ms 키가 없으면 거부한다`() {
        val broken = baseInput().withoutField("last_collection_attempt_ms")
        assertFailsWith<ValidationException> { parse(broken) }
    }

    @Test
    fun `last_collection_attempt_ms 가 명시적 null 이면 통과한다`() {
        val ok = baseInput().withField("last_collection_attempt_ms", JsonNull)
        val result = parse(ok)
        assertEquals(null, result.lastCollectionAttemptMs)
    }

    // ---- 4. 모르는 필드 추가 → 거부 (root, 중첩 객체 둘 다) ----

    @Test
    fun `root 에 모르는 필드를 추가하면 거부한다`() {
        val broken = baseInput().withField("unexpected_field", JsonPrimitive("x"))
        assertFailsWith<ValidationException> { parse(broken) }
    }

    @Test
    fun `profile 에 모르는 필드를 추가하면 거부한다`() {
        val base = baseInput()
        val profile = base.getValue("profile").jsonObject.withField("bogus", JsonPrimitive(1))
        val broken = base.withField("profile", profile)
        assertFailsWith<ValidationException> { parse(broken) }
    }

    @Test
    fun `aggregates 원소에 모르는 필드를 추가하면 거부한다`() {
        val base = baseInput()
        val aggregates = base.getValue("aggregates").jsonArray
        val firstAgg = aggregates[0].jsonObject.withField("bogus", JsonPrimitive(1))
        val newAggregates = JsonArray(listOf(firstAgg) + aggregates.drop(1))
        val broken = base.withField("aggregates", newAggregates)
        assertFailsWith<ValidationException> { parse(broken) }
    }

    // ---- 5. schema_version="99" → 거부 ----

    @Test
    fun `schema_version 이 2가 아니면 거부한다`() {
        val broken = baseInput().withField("schema_version", JsonPrimitive("99"))
        assertFailsWith<ValidationException> { parse(broken) }
    }

    @Test
    fun `schema_version 이 2면 통과한다`() {
        val ok = baseInput().withField("schema_version", JsonPrimitive("2"))
        val result = parse(ok)
        assertEquals("2", result.schemaVersion)
    }

    @Test
    fun `schema_version 키가 없으면 기본값 2로 통과한다`() {
        val ok = baseInput().withoutField("schema_version")
        val result = parse(ok)
        assertEquals("2", result.schemaVersion)
    }

    // ---- 추가: 중첩 객체의 required 필드 누락 ----

    @Test
    fun `profile 의 required 필드가 없으면 거부한다`() {
        val base = baseInput()
        val profile = base.getValue("profile").jsonObject.withoutField("timezone")
        val broken = base.withField("profile", profile)
        assertFailsWith<ValidationException> { parse(broken) }
    }

    @Test
    fun `aggregates 원소의 required 필드가 없으면 거부한다`() {
        val base = baseInput()
        val aggregates = base.getValue("aggregates").jsonArray
        val firstAgg = aggregates[0].jsonObject.withoutField("quality")
        val newAggregates = JsonArray(listOf(firstAgg) + aggregates.drop(1))
        val broken = base.withField("aggregates", newAggregates)
        assertFailsWith<ValidationException> { parse(broken) }
    }

    // ---- 추가: apps 키는 필수, 값만 null 가능 (unavailable 집계) ----

    @Test
    fun `apps 키 자체가 없으면 거부한다`() {
        val base = baseInput()
        val aggregates = base.getValue("aggregates").jsonArray
        val firstAgg = aggregates[0].jsonObject.withoutField("apps")
        val newAggregates = JsonArray(listOf(firstAgg) + aggregates.drop(1))
        val broken = base.withField("aggregates", newAggregates)
        assertFailsWith<ValidationException> { parse(broken) }
    }

    @Test
    fun `정상 입력은 여전히 통과한다`() {
        val result = parse(baseInput())
        assertEquals("2", result.schemaVersion)
    }

    // ---- 타입이 다른 값도 ValidationException 이다 (rules.md 5절) ----

    @Test
    fun `객체 자리에 배열이 오면 ValidationException 이다`() {
        val broken = baseInput().withField("profile", JsonArray(emptyList()))

        assertFailsWith<ValidationException> { parse(broken) }
    }

    @Test
    fun `숫자 자리에 객체가 오면 ValidationException 이다`() {
        val broken = baseInput().withField("as_of_ms", JsonObject(emptyMap()))

        assertFailsWith<ValidationException> { parse(broken) }
    }

    @Test
    fun `배열 자리에 숫자가 오면 ValidationException 이다`() {
        val broken = baseInput().withField("aggregates", JsonPrimitive(1))

        assertFailsWith<ValidationException> { parse(broken) }
    }

    @Test
    fun `최상위가 객체가 아니면 ValidationException 이다`() {
        assertFailsWith<ValidationException> { AnalysisJson.parseInput("[]") }
    }
}
