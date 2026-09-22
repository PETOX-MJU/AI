package com.petox.screentime

import java.time.LocalDate
import java.time.ZoneId
import java.time.zone.ZoneRulesException

/**
 * Python `screentime/models.py` 이식.
 *
 * 시간 단위는 정수 밀리초, 시각은 UTC epoch milliseconds다.
 * Python `int` 는 무제한이지만 JVM `Int` 는 21억에서 넘치므로 전부 `Long` 을 쓴다.
 *
 * 데이터가 없다는 이유로 0을 만들지 않는다. 확인 불가는 `null` 이고 확인된 0은 빈 배열이다.
 */

const val SCHEMA_VERSION: String = "1"
const val RULES_VERSION: String = "2026-09-10.1"

const val MINUTE_MS: Long = 60_000L

/** Python `2**53 - 1`. JSON 숫자의 안전 정수 상한과 맞춘다. */
const val MAX_DURATION_MS: Long = (1L shl 53) - 1

/** 2000-01-01T00:00:00Z — 초 단위 값을 밀리초로 잘못 보내는 실수를 잡는다. */
const val EPOCH_MIN_MS: Long = 946_684_800_000L

/** 2100-01-01T00:00:00Z */
const val EPOCH_MAX_MS: Long = 4_102_444_800_000L

/** 한 요청이 다룰 수 있는 anchor date 총 개수 상한. */
const val MAX_ANCHOR_DATES: Int = 21

/** 한 구간에 담을 수 있는 앱 개수 상한. */
const val MAX_APPS_PER_WINDOW: Int = 200

/** Pydantic `ValidationError` 에 대응한다. 검증 실패는 빈 성공 결과로 치환하지 않는다. */
class ValidationException(message: String) : IllegalArgumentException(message)

private val CLOCK_PATTERN = Regex("""^([01]\d|2[0-3]):[0-5]\d$""")

private fun requireClock(name: String, value: String): String {
    if (!CLOCK_PATTERN.matches(value)) {
        throw ValidationException("$name 는 HH:MM(00:00~23:59) 형식이어야 합니다")
    }
    return value
}

private fun requireEpochMs(name: String, value: Long): Long {
    if (value < EPOCH_MIN_MS || value > EPOCH_MAX_MS) {
        throw ValidationException("$name 가 허용 범위를 벗어났습니다")
    }
    return value
}

private fun requireDurationMs(name: String, value: Long): Long {
    if (value < 0 || value > MAX_DURATION_MS) {
        throw ValidationException("$name 가 허용 범위를 벗어났습니다")
    }
    return value
}

/** `[startMs, endMs)` 반열린 구간. */
data class Window(val startMs: Long, val endMs: Long) {
    init {
        requireEpochMs("start_ms", startMs)
        requireEpochMs("end_ms", endMs)
        if (startMs >= endMs) {
            throw ValidationException("start_ms는 end_ms보다 작아야 합니다")
        }
    }

    val durationMs: Long
        get() = endMs - startMs
}

/**
 * 사용자 설정 스냅샷. 목표 입력은 분 단위 정수다.
 *
 * Python 쪽은 Pydantic `extra="forbid"` + `frozen=True` 다. Kotlin data class 는
 * 알 수 없는 필드를 애초에 받을 수 없고, `val` 만 쓰므로 불변이다.
 */
data class Profile(
    val version: Long,
    val timezone: String,
    val targetPackages: List<String>,
    val purposes: Map<String, String> = emptyMap(),
    val weekdayBed: String,
    val weekdayWake: String,
    val weekendBed: String,
    val weekendWake: String,
    val temporaryDailyMs: Long,
    val temporaryNightMs: Long,
    val finalDailyMs: Long,
    val finalNightMs: Long,
    val effectiveFrom: LocalDate,
) {
    init {
        if (version < 0) throw ValidationException("version은 0 이상이어야 합니다")
        if (timezone.isEmpty()) throw ValidationException("timezone이 비어 있습니다")
        try {
            ZoneId.of(timezone)
        } catch (exc: ZoneRulesException) {
            throw ValidationException("알 수 없는 IANA 시간대입니다: $timezone")
        } catch (exc: java.time.DateTimeException) {
            throw ValidationException("알 수 없는 IANA 시간대입니다: $timezone")
        }

        if (targetPackages.isEmpty()) throw ValidationException("target_packages가 비어 있습니다")
        if (targetPackages.toSet().size != targetPackages.size) {
            throw ValidationException("target_packages에 중복이 있습니다")
        }
        if (targetPackages.any { it.isEmpty() }) {
            throw ValidationException("target_packages에 빈 문자열이 있습니다")
        }

        requireClock("weekday_bed", weekdayBed)
        requireClock("weekday_wake", weekdayWake)
        requireClock("weekend_bed", weekendBed)
        requireClock("weekend_wake", weekendWake)

        val goals = listOf(
            "temporary_daily_ms" to temporaryDailyMs,
            "temporary_night_ms" to temporaryNightMs,
            "final_daily_ms" to finalDailyMs,
            "final_night_ms" to finalNightMs,
        )
        for ((name, value) in goals) {
            requireDurationMs(name, value)
            if (value % MINUTE_MS != 0L) {
                throw ValidationException("$name 는 분 단위(60000ms의 배수)여야 합니다")
            }
        }

        // 임시 목표는 최종 목표보다 느슨하다. 반대면 온보딩 입력이 잘못된 것이다.
        if (temporaryDailyMs < finalDailyMs) {
            throw ValidationException("temporary_daily_ms는 final_daily_ms 이상이어야 합니다")
        }
        if (temporaryNightMs < finalNightMs) {
            throw ValidationException("temporary_night_ms는 final_night_ms 이상이어야 합니다")
        }
    }

    /** 야간 일정은 밤을 시작하는 저녁이 속한 날짜로 고른다. 토·일 저녁이 주말이다. */
    fun isWeekendAnchor(anchorDate: LocalDate): Boolean =
        anchorDate.dayOfWeek.value >= 6

    fun bedWakeFor(anchorDate: LocalDate): Pair<String, String> =
        if (isWeekendAnchor(anchorDate)) weekendBed to weekendWake
        else weekdayBed to weekdayWake
}

// ---------------------------------------------------------------------------
// Python `Literal[...]` 대응 enum.
//
// JSON 직렬화 값은 Python 과 글자 그대로 같아야 한다 (`pre_bed`, `not_applicable` 등
// snake_case 그대로). enum 이름이 아니라 [wire] 를 쓴다.
// ---------------------------------------------------------------------------

private fun <T> wireOf(values: Array<T>, raw: String, field: String, wire: (T) -> String): T =
    values.firstOrNull { wire(it) == raw }
        ?: throw ValidationException("$field 에 알 수 없는 값입니다: $raw")

enum class Quality(val wire: String) {
    COMPLETE("complete"),
    PARTIAL("partial"),
    UNAVAILABLE("unavailable");

    override fun toString(): String = wire

    companion object {
        fun fromWire(raw: String): Quality = wireOf(entries.toTypedArray(), raw, "quality") { it.wire }
    }
}

enum class WindowKind(val wire: String) {
    DAILY("daily"),
    PRE_BED("pre_bed"),
    AFTER_BED("after_bed");

    override fun toString(): String = wire

    companion object {
        fun fromWire(raw: String): WindowKind = wireOf(entries.toTypedArray(), raw, "kind") { it.wire }
    }
}

enum class MissionKind(val wire: String) {
    DAILY("daily"),
    NIGHT("night");

    override fun toString(): String = wire

    companion object {
        fun fromWire(raw: String): MissionKind = wireOf(entries.toTypedArray(), raw, "kind") { it.wire }
    }
}

enum class MissionStatus(val wire: String) {
    IN_PROGRESS("in_progress"),
    SUCCEEDED("succeeded"),
    FAILED("failed"),
    UNKNOWN("unknown"),
    NOT_APPLICABLE("not_applicable");

    override fun toString(): String = wire

    companion object {
        fun fromWire(raw: String): MissionStatus = wireOf(entries.toTypedArray(), raw, "status") { it.wire }
    }
}

enum class WeekStatus(val wire: String) {
    IN_PROGRESS("in_progress"),
    AWAITING_DATA("awaiting_data"),
    READY("ready"),
    INSUFFICIENT_DATA("insufficient_data");

    override fun toString(): String = wire

    companion object {
        fun fromWire(raw: String): WeekStatus = wireOf(entries.toTypedArray(), raw, "week_status") { it.wire }
    }
}

// ---------------------------------------------------------------------------
// 입력 모델
// ---------------------------------------------------------------------------

/** 한 앱의 사용 시간. */
data class AppDuration(val packageName: String, val durationMs: Long) {
    init {
        if (packageName.isEmpty()) throw ValidationException("package_name이 비어 있습니다")
        requireDurationMs("duration_ms", durationMs)
    }
}

/** aggregates 중복 판정 키. Python `WindowAggregate.key` 튜플에 대응한다. */
data class AggregateKey(
    val anchorDate: LocalDate,
    val kind: WindowKind,
    val profileVersion: Long,
    val measurementVersion: String,
)

/** FE가 정규화한 한 구간의 앱별 집계. */
data class WindowAggregate(
    val anchorDate: LocalDate,
    val kind: WindowKind,
    val startMs: Long,
    val endMs: Long,
    val observedUntilMs: Long,
    val quality: Quality,
    val reasonCodes: List<String> = emptyList(),
    val profileVersion: Long,
    /** `null` 은 "확인 불가", 빈 배열은 "확인된 0". 둘을 섞으면 안 된다. */
    val apps: List<AppDuration>?,
    val measurementVersion: String,
) {
    init {
        requireEpochMs("start_ms", startMs)
        requireEpochMs("end_ms", endMs)
        requireEpochMs("observed_until_ms", observedUntilMs)
        if (profileVersion < 0) throw ValidationException("profile_version은 0 이상이어야 합니다")
        if (measurementVersion.isEmpty()) throw ValidationException("measurement_version이 비어 있습니다")

        if (startMs >= endMs) throw ValidationException("start_ms는 end_ms보다 작아야 합니다")
        if (observedUntilMs < startMs || observedUntilMs > endMs) {
            throw ValidationException("observed_until_ms는 [start_ms, end_ms] 안에 있어야 합니다")
        }

        if (quality == Quality.UNAVAILABLE) {
            if (apps != null) throw ValidationException("unavailable 집계의 apps는 null이어야 합니다")
        } else if (apps == null) {
            throw ValidationException("$quality 집계의 apps는 배열이어야 합니다 (빈 배열이 확인된 0)")
        }

        if (quality == Quality.COMPLETE && observedUntilMs != endMs) {
            throw ValidationException("complete 집계는 observed_until_ms == end_ms 여야 합니다")
        }

        if (apps != null) {
            if (apps.size > MAX_APPS_PER_WINDOW) {
                throw ValidationException("한 구간의 앱은 ${MAX_APPS_PER_WINDOW}개를 넘을 수 없습니다")
            }
            val names = apps.map { it.packageName }
            if (names.toSet().size != names.size) {
                throw ValidationException("같은 집계 안에 package_name 중복이 있습니다")
            }
            val span = endMs - startMs
            // 개별 앱은 구간 길이를 넘을 수 없다. 멀티윈도우 때문에 앱들의 합계는 넘을 수 있다.
            for (app in apps) {
                if (app.durationMs > span) {
                    throw ValidationException("${app.packageName}의 사용 시간이 구간 길이를 초과합니다")
                }
            }
        }
    }

    val key: AggregateKey
        get() = AggregateKey(anchorDate, kind, profileVersion, measurementVersion)

    /**
     * [packages] 가 null이면 전체 앱 합계. 집계 불가(`apps == null`)면 null.
     *
     * 빈 배열은 "확인된 0"이라 `0L` 을 돌려준다. null 로 뭉개면 안 된다.
     */
    fun totalMs(packages: Set<String>? = null): Long? {
        val list = apps ?: return null
        return list
            .filter { packages == null || it.packageName in packages }
            .sumOf { it.durationMs }
    }
}

/** 실제로 발급된 미션 스냅샷. 현재 설정으로 과거를 재평가하지 않는다. */
data class Mission(
    val id: String,
    val anchorDate: LocalDate,
    val kind: MissionKind,
    val targetMs: Long,
    val profileVersion: Long,
    val acceptedAtMs: Long,
    val windowStartMs: Long,
    val windowEndMs: Long,
) {
    init {
        if (id.isEmpty()) throw ValidationException("mission.id가 비어 있습니다")
        requireDurationMs("target_ms", targetMs)
        if (profileVersion < 0) throw ValidationException("profile_version은 0 이상이어야 합니다")
        requireEpochMs("accepted_at_ms", acceptedAtMs)
        requireEpochMs("window_start_ms", windowStartMs)
        requireEpochMs("window_end_ms", windowEndMs)
        if (windowStartMs >= windowEndMs) {
            throw ValidationException("window_start_ms는 window_end_ms보다 작아야 합니다")
        }
    }
}

/** 추천이며 활성 미션이 아니다. 수락·저장은 BE 책임이다. */
data class Proposal(
    val kind: MissionKind,
    val targetMs: Long?,
    val reasonCode: String,
    val basisWeek: LocalDate,
    val profileVersion: Long,
    val rulesVersion: String,
) {
    init {
        if (targetMs != null) requireDurationMs("target_ms", targetMs)
        if (profileVersion < 0) throw ValidationException("profile_version은 0 이상이어야 합니다")
    }
}

data class MissionResult(
    val missionId: String,
    val status: MissionStatus,
    val observedMs: Long?,
    val evaluatedAtMs: Long,
) {
    init {
        if (observedMs != null) requireDurationMs("observed_ms", observedMs)
        requireEpochMs("evaluated_at_ms", evaluatedAtMs)
    }
}

// ---------------------------------------------------------------------------
// 출력 모델 — null 은 전부 "확인 불가"다
// ---------------------------------------------------------------------------

data class DayMetrics(
    val date: LocalDate,
    val dailyQuality: Quality?,
    val preBedQuality: Quality?,
    val afterBedQuality: Quality?,
    val allAppsMs: Long?,
    val selectedMs: Long?,
    val preBedMs: Long?,
    val afterBedMs: Long?,
)

data class AppMetrics(
    val packageName: String,
    val isTarget: Boolean,
    val totalMs: Long?,
    val sharePct: Double?,
    val nightTotalMs: Long?,
    val nightSharePct: Double?,
    val deltaMs: Long?,
    val deltaPct: Double?,
)

data class Comparison(
    val comparable: Boolean,
    val reason: String?,
    val selectedDeltaMs: Long?,
    val selectedDeltaPct: Double?,
    val allAppsDeltaMs: Long?,
)

data class WeeklyMetrics(
    val validDays: Long,
    val validNights: Long,
    val allAppsTotalMs: Long?,
    val selectedTotalMs: Long?,
    val selectedDailyMeanMs: Double?,
    val selectedNightMeanMs: Double?,
    val preBedTotalMs: Long?,
    val afterBedTotalMs: Long?,
    val dailySuccessCount: Long,
    val dailyEvaluableCount: Long,
    val nightSuccessCount: Long,
    val nightEvaluableCount: Long,
    val perDay: List<DayMetrics>,
    val previousPerDay: List<DayMetrics>,
    val perApp: List<AppMetrics>,
    val comparison: Comparison,
) {
    init {
        val counts = listOf(
            "valid_days" to validDays,
            "valid_nights" to validNights,
            "daily_success_count" to dailySuccessCount,
            "daily_evaluable_count" to dailyEvaluableCount,
            "night_success_count" to nightSuccessCount,
            "night_evaluable_count" to nightEvaluableCount,
        )
        for ((name, value) in counts) {
            if (value < 0) throw ValidationException("$name 는 0 이상이어야 합니다")
        }
    }
}

/**
 * 한 줄 요약 하나.
 *
 * [source] 는 항상 `"template"` 고정이다. 생성형 AI를 쓰지 않는다는 계약이다.
 */
data class Insight(
    val code: String,
    val evidence: Map<String, Any?>,
    val text: String,
) {
    val source: String = "template"
}

data class AnalysisInput(
    val asOfMs: Long,
    val lastCollectionAttemptMs: Long?,
    val weekStart: LocalDate,
    val profile: Profile,
    val aggregates: List<WindowAggregate>,
    val missions: List<Mission>,
    val currentDailyTargetMs: Long?,
    val currentNightTargetMs: Long?,
) {
    val schemaVersion: String = SCHEMA_VERSION

    init {
        requireEpochMs("as_of_ms", asOfMs)
        if (lastCollectionAttemptMs != null) {
            requireEpochMs("last_collection_attempt_ms", lastCollectionAttemptMs)
        }
        if (currentDailyTargetMs != null) requireDurationMs("current_daily_target_ms", currentDailyTargetMs)
        if (currentNightTargetMs != null) requireDurationMs("current_night_target_ms", currentNightTargetMs)

        if (weekStart.dayOfWeek.value != 1) {
            throw ValidationException("week_start는 월요일이어야 합니다")
        }

        val keys = aggregates.map { it.key }
        if (keys.toSet().size != keys.size) {
            throw ValidationException(
                "aggregates에 (anchor_date, kind, profile_version, measurement_version) 중복이 있습니다"
            )
        }

        val anchors = aggregates.map { it.anchorDate }.toSet() + missions.map { it.anchorDate }.toSet()
        if (anchors.size > MAX_ANCHOR_DATES) {
            throw ValidationException("anchor date는 최대 ${MAX_ANCHOR_DATES}개까지 허용합니다")
        }

        val versions = aggregates.map { it.measurementVersion }.toSet()
        if (versions.size > 1) {
            throw ValidationException("한 요청의 measurement_version은 하나여야 합니다")
        }

        for (agg in aggregates) {
            if (agg.profileVersion != profile.version) {
                throw ValidationException("집계 profile_version(${agg.profileVersion})이 프로필과 다릅니다")
            }
            // complete는 이미 끝난 구간에만 붙일 수 있다. 진행 중 구간의 complete를 막는다.
            if (agg.quality == Quality.COMPLETE && agg.endMs > asOfMs) {
                throw ValidationException("아직 끝나지 않은 구간을 complete로 표시할 수 없습니다")
            }

            // 집계 경계가 프로필로 계산한 구간과 같아야 한다. 이걸 검사하지 않으면
            // 1분짜리 구간에 빈 앱 목록을 넣어 하루 전체를 '확인된 0'으로 만들 수 있다.
            val expected = if (agg.kind == WindowKind.DAILY) {
                dailyWindow(agg.anchorDate, profile)
            } else {
                val (pre, post) = nightWindows(agg.anchorDate, profile)
                if (agg.kind == WindowKind.PRE_BED) pre else post
            }
            if (agg.startMs != expected.startMs || agg.endMs != expected.endMs) {
                throw ValidationException(
                    "${agg.anchorDate} ${agg.kind} 구간이 프로필로 계산한 경계와 다릅니다: " +
                        "입력 [${agg.startMs}, ${agg.endMs}) / 기대 [${expected.startMs}, ${expected.endMs})"
                )
            }
        }

        val missionIds = missions.map { it.id }
        if (missionIds.toSet().size != missionIds.size) {
            throw ValidationException("mission.id 중복이 있습니다")
        }
        val missionKeys = missions.map { it.anchorDate to it.kind }
        if (missionKeys.toSet().size != missionKeys.size) {
            throw ValidationException("(anchor_date, kind)가 같은 미션이 둘 이상입니다")
        }
        for (mission in missions) {
            if (mission.profileVersion != profile.version) {
                throw ValidationException("미션 profile_version(${mission.profileVersion})이 프로필과 다릅니다")
            }
        }
    }

    /** aggregates 의 measurement_version. 비어 있으면 `"unknown"`. */
    val measurementVersion: String
        get() = aggregates.firstOrNull()?.measurementVersion ?: "unknown"

    val targetPackages: Set<String>
        get() = profile.targetPackages.toSet()
}

data class AnalysisOutput(
    val weekStatus: WeekStatus,
    val metrics: WeeklyMetrics,
    val missionResults: List<MissionResult>,
    val proposals: List<Proposal>,
    val insights: List<Insight>,
    val rulesVersion: String,
) {
    val schemaVersion: String = SCHEMA_VERSION
}
