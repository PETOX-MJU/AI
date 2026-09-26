package com.petox.screentime

import kotlinx.serialization.json.Json
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * 6단계(`pipeline.py` 이식) 본체 — 전체 예제 parity.
 *
 * `contracts/examples` 디렉터리의 `*.input.json` 을 Kotlin [analyze] 에 넣고 `*.output.json` 과
 * **파싱 후 구조 비교**한다. 문자열 전체 비교보다 이게 낫다:
 * - 필드 순서가 달라도 의미는 같다
 * - `Double` 은 표현이 다를 수 있다 (`12.35` vs `12.350000000000001`)
 *
 * 값이 다르면 어느 필드에서 갈리는지 출력한다. "다르다"만으로는 디버깅이 안 된다.
 */
class PipelineParityTest {

    private val json = Json { prettyPrint = true }

    private fun examplesDir(): File {
        // 테스트는 kotlin_port/ 에서 실행된다. 계약 문서 경로는 형제 디렉터리다.
        val candidates = listOf(
            File("contracts/examples"),
            File("kotlin_port/contracts/examples"),
        )
        return candidates.firstOrNull { it.isDirectory }
            ?: error("contracts/examples 디렉터리를 찾을 수 없습니다: ${candidates.map { it.absolutePath }}")
    }

    /** 두 JsonElement 를 재귀적으로 비교해 첫 번째 불일치 경로를 사람이 읽을 문자열로 만든다. */
    private fun diff(path: String, actual: kotlinx.serialization.json.JsonElement, expected: kotlinx.serialization.json.JsonElement): String? {
        if (actual == expected) return null
        if (actual is kotlinx.serialization.json.JsonObject && expected is kotlinx.serialization.json.JsonObject) {
            val keys = actual.keys + expected.keys
            for (key in keys) {
                val a = actual[key]
                val e = expected[key]
                if (a == null) return "$path.$key: actual에 필드 없음 (expected=$e)"
                if (e == null) return "$path.$key: expected에 필드 없음 (actual=$a)"
                val sub = diff("$path.$key", a, e)
                if (sub != null) return sub
            }
            return null
        }
        if (actual is kotlinx.serialization.json.JsonArray && expected is kotlinx.serialization.json.JsonArray) {
            if (actual.size != expected.size) {
                return "$path: 배열 길이 다름 (actual=${actual.size}, expected=${expected.size})"
            }
            for (i in actual.indices) {
                val sub = diff("$path[$i]", actual[i], expected[i])
                if (sub != null) return sub
            }
            return null
        }
        return "$path: 값 다름 (actual=$actual, expected=$expected)"
    }

    private fun runCase(inputName: String, outputName: String) {
        val dir = examplesDir()
        val inputText = File(dir, inputName).readText()
        val expectedText = File(dir, outputName).readText()

        val request = AnalysisJson.parseInput(inputText)
        val actualOutput = analyze(request)
        val actualElement = AnalysisJson.outputToJson(actualOutput)
        val expectedElement = json.parseToJsonElement(expectedText)

        val mismatch = diff("root", actualElement, expectedElement)
        assertTrue(mismatch == null, "출력이 계약과 다릅니다 — $mismatch")
    }

    @Test
    fun `complete-week 예제는 Kotlin analyze 결과와 구조적으로 일치한다`() {
        runCase("complete-week.input.json", "complete-week.output.json")
    }

    @Test
    fun `insufficient-data 예제는 Kotlin analyze 결과와 구조적으로 일치한다`() {
        runCase("insufficient-data.input.json", "insufficient-data.output.json")
    }

    @Test
    fun `analyze 는 결정론적이다 -- 같은 입력 두 번 호출은 같은 출력`() {
        val dir = examplesDir()
        val request = AnalysisJson.parseInput(File(dir, "complete-week.input.json").readText())
        val first = AnalysisJson.outputToJson(analyze(request))
        val second = AnalysisJson.outputToJson(analyze(request))
        assertEquals(first, second)
    }

    @Test
    fun `rules_version 은 계약된 문자열이다`() {
        val dir = examplesDir()
        val request = AnalysisJson.parseInput(File(dir, "complete-week.input.json").readText())
        assertEquals("2026-09-10.1", analyze(request).rulesVersion)
    }

    @Test
    fun `schema_version 은 2 이다`() {
        val dir = examplesDir()
        val request = AnalysisJson.parseInput(File(dir, "complete-week.input.json").readText())
        assertEquals("2", analyze(request).schemaVersion)
    }
}
