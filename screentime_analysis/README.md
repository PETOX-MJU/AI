# screentime — 스크린타임 분석 라이브러리

펫톡스의 **AI 담당 산출물**이다. 사용 시간 집계를 받아 주간 분석, 개인 기준선,
맞춤 미션 후보, 규칙 기반 판정, 근거 기반 한국어 설명을 돌려주는 **무상태 Python 패키지**다.

HTTP 서버·인증·DB·스케줄러·Android 코드는 포함하지 않는다. BE가 이 패키지를 호출한다.

## 설치

```bash
pip install dist/screentime-0.1.0-py3-none-any.whl
```

런타임 의존성은 `pydantic>=2.7` 하나다.

## 사용

```python
from screentime import AnalysisInput, AnalysisOutput, analyze


def run_analysis(payload: dict) -> dict:
    request = AnalysisInput.model_validate(payload)
    result: AnalysisOutput = analyze(request)
    return result.model_dump(mode="json")
```

`analyze`가 유일한 상위 진입점이다. DB도 시스템 현재 시각도 읽지 않으며,
분석 기준 시각은 호출자가 `as_of_ms`로 넣는다. 같은 입력은 항상 같은 출력을 낸다.

### CLI 데모

```bash
python -m screentime --input contracts/examples/complete-week.input.json --output /tmp/out.json
```

성공 시 exit 0, 검증 실패 시 exit 2. 실패 메시지는 **필드 위치와 오류 유형만** 담고
원본 사용자 값은 출력하지 않는다. 네트워크·API 키·DB 없이 동작한다.

## 구성

| 모듈 | 역할 |
|---|---|
| `models.py` | 입출력 Pydantic 모델과 검증 규칙 |
| `windows.py` | 날짜·야간·주간·시간대 경계 (DST 포함) |
| `analytics.py` | 합산·평균·비교·데이터 품질 |
| `missions.py` | 목표 제안·미션 판정 순수 함수 |
| `narratives.py` | 근거 기반 한국어 템플릿 |
| `pipeline.py` | `analyze` 진입점 |

## 핵심 규칙

**데이터가 없다는 이유로 0이나 성공을 만들지 않는다.**

| 값 | 의미 |
|---|---|
| `apps: []` + `complete` | 확인된 0분 |
| `apps: null` + `unavailable` | 확인 불가 |
| `*_total_ms: null` | complete 구간이 하나도 없음 |
| `*_mean_ms: null` | complete 구간이 7개가 아님 |
| `delta_pct: null` | 분모가 0 |

- 단위는 정수 밀리초, 시각은 UTC epoch milliseconds. 분 변환은 화면에서만 한다
- 하루를 86,400,000ms로 가정하지 않는다. DST 전환일은 23시간 또는 25시간이다
- 성공률 분모에서 `unknown`·`in_progress`·`not_applicable`은 제외한다
- 제안(`Proposal`)은 추천이며 활성 미션이 아니다. 수락·저장·활성화는 BE가 한다

## 개발

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
python -m ruff check .
python -m build
```

## 문서

| 파일 | 대상 |
|---|---|
| `contracts/be-handoff.md` | BE 담당자 — 설치·호출·필드·오류·버전·책임 경계 |
| `contracts/android-data-contract.md` | FE 담당자 — 수집·정규화·품질·경계 정의 |
| `contracts/input.schema.json`, `output.schema.json` | JSON Schema |
| `contracts/examples/` | 실제 `analyze` 실행으로 만든 입출력 예제 |
| `contracts/fixtures.json` | FE 로컬 판정 대조용 공통 입력·기대값 |
| `evaluation/report.md` | 검증 결과와 미검증 항목 |

## 한계 — 반드시 읽을 것

- **설명(`insights`)은 전부 규칙 기반 템플릿이다.** 외부 생성형 AI를 호출하지 않으며
  `source`는 항상 `"template"`이다. 화면에서 AI 생성 결과라고 표시하지 마라.
  외부 AI 제공자는 아직 선택되지 않았다
- **합성 데이터로만 검증했다.** 실제 사용자 행동 개선 효과나 모델 품질을 입증한 것이 아니다
- **원시 Android 이벤트는 검증하지 않았다.** 이 패키지는 집계 이후의 산술과 경계만 다룬다.
  F13/F14/F15/F22 등은 FE가 실기기에서 확인해야 한다
- 통계적 유의성, 중독, 불안·우울, 실제 잠든 시각, 의지 부족을 사용 기록으로 판단하지 않는다
- 하나의 기기·하나의 로컬 프로필이 MVP 범위다
- **Python 3.12가 아니라 3.13.9에서 검증했다.** 자세한 내용은 `requirements.lock` 참고

## 개인정보

이 패키지는 실행 중 입력·프로필·결과를 **영구 저장하거나 외부로 보내지 않는다.** 로그도 남기지 않는다.
CLI는 사용자가 지정한 파일만 읽고 쓴다. 저장·보관 정책은 BE 담당 범위다.

테스트와 예제의 데이터는 전부 합성이다. 실제 사용 기록은 저장소에 넣지 않는다.
