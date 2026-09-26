# 한줄 요약 SLM 앱 연결 설계 (시연용)

2026-09-25 · 상태: 설계 승인 (2026-09-26, "AI" 표시 제외)

## 목표

v2 모델(`slm_summary/models/ft-v2-q4.gguf`, 541MB)을 FE 앱 대시보드에 붙여 **실기기에서 시연**한다.
한줄 요약 카드의 문장을 반려견 말투로 바꾸고, 제목을 `초코의 한줄 요약`처럼 반려견 이름으로 단다.
폰에서 불러오기·생성 시간과 메모리를 재서 루트 README 의 "앱 번들 SLM 기각" 결정을 다시 볼 근거로 삼는다.

```
분석기(Kotlin, 변경 없음) → insights[0] 템플릿 문장 ─┬─ 즉시 표시
                                                  └─ SLM 생성 → 검사 통과 → 교체
                                                                 실패 → 템플릿 유지
```

## 범위

| 포함 | 제외 (필요해지면 추가) |
|---|---|
| `insights[0]` 한 문장만 SLM 으로 바꾸기 | `insights[1..]` 변환 (화면에 안 나온다) |
| 출력 검사, 실패 시 템플릿 대체 | 모델 다운로드 (v3 이후, 배포 시) |
| 제목에 반려견 이름 | RAM 기준 기기 판별 (실측 뒤 기준을 정한다) |
| 모델 adb 배치 (디버그 빌드) | 설정에서 끄기, 모델 상주 캐시 |
| 실기기 속도·메모리 측정 | "AI" 표시·사전 고지 문구 (출시 때, 아래 「결정」) |

## 결정

- **분석기와 출력 계약은 바꾸지 않는다.** `kotlin_port` 는 계속 템플릿만 만들고 `insight.source` 는 `"template"` 고정이다.
  SLM 은 FE 표시 단계의 선택 계층이라 빼면 지금 앱과 같다. 설계 원칙 6(중급기)과 충돌하지 않는 이유다.
- **런타임은 `llama.rn`** (MIT, llama.cpp 바인딩). 동봉된 llama.cpp 가 `qwen35` 아키텍처를 지원함을 확인했다
  (`vendor/llama.cpp/src/llama-arch.cpp`). FE 는 React Native 0.87, New Architecture.
- **검사·조사 채우기는 TS 로 옮긴다.** Python 정본(`slm_summary/bench.py`, `data.py`)과의 일치는 대조 JSON 으로 테스트한다.
- **"AI" 표시는 시연에서 뺀다.** 시연은 상용 서비스가 아니고 과태료 계도기간(최소 1년) 중이다. **출시 때는 필요하다:**
  인공지능기본법 제31조 제2항(생성형 AI 결과물 표시)과 제1항(사전 고지). 서비스 안에서만 보이는 결과물은
  화면 안내·로고 등 유연한 표시가 허용되므로 제목 옆 작은 "AI" 와 약관·온보딩 고지 한 줄이면 된다고 본다.
  출시 전 인공지능기본법 지원데스크에 확인한다.

## FE 변경 (`PETOX-MJU/FE`, 브랜치 `feat/slm-summary`)

| 파일 | 내용 |
|---|---|
| `src/features/screentime/slmCheck.ts` (새) | 순수 함수: `toFact`, `check`, `meaningErrors`, `markerErrors`, `hasBatchim`, `fill`. 네이티브 import 없음 |
| `src/features/screentime/slm.ts` (새) | llama.rn 호출: 불러오기 → 생성 → 검사 → 해제. `rewriteSummary()` 하나만 내보낸다 |
| `src/features/screentime/dashboard.ts` | `AnalysisOutput.insights` 에 `evidence` 추가 |
| `src/screens/ScreentimeDashboardScreen.tsx` | 제목에 반려견 이름, 따옴표 제거, SLM 문장 교체 |
| `package.json` | `llama.rn` 추가 |
| `__tests__/slmCheck.test.ts` (새) | 대조 JSON 으로 Python 판정과 일치 확인, `toFact` 단위 테스트 |

### 생성 흐름

1. 분석 결과가 오면 템플릿 문장을 바로 표시한다.
2. **사실 만들기 (`toFact`):** `insights[0].text` 를 그대로 쓰되, `NIGHT_TOP_APP` 이면 문장 속 `evidence.package_name` 을
   `{앱}` 으로 바꾼다. 분석기는 패키지명을 문장에 넣고, 모델은 `{앱}` 으로 학습했다.
3. **생성:** 학습·평가와 같은 형식이어야 v2 평가 결과가 유지된다.
   - 메시지: system = `data.SYSTEM` 원문, user = `사실: {fact}`
   - `jinja: true`(평가의 `--jinja`), `enable_thinking: false`, `n_predict 80`, `temperature 0.5`, `n_ctx 512`, 4스레드
   - `seed` = 리포트 주 시작일(`per_day[0].date`)의 epoch day. 같은 주는 같은 문장이 나온다.
4. **검사:** `check`(빈 출력·숫자·여러 문장·90자 초과·외국 문자·금지어) + `meaningErrors`(단위·방향·"모두 달성")
   + `markerErrors`(`{앱}` 개수, 잘못된 중괄호). 하나라도 걸리면 실패.
5. **통과:** `fill(out, 표시명)` 으로 이름·조사를 넣어 교체한다. 표시명은 `APP_META` 이름, 없으면 패키지명.
6. **해제:** 성공·실패와 상관없이 `finally` 에서 모델을 해제한다.

### 템플릿을 유지하는 경우

모델 파일 없음, 불러오기 오류, 15초 초과, 검사 실패, 화면 이탈(취소). 어떤 경우도 오류 화면을 띄우지 않고
`console.warn` 한 줄(원인)만 남긴다.

### 화면

- 제목 스티커: `${이름}의 한줄 요약`. 이름은 `loadPetProfile()?.name` (온보딩에서 지은 이름, 계정별 AsyncStorage).
  비었거나 로그인 전·프로필 없음이면 `한줄 요약`. 8자 넘으면 8자 + `…`. 템플릿 문장일 때도 같은 제목(깜빡임 방지).
- 문장: 따옴표 없이 표시한다 (템플릿·SLM 공통).

### 모델 배치 (시연용)

```bash
adb push ft-v2-q4.gguf /data/local/tmp/
adb shell run-as com.petoxmju.petox cp /data/local/tmp/ft-v2-q4.gguf files/
```

앱은 `/data/data/com.petoxmju.petox/files/ft-v2-q4.gguf` 를 고정 경로로 읽는다 (`ponytail:` 주석 — 배포 때 다운로드로 교체).

## AI 저장소 변경

- `slm_summary/export_cases.py` (새): 대조 JSON 생성. v2 평가 결과(세트 A·B)의 통과·실패 출력 +
  일부러 망가뜨린 출력(숫자 교체, 방향 뒤집기, `{앱}` 삭제)과 Python 판정, `fill` 사례(치지직, 아프리카TV, YouTube 등).
  생성물은 FE `__tests__/fixtures/slmCases.json` 으로 복사한다.
- 루트 README "온디바이스 LLM — 검토했고 도입하지 않는다" 절: 실측값을 넣어 "선택 기능, 템플릿이 항상 대체 경로"로 고친다.
  실기기 측정 뒤에 쓴다.
- 대시보드 명세의 "생성형 AI 배지 금지" 규칙: 정본 위치(FE 쪽 여부)를 확인한 뒤 고친다.
  AI 저장소 루트의 `dashboard-api-spec.md` 는 커밋되지 않은 로컬 파일이라 건드리지 않는다.

## 테스트

1. **jest 대조:** TS 검사 판정·`fill` 결과가 대조 JSON 의 Python 결과와 전부 같다.
2. **`toFact` 단위:** `NIGHT_TOP_APP` 패키지명 → `{앱}`, 다른 코드는 원문 그대로.
3. **에뮬레이터(Pixel_8):** 모델 있음 → 이름 제목 + SLM 문장(logcat 에 생성 성공 로그). 모델 파일 삭제 → 템플릿 문장. 스크린샷으로 확인.
4. **실기기:** 불러오기 시간, 생성 시간(tok/s), 메모리 최대치(`dumpsys meminfo`). 폰 연결이 필요하다.

## 위험

- **메모리:** 예전 측정(Qwen 0.5B)에서 추론 중 RAM 약 1.36GB. 중급기에서 앱이 종료될 수 있어 실측이 이 시연의 핵심 산출물이다.
- **에뮬레이터 속도는 실기기를 대표하지 않는다.** 동작 확인용으로만 쓴다.
- **v2 남은 오류:** 틀 섞임 1/97 은 자동 검사에 안 걸린다. 시연 중 드물게 뜻이 흐린 문장이 나올 수 있다 (v3 에서 고친다).
