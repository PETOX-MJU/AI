# BE 담당자 전달 문서

AI 측 산출물은 **무상태 Python 분석 라이브러리** 하나다.
HTTP 서버·인증·DB·스케줄러는 포함하지 않으며 BE가 자신의 구조에 맞게 붙인다.

## 1. 설치

```bash
pip install screentime-0.1.0-py3-none-any.whl
```

런타임 의존성은 `pydantic>=2.7` 하나다. FastAPI·DB 드라이버는 이 패키지가 요구하지 않는다.

## 2. 호출

```python
from screentime import AnalysisInput, AnalysisOutput, analyze


def run_analysis(payload: dict) -> dict:
    request = AnalysisInput.model_validate(payload)
    result: AnalysisOutput = analyze(request)
    return result.model_dump(mode="json")
```

`analyze`가 유일한 상위 진입점이다. 내부 함수(`analyze_week`, `evaluate_mission`,
`propose_targets`, `render_insights`)도 재사용을 위해 노출되어 있다.

**함수는 DB도 시스템 현재 시각도 읽지 않는다.** 분석 기준 시각은 호출자가 `as_of_ms`로 넣는다.
같은 입력과 같은 `rules_version`은 항상 같은 출력을 반환한다.

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

- 구조·단위·범위 오류 → `pydantic.ValidationError`. 잘못된 입력을 빈 성공 결과로 치환하지 않는다.
- 데이터 부족 → 예외가 아니라 `week_status: "insufficient_data"` 같은 **정상 결과**다.
- 사용자 식별자·세션·토큰·HTTP 상태 코드는 이 패키지의 입력이 아니다.
  올바른 사용자의 기록을 조회하고 결과를 사용자에게 연결하는 것은 BE 책임이다.

`ValidationError`를 그대로 클라이언트에 노출하지 마라. 오류 위치(`loc`)와 유형(`type`)만
전달하고 `input` 필드는 사용자 원본 값이므로 로그에도 남기지 않는 편이 안전하다.

**`loc`에도 사용자 값이 섞인다.** `profile.purposes`는 패키지명을 키로 쓰므로
`("profile", "purposes", "com.private.app")` 같은 경로가 나온다. 선언된 필드 이름이
아닌 조각은 가려라. 이 패키지의 CLI는 `_safe_location()`으로 그렇게 처리한다.

## 6. week_status

| 값 | 의미 | BE 처리 |
|---|---|---|
| `in_progress` | 이번 주 구간이 아직 안 끝남 | 진행 상황만 표시 |
| `awaiting_data` | 구간은 끝났으나 그 뒤 수집 시도가 없음 | 동기화 유도 |
| `ready` | 7일·7야간 모두 complete | 보고서 확정 가능 |
| `insufficient_data` | 수집했으나 일부 복원 실패 | 확보된 값만 표시 |

`last_collection_attempt_ms`만으로 집계 품질을 `complete`로 승격하지 마라.

## 7. 제안(Proposal)은 활성 미션이 아니다

`analyze`가 돌려주는 `proposals`는 **추천**이다. BE가 해야 할 일:

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
| `schema_version` | 입출력 계약 버전. 현재 `"1"` |
| `rules_version` | 계산·판정 규칙 버전. 바뀌면 결과가 달라질 수 있다 |
| `profile_version` | 사용자 설정 스냅샷 버전 |
| `measurement_version` | FE 측정 정의 버전 |

한 요청 안의 모든 집계·미션은 `profile.version`과 같아야 하고 `measurement_version`도 하나여야 한다.
다른 버전의 보고서는 **당시 Profile로 별도 요청**한다. 과거 보고서를 현재 기준선으로 재사용하지 마라.

## 10. 입력 한도

- anchor date 최대 21개 (현재 주 + 이전 주를 포함하는 범위)
- 한 구간당 앱 최대 200개
- duration/target 상한 `2**53-1` ms, 시각 범위 2000-01-01 ~ 2100-01-01 UTC

HTTP 본문 크기 제한, 타임아웃, 인증 실패 처리 등 전송 계층 제약은 BE가 정한다.

## 11. 개인정보

이 패키지는 실행 중 입력·프로필·결과를 **영구 저장하거나 외부로 보내지 않는다.**
로그도 남기지 않는다. 저장 방식과 보관 정책은 BE 담당 범위다.

동의 없이 사용 기록을 서버나 외부 AI로 보내지 않는 것은 FE/BE가 보장한다.
AI 패키지는 실제 수집 여부나 사용자 신원을 검증할 수 없다.

## 12. 설명(insights)

현재 `insights`는 **전부 규칙 기반 템플릿**이며 `source: "template"`이다.
외부 생성형 AI를 호출하지 않는다. 화면에서 AI 생성 결과라고 표시하지 마라.

`evidence`의 수치와 `text`의 숫자는 항상 일치한다. 외부 모델이 숫자를 다시 계산하지 않도록
코드가 문장 슬롯에 값을 넣는다.

`INSUFFICIENT_DATA` 문구는 `current_*_target_ms` 전달 여부에 따라 달라진다.
활성 목표를 보내면 '현재 목표는 그대로 유지됩니다', 보내지 않으면 '임시 목표를 사용합니다'가 된다.
**활성 목표가 있는데 null로 보내면 사용자에게 잘못된 안내가 나간다.**

## 13. 예제와 스키마

| 파일 | 내용 |
|---|---|
| `input.schema.json` | `AnalysisInput.model_json_schema()` |
| `output.schema.json` | `AnalysisOutput.model_json_schema()` |
| `examples/complete-week.*.json` | F01 완전한 주 |
| `examples/insufficient-data.*.json` | F04 확인 불가한 주 |
| `fixtures.json` | FE 로컬 판정 대조용 공통 입력·기대값 |

출력 예제는 **실제 `analyze` 실행값**이다. 손으로 쓴 값이 아니며
`tests/test_contract_examples.py`가 구현과의 일치를 검사한다.

스키마·예제를 다시 만들려면 위 테스트를 먼저 돌려 현재 구현과 어긋나는지 확인하라.
