# 스크린타임 분석기 (Kotlin)

주간 사용 분석·미션 판정·목표 제안·한 줄 요약을 계산한다. **이 코드가 규칙의 정본이다.**
FE 앱이 `src/main/kotlin/com/petox/screentime/` 를 그대로 복사해 폰 안에서 실행한다
(FE `android/app/src/main/java/com/petox/screentime`). 사용 기록은 기기 밖으로 나가지 않는다.

처음엔 Python으로 규칙을 만들고 이 코드로 이식했다. 이식을 끝낸 뒤 Python 패키지는 지웠고,
그때 Python 실행값으로 만든 정답 JSON(`contracts/examples/`, `contracts/fixtures.json`)은
회귀 테스트로 계속 쓴다.

## 실행

```bash
cd kotlin_port
./gradlew test
```

JDK 17만 있으면 된다(Gradle wrapper 포함). 테스트 104개.

## 구조

```
src/main/kotlin/com/petox/screentime/
├─ Models.kt      입력·출력 모델과 검증 규칙
├─ Windows.kt     일/취침 전/취침 후 구간 경계 (시간대·DST)
├─ Analytics.kt   주간 집계·평균·전주 비교
├─ Missions.kt    미션 판정·다음 목표 제안
├─ Narratives.kt  근거 기반 한국어 설명 템플릿 (한 줄 요약)
├─ Pipeline.kt    analyze() 진입점
└─ Json.kt        계약 JSON ↔ 모델 수동 매핑
contracts/
├─ android-data-contract.md  FE 수집기가 지켜야 할 규칙 (구간 정규화·품질 코드)
├─ rules.md                  판정·경계·버전 규칙 상세
├─ input/output.schema.json  입출력 JSON Schema
├─ examples/                 정상 주·데이터 부족 주 입력과 기대 출력
└─ fixtures.json             구간 경계·미션 판정 대조 케이스
```

`analyze(request): AnalysisOutput` 은 순수 함수다. 현재 시각을 읽지 않으므로
`as_of_ms`·`week_start`·현재 목표를 호출하는 쪽이 전부 넣어야 한다.

## 핵심 규칙

**데이터가 없다는 이유로 0이나 성공을 만들지 않는다.**

| 값 | 의미 |
|---|---|
| `apps: []` + `complete` | 확인된 0분 |
| `apps: null` + `unavailable` | 확인 불가 |
| `*_total_ms: null` | complete 구간이 하나도 없음 |
| `*_mean_ms: null` | complete 구간이 7개가 아님 |
| `delta_pct: null` | 분모가 0 |

- 주간 합계·앱별 합계는 **complete 인 날만** 더한다. 진행 중인 날은 다음 리포트에 들어간다
- 단위는 정수 밀리초, 시각은 UTC epoch ms. 분 변환은 화면에서만 한다. `Int` 를 쓰지 않는다
- 하루를 86,400,000ms로 가정하지 않는다. DST 전환일은 23시간 또는 25시간이다
- 성공률 분모에서 `unknown`·`in_progress`·`not_applicable`은 뺀다
- 제안(`Proposal`)은 추천이다. 수락·저장·활성화는 앱이 한다
- 설명(`insights`)은 전부 규칙 기반 템플릿이다. 생성형 AI를 쓰지 않으며 `source` 는 항상 `"template"`
  (기각 사유는 [루트 README](../README.md#온디바이스-llm--검토했고-도입하지-않는다))

## 코드만 봐서는 모르는 결정

- **반올림은 half-to-even.** `bankersRound()`·`minutes()` 가 Python `round()` 와 같은 방식이다.
  "직관적 반올림"으로 바꾸면 정답 JSON과 어긋난다 (예: 90,999ms → 2분)
- **DST 갭은 `ZonedDateTime.of()` 로 풀지 않는다.** 없는 시각은 전환 후 첫 유효 시각
  (`02:30 → 03:00`), 겹치는 시각은 먼저 오는 오프셋이다. `ZonedDateTime.of()` 는 갭에서
  `03:30` 을 만들어 30분 어긋난다. 그래서 `Windows.kt` 가 `ZoneRules` 를 직접 본다
- **집계 경계를 프로필로 다시 계산해 대조한다** (`AnalysisInput` 검증). 없으면 1분짜리 구간에
  빈 앱 목록을 넣어 하루 전체를 '확인된 0'으로 위조할 수 있다
- **개별 앱 시간은 구간 길이를 넘을 수 없지만 합계는 넘을 수 있다** (멀티윈도우)
- **`Json.kt` 는 자동 매핑이 아니다.** `null` 과 필드 부재를 구분하려고 수동으로 매핑한다.
  모델에 필드를 추가하면 `inputFromJson`/`outputToJson` 도 같이 고쳐야 한다 — 빠뜨리면 조용히 빠진다
- **문장 회전은 주차 기준 결정적이다** (`rotationSeed`). 같은 주는 항상 같은 문장이 나온다

## 규칙을 바꿀 때

1. Kotlin 코드를 고친다
2. `./gradlew test` 로 어떤 기대값이 바뀌는지 본다
3. 바뀐 게 의도한 변화면 `contracts/examples/*.output.json`·`fixtures.json` 을 새 결과로 갱신하고,
   `Models.kt` 의 `RULES_VERSION` 을 올린다
4. FE `android/app/src/main/java/com/petox/screentime/` 에 다시 복사한다

정답 JSON은 사람이 검토한 기대값이다. 테스트를 통과시키려고 기계적으로 덮어쓰지 마라.

## 한계

- **합성 데이터로만 검증했다.** 실제 사용자 행동 개선 효과를 입증한 것이 아니다
- **원시 Android 이벤트는 여기서 다루지 않는다.** 이벤트 → 구간 정규화는 FE 수집기 몫이고
  (`contracts/android-data-contract.md`), F13/F14/F15/F22 는 실기기에서 확인해야 한다
- 예제 대조는 정상 주·데이터 부족 주 2건뿐이다. 새 엣지 케이스는 예제나 fixtures에 추가해야 회귀를 잡는다
- 통계적 유의성, 중독, 실제 잠든 시각, 의지 부족을 사용 기록으로 판단하지 않는다
