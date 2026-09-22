# Kotlin 이식 가이드

주간 분석·미션 판정·한 줄 요약을 **앱에서 실행하기 위한 이식 문서**다.
Python 패키지(`screentime/`)는 규칙의 정본이고, 이식본이 제품 경로다.

배경은 [루트 README의 「주간 분석은 앱에서 돈다」](../../README.md#주간-분석은-앱에서-돈다) 참고.

## 0. 이식 범위

| Python 모듈 | 줄수 | Kotlin 대응 | 비고 |
|---|---|---|---|
| `models.py` | 355 | data class + 검증 | Pydantic 검증 규칙을 직접 옮겨야 한다 |
| `windows.py` | 130 | `java.time` | **DST가 핵심.** 가장 먼저 옮긴다 |
| `analytics.py` | 308 | 순수 함수 | null/0 구분이 전부다 |
| `missions.py` | 212 | 순수 함수 | 판정 5분기 |
| `narratives.py` | 246 | 템플릿 렌더러 | 문장 회전 규칙 포함 |
| `pipeline.py` | 34 | 진입점 | `analyze()` 하나 |

합계 약 1,400줄. HTTP·DB·CLI(`__main__.py`)는 이식 대상이 아니다.

## 1. 순서

```text
1. windows.py    → DST·야간·주간 경계        fixtures 대조 가능
2. models.py     → 입력 검증
3. analytics.py  → 합산·평균·비교
4. missions.py   → 판정                      fixtures 대조 가능
5. narratives.py → 문장
6. pipeline.py   → 조립
```

**1번과 4번을 먼저 끝내고 `fixtures.json`으로 대조하라.** 이 두 개가 맞으면
나머지는 산술이라 비교적 안전하다. 순서를 바꾸면 틀린 경계 위에 산술을 쌓게 된다.

## 2. parity 테스트 — 이게 이식의 합격 기준이다

`contracts/fixtures.json` 의 세 블록을 Kotlin 테스트로 그대로 옮긴다.

| 블록 | 검사 대상 | 케이스 |
|---|---|---|
| `night_windows` | 야간 구간 경계 (F07) | 1 |
| `daily_window_dst` | DST 전환일 길이 (F21) | 2 |
| `mission_judgement` | 미션 판정 (F02~F05, F16) | 6 |

추가로 `examples/*.input.json` 을 Kotlin `analyze()` 에 넣고 `examples/*.output.json`
과 일치하는지 검사한다. 출력 예제는 손으로 쓴 값이 아니라 **실제 Python 실행값**이다.

```text
Kotlin analyze(complete-week.input.json)
  == complete-week.output.json      → 통과
```

불일치가 나오면 **Python이 옳다고 가정하고 Kotlin을 고친다.** Python 쪽 버그로
판단되면 먼저 `screentime_analysis` 테스트를 추가해 재현시킨 뒤 양쪽을 같이 고친다.

## 3. 함정 — Python과 Kotlin이 다르게 동작하는 지점

### 3-1. 정수 나눗셈

Python `//` 는 **음수에서 내림(floor)** 이고 Kotlin `/` 는 **0 방향 절단**이다.

```text
Python:  -7 // 2  ==  -4
Kotlin:  -7 / 2   ==  -3
```

사용 시간은 음수가 아니지만 `delta_ms` 는 음수가 된다. 비율·평균 계산에서
음수 값을 나누는 코드가 있으면 반드시 확인하라.

### 3-2. 나눗셈 자체

Python `/` 는 항상 float, Kotlin `Int / Int` 는 Int다. `delta_pct` 계산에서
정수 나눗셈으로 떨어지면 조용히 0이 된다.

### 3-3. 오버플로

밀리초 상한이 `2**53-1` 이다. Kotlin `Int` 는 약 21억(2^31)이라 **넘친다.**
사용 시간·시각은 전부 `Long` 을 쓴다. `Int` 를 쓰면 25일치 밀리초에서 깨진다.

### 3-4. 시간대

```kotlin
ZoneId.of("Asia/Seoul")
LocalDate.atStartOfDay(zone)   // DST 전환일에 23h/25h가 자동 반영된다
```

**`86_400_000L` 을 하드코딩하지 마라.** `fixtures.json` 의 `daily_window_dst` 가
정확히 이걸 잡는 테스트다 (`America/New_York` 2026-03-08 = 82,800,000ms).

Android 기기의 tzdata는 OS 버전에 따라 다르다. `java.time` 은 API 26+ 이고
그 이하를 지원하려면 desugaring이 필요하다.

### 3-5. null과 0

Python `Optional[int]` 를 Kotlin `Int` 로 옮기면 **null이 0으로 뭉개진다.**
이건 이 프로젝트에서 가장 치명적인 실수다.

| Python | Kotlin |
|---|---|
| `total_ms: int \| None` | `totalMs: Long?` |
| `apps: list \| None` | `apps: List<AppUsage>?` |

`?: 0` 같은 기본값 처리를 습관적으로 넣지 마라. `null` 은 **확인 불가**라는 정보다.
상세 규칙은 [`be-handoff.md` 4절](be-handoff.md#4-null과-0의-구분--가장-흔한-오해).

### 3-6. 딕셔너리 순회 순서

Python dict는 삽입 순서를 보존한다. Kotlin `HashMap` 은 보존하지 않는다.
`per_app` 목록 순서가 출력에 나타나므로 `LinkedHashMap` 을 쓴다.

## 4. 검증 이식

Pydantic이 해주던 걸 직접 해야 한다. 빠뜨리기 쉬운 것들:

- **구간 경계 일치 검사** — 프로필로 계산한 경계와 입력 `start_ms`/`end_ms` 가
  정확히 같아야 한다. 이게 없으면 1분 구간에 빈 앱 목록을 넣어 하루를
  '확인된 0분'으로 위조할 수 있다 ([`be-handoff.md` 4-1절](be-handoff.md#4-1-집계-경계는-정확히-일치해야-한다))
- anchor date 최대 21개, 구간당 앱 최대 200개
- 시각 범위 2000-01-01 ~ 2100-01-01 UTC
- 한 요청 안의 `profile_version`·`measurement_version` 단일성

검증 실패는 예외로 던지고 **빈 성공 결과로 치환하지 않는다.** 오류 메시지에
사용자 원본 값(패키지명 등)을 넣지 않는다.

## 5. 문장 회전

`narratives.py` 는 `week_start` 로 도입부 표현을 결정론적으로 회전시킨다.
무작위가 아니다 — 같은 주를 몇 번 분석해도 같은 문장이 나와야 한다.

```text
바뀌는 것:     도입부 표현
바뀌지 않는 것: evidence 값, 문장 안의 숫자, 의미를 담은 고정 절
```

`Random()` 이나 `System.currentTimeMillis()` 를 쓰면 이 계약이 깨진다.

## 6. 무상태 계약 유지

```text
현재 시각을 읽지 않는다      → as_of_ms 를 파라미터로 받는다
DB를 읽지 않는다            → 입력으로만 판단한다
로그를 남기지 않는다         → 사용 기록이 logcat에 남으면 개인정보 문제다
```

Kotlin 이식본도 같은 계약을 지킨다. `LocalDate.now()` 나 `System.currentTimeMillis()`
를 분석 로직 안에서 호출하면 테스트가 불가능해지고 parity도 깨진다.

호출 측(ViewModel 등)에서 시각을 주입한다.

## 7. 실행 위치

주간 분석은 **리포트 화면을 열 때** 돌면 된다. 상시 백그라운드 작업이 아니다.

```text
사용자가 리포트 탭 진입
  → Room에서 집계 조회
  → analyze() 실행 (수 ms)
  → 화면 표시
```

순수 산술이라 중급기에서도 즉시 끝난다. WorkManager로 미리 계산해둘 필요는
현재 범위에서는 없다. 필요해지면 그때 추가한다.

## 8. 이식 완료 판정

- [ ] `fixtures.json` 9개 케이스 전부 통과
- [ ] `examples/*.input.json` → `examples/*.output.json` 일치
- [ ] `Long` 사용 확인 (`Int` 없음)
- [ ] `86_400_000` 하드코딩 없음
- [ ] nullable 타입이 Python `Optional` 과 1:1 대응
- [ ] 분석 로직 안에 현재 시각 호출 없음
- [ ] 구간 경계 일치 검사 구현됨
- [ ] logcat에 사용 기록·패키지명 출력 없음

## 9. Python 패키지는 계속 유지한다

이식이 끝나도 `screentime_analysis/` 를 지우지 않는다.

- 규칙을 바꿀 때 **Python에서 먼저 바꾸고 테스트**한 뒤 Kotlin에 반영한다
- `fixtures.json` 을 갱신할 때 Python 실행값을 기준으로 만든다
- `rules_version` 을 올릴 때 양쪽을 같이 올린다

양쪽이 갈라지면 이 문서 전체가 무의미해진다.
