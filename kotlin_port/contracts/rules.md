# 분석 규칙 상세

판정·경계·버전 규칙의 상세 명세다. 코드는 `kotlin_port/src/main/kotlin/com/petox/screentime/` 이고
앱(FE)이 이 코드를 복사해 폰 안에서 실행한다. **BE는 분석을 호출하지 않는다.**

아래의 "앱이 한다"는 저장·상태 관리 계층(Room 등)의 책임을 뜻한다.
특히 7절의 제안 수락·저장·적용 흐름은 앱 코드가 맡는다.

## 1. 호출

```kotlin
val output: AnalysisOutput = analyze(input)          // AnalysisInput → AnalysisOutput
val json: String = AnalysisJson.encodeOutput(output) // 계약 JSON(snake_case)
```

`analyze` 가 유일한 상위 진입점이다. **DB도 시스템 현재 시각도 읽지 않는다.**
분석 기준 시각은 호출자가 `as_of_ms` 로 넣는다.
같은 입력과 같은 `rules_version` 은 항상 같은 출력을 반환한다.

## 2. 상태는 분석기가 갖지 않는다

`analyze` 는 순수 함수다. 사용 기록 수집, 결과 저장, 미션 발급·수락, 목표 적용은 전부 앱이 한다.
분석기는 **호출 한 번에 대한 입력만** 보고 결과를 돌려준다.

## 3. 단위와 표현

| 항목 | 규칙 |
|---|---|
| 사용 시간 | 정수 **밀리초**. 화면에서만 분으로 표시 |
| 시각 | UTC epoch **milliseconds** (초 아님) |
| 시간대 | IANA 식별자 문자열 (`Asia/Seoul`) |
| 날짜 | `YYYY-MM-DD` |
| 시:분 | `HH:MM` 24시간 |

## 4. null과 0의 구분 — 가장 흔한 오해

| 값 | 의미 |
|---|---|
| `apps: []` + `quality: "complete"` | **확인된 0분**. 유효 기록으로 센다 |
| `apps: null` + `quality: "unavailable"` | **확인 불가**. 0으로 바꾸면 안 된다 |
| `selected_total_ms: null` | 그 주에 complete 구간이 하나도 없음 |
| `selected_daily_mean_ms: null` | complete 일수가 7이 아님 |
| `delta_pct: null` | 분모가 0. `0분 → 20분`은 절대 증가로만 설명 |
| `per_app[].total_ms: 0` | complete 기록이 있고 그 앱을 쓰지 않음 |
| `per_app[].total_ms: null` | 그 주에 complete 구간이 없어 알 수 없음 |
| `target_ms: null` (Proposal) | 기준선이 1분 미만이라 숫자 목표를 만들지 않음 |

**데이터가 없다는 이유로 사용량 0이나 미션 성공을 만들지 않는다.**

## 4-1. 집계 경계는 정확히 일치해야 한다

`aggregates[*].start_ms` / `end_ms`는 **프로필로 계산한 구간과 정확히 같아야 한다.**
다르면 `ValidationError`다.

```text
daily     → 로컬 자정 ~ 다음 로컬 자정
pre_bed   → [취침 - 30분, 취침)
after_bed → [취침, 기상)
```

이 검사가 없으면 1분짜리 구간에 빈 앱 목록을 넣어 하루 전체를 '확인된 0분'으로
위조할 수 있다. FE는 `contracts/fixtures.json`으로 경계 계산을 대조하라.

Mission의 `window_start_ms` / `window_end_ms`는 **검사하지 않는다.** 발급 당시
프로필의 스냅샷이므로 현재 프로필과 다를 수 있다.

## 5. 오류 처리

- 구조·단위·범위 오류 → `ValidationException`. 잘못된 입력을 빈 성공 결과로 치환하지 않는다.
- 데이터 부족 → 예외가 아니라 `week_status: "insufficient_data"` 같은 **정상 결과**다.
- 사용자 식별자·세션·토큰은 이 분석기의 입력이 아니다. 어느 사용자의 기록인지는 앱이 관리한다.

**`ValidationException` 메시지를 화면에 그대로 띄우지 마라.** 메시지에 필드 이름과 값이
섞인다 — `profile.purposes` 는 패키지명을 키로 쓰므로 사용자가 쓰는 앱 목록이 드러난다.
로그(logcat)에도 남기지 않는다.

## 6. week_status

| 값 | 의미 | BE 처리 |
|---|---|---|
| `in_progress` | 이번 주 구간이 아직 안 끝남 | 진행 상황만 표시 |
| `awaiting_data` | 구간은 끝났으나 그 뒤 수집 시도가 없음 | 동기화 유도 |
| `ready` | 7일·7야간 모두 complete | 보고서 확정 가능 |
| `insufficient_data` | 수집했으나 일부 복원 실패 | 확보된 값만 표시 |

`last_collection_attempt_ms`만으로 집계 품질을 `complete`로 승격하지 마라.

## 7. 제안(Proposal)은 활성 미션이 아니다

`analyze`가 돌려주는 `proposals`는 **추천**이다. 앱의 저장 계층이 해야 할 일:

1. 사용자에게 제안을 보여주고 `수락` / `직접 수정` / `현재 목표 유지` 중 선택을 받는다.
2. `(basis_week, kind, profile_version, rules_version)`별로 그 선택을 저장한다.
   무상태 함수를 재호출해도 이미 결정한 같은 주의 제안을 다시 적용하지 않기 위해서다.
3. 수락된 목표를 **아직 시작하지 않은 첫 구간부터** 적용한다. 진행 중인 미션을 소급 변경하지 않는다.
4. 발급한 Mission의 `profile_version`·`target_ms`·`window`를 그 시점 값으로 저장한다.
   현재 설정으로 과거 결과를 재평가하지 않는다.
5. 다음 분석 호출 시 활성 목표를 `current_daily_target_ms` / `current_night_target_ms`로 넣는다.
   **분석 결과의 proposal을 current 값에 자동 복사하지 마라.**

임시 목표만 쓰는 유형은 `current_*`를 `null`로 보낸다. 임시 목표는 `profile`에서 읽는다.

### reason_code

| 코드 | 의미 |
|---|---|
| `INITIAL_BASELINE` | 유효 7개로 첫 개인화 목표를 계산함 |
| `REDUCE_AFTER_SUCCESS` | 직전 주 판정 7개·성공 5개 이상이라 10% 감축 |
| `MAINTAIN_INSUFFICIENT_SUCCESS` | 감축 조건 미충족. 현재 목표 유지 |
| `MAINTAIN_AT_FINAL_GOAL` | 이미 최종 목표 이하. 추가 감축 요구 없음 |
| `LOW_USAGE_NO_TARGET` | 기준선이 1분 미만. 숫자 목표를 만들지 않음 |

해당 유형의 `proposals`가 **비어 있으면** 아직 기준선(유효 7개)을 확보하지 못한 것이다.
임시 목표를 계속 쓰고, 이유는 `insights`의 `INSUFFICIENT_DATA`가 설명한다.

### per_app에 포함되는 앱

이번 주 기록에 등장한 앱뿐 아니라 **이전 주에만 쓰인 앱과 선택한 앱(`target_packages`)** 도
포함된다. 사용을 완전히 끊은 앱의 `0분 / -100%` 변화가 화면에서 사라지지 않게 하기 위해서다.

## 8. 미션 판정

`analyze`는 **입력으로 받은 Mission만** 판정한다. 미션을 새로 만들지 않는다.

```text
구간 시작 뒤에 수락됨            → not_applicable
구간 종료 전                     → in_progress (초과했어도)
종료 후 quality != complete      → unknown
종료 후 complete, 사용 <= 목표   → succeeded
종료 후 complete, 사용 > 목표    → failed
```

야간은 `pre_bed`와 `after_bed`가 **둘 다** complete일 때만 complete다.

성공 카운트는 **`week_start` 주간의 미션만** 센다. 입력에 이전 주 미션을 함께 보내도
감축 조건(판정 7개·성공 5개) 계산에는 보고서 주간만 쓰인다.
`mission_results`에는 보낸 미션이 모두 들어간다.

성공률 분모에서 `unknown` / `in_progress` / `not_applicable`은 제외된다.
`daily_evaluable_count`가 분모이고 `daily_success_count`가 분자다.
**`2/2 달성, 5일 확인 불가`를 `주간 100% 달성`으로 표시하지 마라.**

## 9. 버전

| 필드 | 뜻 |
|---|---|
| `schema_version` | 입출력 계약 버전. 현재 `"2"` |
| `rules_version` | 계산·판정 규칙 버전. 바뀌면 결과가 달라질 수 있다 |
| `profile_version` | 사용자 설정 스냅샷 버전 |
| `measurement_version` | FE 측정 정의 버전 |

### schema_version 이력

| 버전 | 바뀐 것 |
|---|---|
| `"1"` | 최초 계약 |
| `"2"` | `metrics.previous_per_day` 추가 (필수). 대시보드 그래프가 지난주 일별 값을 다시 계산하지 않도록 출력에 담는다. 스키마가 `additionalProperties: false` 라 v1 소비자는 v2 응답을 거부한다 |

한 요청 안의 모든 집계·미션은 `profile.version`과 같아야 하고 `measurement_version`도 하나여야 한다.
다른 버전의 보고서는 **당시 Profile로 별도 요청**한다. 과거 보고서를 현재 기준선으로 재사용하지 마라.

## 10. 입력 한도

- anchor date 최대 21개 (현재 주 + 이전 주를 포함하는 범위)
- 한 구간당 앱 최대 200개
- duration/target 상한 `2**53-1` ms, 시각 범위 2000-01-01 ~ 2100-01-01 UTC

앱 내부 호출이므로 HTTP 본문 크기 제한이나 인증 실패 처리는 해당 없다.
입력 한도 초과는 앱 내부 예외로 처리한다.

## 11. 개인정보

이 패키지는 실행 중 입력·프로필·결과를 **영구 저장하거나 외부로 보내지 않는다.**
로그도 남기지 않는다. Kotlin 이식본도 같은 계약을 지킨다 — **사용 기록을 logcat에 출력하지 마라.**

분석은 기기 안에서 끝난다. 외부 생성형 AI는 도입하지 않기로 확정했다.
계정 백업 동의로 집계를 동기화하는 경우에만 데이터가 기기를 벗어난다.

## 12. 설명(insights)

`insights`는 **전부 규칙 기반 템플릿**이며 `source: "template"`이다.
생성형 AI를 호출하지 않는다 — **이건 확정된 설계이고 미완성 상태가 아니다.**
화면에서 AI 생성 결과라고 표시하지 마라.

`evidence`의 수치와 `text`의 숫자는 항상 일치한다. 외부 모델이 숫자를 다시 계산하지 않도록
코드가 문장 슬롯에 값을 넣는다.

### 문장은 주차에 따라 달라진다

같은 지표라도 `week_start`가 다르면 **도입부 표현이 바뀐다.** 매주 같은 문장이 반복되는 것을
막기 위한 회전이며 무작위가 아니다. 같은 주를 몇 번 분석해도 결과는 같다.

- 바뀌는 것: 도입부 표현
- 바뀌지 않는 것: **`evidence`의 값, 문장 안의 숫자, 의미를 담은 고정 절**

그러므로 `text`를 문자열 비교로 캐시 키에 쓰지 마라. 캐시 키에는 `evidence`와
`(week_start, rules_version)`을 쓴다.

`INSUFFICIENT_DATA` 문구는 `current_*_target_ms` 전달 여부에 따라 달라진다.
활성 목표를 보내면 '현재 목표는 그대로 유지됩니다', 보내지 않으면 '임시 목표를 사용합니다'가 된다.
**활성 목표가 있는데 null로 보내면 사용자에게 잘못된 안내가 나간다.**

## 13. 예제와 스키마

| 파일 | 내용 |
|---|---|
| `input.schema.json` | `AnalysisInput` JSON Schema |
| `output.schema.json` | `AnalysisOutput` JSON Schema |
| `examples/complete-week.*.json` | F01 완전한 주 |
| `examples/insufficient-data.*.json` | F04 확인 불가한 주 |
| `fixtures.json` | 구간 경계·미션 판정 대조용 입력·기대값 |

출력 예제는 **실제 `analyze` 실행값**이다. 손으로 쓴 값이 아니다.
`PipelineParityTest` 가 예제와 구현의 일치를, `WindowsParityTest`·`MissionsTest` 가
`fixtures.json` 의 기대값을 직접 읽어 검사한다.

예제·스키마를 바꿀 때는 README 「규칙을 바꿀 때」를 따른다.
