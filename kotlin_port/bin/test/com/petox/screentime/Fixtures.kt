package com.petox.screentime

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long

/**
 * `contracts/fixtures.json` 을 **직접 읽는다.** 값을 테스트에 상수로 베껴 두면
 * JSON 만 바뀌어도 테스트가 전부 통과해 계약이 조용히 갈라진다.
 */
object Fixtures {
    private val dir: File = listOf(File("contracts"), File("kotlin_port/contracts"))
        .firstOrNull { it.isDirectory }
        ?: error("contracts 디렉터리를 찾을 수 없습니다: ${File("contracts").absolutePath}")

    private val root: JsonObject =
        Json.parseToJsonElement(File(dir, "fixtures.json").readText()).jsonObject

    /** 비어 있는 블록은 테스트를 통과시키는 게 아니라 실패시킨다. */
    fun cases(block: String): List<JsonObject> {
        val cases = (root[block] ?: error("fixtures.json 에 $block 블록이 없습니다"))
            .jsonArray.map { it.jsonObject }
        check(cases.isNotEmpty()) { "fixtures.json 의 $block 블록이 비어 있습니다" }
        return cases
    }
}

fun JsonObject.id(): String = this["id"]?.jsonPrimitive?.content ?: "(id 없음)"

fun JsonObject.str(key: String): String =
    (this[key] ?: error("fixture 에 $key 가 없습니다")).jsonPrimitive.content

fun JsonObject.long(key: String): Long =
    (this[key] ?: error("fixture 에 $key 가 없습니다")).jsonPrimitive.long

fun JsonObject.longOrNull(key: String): Long? =
    this[key]?.jsonPrimitive?.takeIf { it.content != "null" }?.long

fun JsonObject.bool(key: String, default: Boolean = false): Boolean =
    this[key]?.jsonPrimitive?.content?.toBoolean() ?: default

fun JsonObject.obj(key: String): JsonObject =
    (this[key] ?: error("fixture 에 $key 가 없습니다")).jsonObject
