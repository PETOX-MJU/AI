# Kotlin 이식본

`screentime_analysis/` Python 패키지의 **Kotlin 이식 결과물**이다.
FE 안드로이드 앱에 그대로 복사해 넣는 것을 전제로 작성한다.

계약과 함정은 [`../screentime_analysis/contracts/kotlin-port.md`](../screentime_analysis/contracts/kotlin-port.md) 를 먼저 읽어라.

## 왜 Gradle Android 프로젝트가 아닌가

**분석 로직은 Android API에 의존하지 않는다.** 순수 Kotlin/JVM이라
Android SDK 없이 테스트할 수 있다. `UsageStatsManager` 수집과 Room 저장은
FE 앱의 책임이고 이 디렉터리 범위가 아니다.

덕분에 `./gradlew test` 로 parity를 즉시 검증할 수 있다.

## 구조

`→` 표시는 아직 만들지 않은 파일이다.

```
kotlin_port/
├─ build.gradle.kts
├─ settings.gradle.kts
├─ gradlew, gradlew.bat, gradle/wrapper/
└─ src/
   ├─ main/kotlin/com/petox/screentime/
   │  ├─ Models.kt        Python models.py — 전체
   │  ├─ Windows.kt       Python windows.py — 전체
   │  ├─ Analytics.kt     Python analytics.py — 집계·평균·비교 (MissionEvaluator 인터페이스로 missions.py 주입)
   │  ├─ Missions.kt      Python missions.py — 목표 제안·미션 판정
   │  ├─ Narratives.kt    Python narratives.py — 근거 기반 한국어 설명 템플릿
   │  ├─ Pipeline.kt      Python pipeline.py — analyze() 진입점 (분석→판정→제안→인사이트 조립)
   │  └─ Json.kt          contracts/examples/*.json 대조용 수동 JSON 매핑 (kotlinx-serialization JsonElement)
   └─ test/kotlin/com/petox/screentime/
      ├─ WindowsParityTest.kt    fixtures.json night_windows·daily_window_dst
      ├─ ModelsValidationTest.kt models.py 검증 규칙·경계 위조 방지
      ├─ AnalyticsTest.kt        analytics.py parity — _pct banker's rounding, null 전파, week_status, complete-week 예제 대조
      ├─ MissionsTest.kt         missions.py parity — fixtures.json reduce_target·mission_judgement 전 케이스
      ├─ NarrativesTest.kt       narratives.py parity — rotation_seed toordinal 오프셋, minutes() half-to-even, 문장 회전 결정론·고정 절 불변, INSUFFICIENT_DATA 분기
      └─ PipelineParityTest.kt   pipeline.py parity — complete-week·insufficient-data 예제 전체 파이프라인 구조 대조, 결정론, rules_version/schema_version
   ```

## 실행

```bash
cd kotlin_port
./gradlew test
```

Gradle wrapper(9.4.1)가 이 디렉터리에 들어 있다. 시스템에 `gradle`·`kotlinc` 를
설치할 필요는 없고 JDK 17만 있으면 된다. Kotlin 플러그인과 의존성은 첫 실행 때
Maven Central에서 내려받는다.

## 진행 상황

| 단계 | 모듈 | 상태 |
|---|---|---|
| 1 | `Windows.kt` | ✅ 이식 완료, fixtures 3케이스 포함 11개 테스트 통과 |
| 2 | `Models.kt` | ✅ 이식 완료, 검증 규칙 27개 테스트 통과 |
| 3 | `Analytics.kt` | ✅ 이식 완료, `AnalyticsTest.kt` 14개 테스트 통과 (`_pct` banker's rounding·null 전파·week_status 4종·complete-week 예제 부분 대조 포함). 순환 의존은 (A) `MissionEvaluator` 인터페이스 주입 방식으로 처리 — 4단계에서 실제 구현체 연결 |
| 4 | `Missions.kt` | ✅ 이식 완료, `MissionsTest.kt` 10개 테스트 통과 (`reduce_target`·`evaluate_mission` fixtures 전 케이스, 야간 complete 조건, `baseline_ms` 처음 7개, `_propose_one` F17/임시목표 상한 포함). `reduce_target`은 `BigDecimal` 사용 |
| 5 | `Narratives.kt` | ✅ 이식 완료, `NarrativesTest.kt` 18개 테스트 통과 (`rotation_seed`의 `toordinal()`/`toEpochDay()` 719163 오프셋 실측 대조, `minutes()` half-to-even 반올림, 문장 회전 결정론·고정 절 불변, `INSUFFICIENT_DATA` 활성 목표 유무 분기 포함) |
| 6 | `Pipeline.kt` | ✅ 이식 완료. `PipelineParityTest.kt` 5개 테스트 통과 (`complete-week`·`insufficient-data` 예제 전체 구조 대조, 결정론, `rules_version`="2026-09-10.1", `schema_version`="1") |
| 6-보완 | `Json.kt` 입력 검증 parity | ✅ 감사 FAIL(t_3d775443) 해소. `JsonValidationTest.kt` 16개 테스트 통과 — 키 부재(ValidationError) vs 명시적 null(정상 통과) 구분, unknown field 거부(root·중첩 객체), `schema_version` Literal 검증 |

**전 단계 이식 완료.**

테스트 총 104개 / 실패 0 (`./gradlew test --rerun-tasks --console=plain`). (Windows 11 + Models 30 + Analytics 14 + Missions 10 + Narratives 18 + Pipeline 5 + JsonValidation 16)

Python 기준 구현(`screentime_analysis`, `source .venv/bin/activate && python -m pytest -q`)도 116개 전부 통과.

### 6단계 — `pipeline.py` 이식과 예제 parity

`analyze(request: AnalysisInput): AnalysisOutput` 하나가 진입점이다. Python과 동일한
순서로 조립한다 (`Pipeline.kt`):

```text
analyzeWeek()        -- 주간 집계
getWeekStatus()       -- 주 상태 (ready / in_progress / awaiting_data / insufficient_data)
missionResults()      -- 미션 판정
proposeTargets()      -- 다음 목표 제안
renderInsights()      -- 근거 문장
→ rulesVersion = RULES_VERSION 주입
```

예제 parity(`contracts/examples/*.json`)는 문자열 전체 비교가 아니라 **파싱 후 구조
비교**로 검증한다(`PipelineParityTest.kt`). 필드 순서 차이와 `Double` 표현 차이
(`12.35` vs `12.350000000000001`)를 걸러내면서도 값 불일치는 어느 필드인지 정확히
찍어준다. 두 예제 모두 Kotlin `analyze()` 출력이 **실제 Python `analyze()` 실행값**과
일치함을 직접 재확인했다:

```bash
cd screentime_analysis && source .venv/bin/activate
python -m screentime --input contracts/examples/complete-week.input.json --output /tmp/py-out.json
# → contracts/examples/complete-week.output.json 과 diff 없음 (일치)
python -m screentime --input contracts/examples/insufficient-data.input.json --output /tmp/py-out2.json
# → contracts/examples/insufficient-data.output.json 과 diff 없음 (일치)
```

### JSON 직렬화 (`Json.kt`)

`kotlinx-serialization-json`을 `build.gradle.kts`에 추가했다(`kotlinx-serialization-json:1.7.3`,
`plugin.serialization` 2.2.10). 다만 도메인 모델(`Models.kt`)에 `@Serializable`을
직접 붙이지 않는다. 필드명이 camelCase인 Kotlin 클래스와 snake_case인 계약을 자동
매핑에 맡기면 `null`과 필드 부재("확인 불가" vs "확인된 0")의 구분이 매핑 규칙 뒤로
숨는다. `Json.kt`에서 `JsonObject`/`JsonElement`를 수동으로 오가며 그 경계를 코드로
드러낸다 — `requireElement`(키 없음 → `ValidationException`) vs 값이 `JsonNull`이면
그대로 `null`을 반환하는 구분. `AnalysisInput`의 required-nullable 필드
(`last_collection_attempt_ms`, `current_daily_target_ms`, `current_night_target_ms`)는
키가 없으면 거부하고 값이 `null`이면 통과시킨다. 모든 모델(root·중첩 객체 포함)은
`rejectUnknownKeys`로 Python `extra="forbid"`와 동일하게 모르는 필드를 거부한다.

2단계에서 옮긴 모델: `AppDuration` `WindowAggregate` `Mission` `Proposal`
`MissionResult` `DayMetrics` `AppMetrics` `Comparison` `WeeklyMetrics`
`Insight` `AnalysisInput` `AnalysisOutput`.
Python `Literal[...]` 은 enum(`Quality` `WindowKind` `MissionKind`
`MissionStatus` `WeekStatus`)으로 옮겼고, 직렬화 문자열은 `wire` 프로퍼티가
Python 과 같은 snake_case 를 그대로 낸다 (`pre_bed`, `not_applicable`).

### 경계 위조 방지 (`models.py:314-325`)

`AnalysisInput` 은 각 집계의 `(start_ms, end_ms)` 를 프로필로 다시 계산한
`dailyWindow()` / `nightWindows()` 결과와 대조한다. 이 검사가 없으면
**1분짜리 구간에 빈 앱 목록을 넣어 하루 전체를 '확인된 0'으로 위조**할 수 있다.

`null` 과 `0` 은 끝까지 구분한다. `apps == null` 은 "확인 불가"라 `totalMs()` 가
`null` 을 내고, `apps == []` 는 "확인된 0"이라 `0L` 을 낸다.
개별 앱의 `durationMs` 는 구간 길이를 넘을 수 없지만 **합계는 넘을 수 있다**
(멀티윈도우). 합계를 검사하면 오답이다.

1단계에서 대조한 fixture 케이스:

| 블록 | id | 내용 | 결과 |
|---|---|---|---|
| `night_windows` | F07 | `Asia/Seoul` 2026-09-13 bed 00:00 / wake 07:00 경계 | 통과 |
| `daily_window_dst` | F21 | `America/New_York` 2026-03-08 = 82,800,000ms (23h) | 통과 |
| `daily_window_dst` | F21 | `America/New_York` 2026-11-01 = 90,000,000ms (25h) | 통과 |

`mission_judgement` 6케이스와 `examples/*.json` 대조는 4·6단계 범위다.

## `localize()` 의 DST 처리 — `ZonedDateTime.of()` 를 쓰면 안 된다

Python `windows.py` 의 정책은 두 가지다.

```text
중복 시각(가을 되돌림)    → 먼저 오는 오프셋 (Python fold=0)
존재하지 않는 시각(봄 갭) → 전환 후 첫 유효 시각
```

`java.time` 기본 동작은 겹침에서는 같지만 **갭에서 다르다.** `ZonedDateTime.of()` 는
벽시계를 갭 길이만큼 밀어서 `02:30 → 03:30` 을 만들고, Python 은 1분씩 전진해
첫 유효 벽시계인 `03:00` 을 찾는다. 결과 instant 가 30분 어긋난다.

그래서 `Windows.kt` 는 `ZoneRules.getValidOffsets()` / `getTransition()` 을 직접 본다.
두 동작 모두 `WindowsParityTest` 에 테스트가 있고, Python 실행값과 교차 확인했다.

## 규칙

**Python이 정본이다.** 결과가 다르면 Kotlin을 고친다.
Python 쪽 버그로 판단되면 먼저 `screentime_analysis` 에 실패 테스트를 추가해
재현시킨 뒤 양쪽을 같이 고친다.

`java.time` 을 쓴다 — Android API 26+ 이고 그 이하는 desugaring이 필요하다.
`Int` 를 쓰지 않는다. 밀리초 상한이 `2^53-1` 이라 넘친다.

## 이식 요약 — FE 인계 시 주의사항

- Python과 의도적으로 다른 동작은 **없다.** parity 테스트가 전부 구조 비교로 통과했고
  값·경계·정렬·회전·null 처리 전부 원본과 1:1 대응한다.
- 감사 카드(t_c016b9e3)가 지목한 `minutes()`의 half-to-even 반올림은 Python
  `narratives.py:65` 의 `round()` 도 같은 방식이라(경계값 90999ms→2분) **양쪽이
  동일하게 동작**함을 재확인했다. 이 부분을 FE에서 다시 "직관적 반올림"으로
  바꾸면 parity가 깨진다.
- `analyze()` 는 순수 함수다. `LocalDate.now()`/`System.currentTimeMillis()`/`Random()`
  을 호출하지 않는다. FE에서 `as_of_ms`·`week_start`·현재 목표값을 전부 주입해야 한다.
- `Json.kt` 는 `contracts/examples/*.json` 대조 전용이다. FE 앱에서 실제 API 응답을
  파싱할 때 이 파일을 그대로 재사용해도 되지만, 필드 추가 시 `Models.kt`가 아니라
  이 파일의 `inputFromJson`/`outputToJson`도 같이 갱신해야 한다 — 자동 매핑이 아니라서
  누락되면 조용히 필드가 빠진다.
- 남은 위험: `PipelineParityTest.kt`는 예제 2건만 대조한다. 새 엣지 케이스(예:
  모든 앱이 target_packages 밖, 미션이 전혀 없는 주)는 fixtures나 예제에 추가해야
  회귀를 잡을 수 있다.
