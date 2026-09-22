# 펫톡스 주간 대시보드 API·화면 데이터 명세

- 문서 버전: `1.0`
- 분석 schema: `1`
- 분석 rules: `2026-09-10.1`
- 대상: Android FE 개발자, UI/UX 디자이너, 디자인 에이전트
- 범위: **주간 대시보드 화면**과 화면에서 발생하는 목표 제안 선택

> 이 문서의 API는 **Android 앱 내부의 화면 데이터 계약**이다.
> 분석은 Kotlin으로 기기 안에서 실행하며, 대시보드를 그리기 위해 서버 HTTP API를 호출하지 않는다.
> 아래의 REST 모양 경로는 디자인·mock 도구에서 식별자로 쓸 수 있는 가상 경로일 뿐이다.

---

## 1. 제품 경계

```text
UsageStatsManager / Room
  → AnalysisInput
  → Kotlin analyze()
  → AnalysisOutput
  → DashboardMapper (표시용 파생값·앱 이름/아이콘 결합)
  → DashboardUiState
  → 주간 대시보드 화면
```

- 원시 사용 이벤트, 화면 프레임, 알림 본문, URL, 원시 Activity 이름은 화면 계약과 서버에 포함하지 않는다.
- 시간 계산·주간 비교·미션 판정·목표 제안·설명 문장은 UI에서 다시 계산하지 않는다.
- 모든 시간 원본 단위는 정수 밀리초(`Long`)다. UI에서만 시간/분으로 변환한다.
- `null`은 **확인 불가**, `0`은 **확인된 0**이다. UI에서 둘을 같은 값으로 표현하지 않는다.
- 앱 이름과 아이콘은 Android `PackageManager`가 로컬에서 결합한다. 분석 결과에는 `package_name`만 있다.
- 선택적 계정 백업은 별도 기능이다. 대시보드 표시의 선행 조건이 아니다.

### 정본 파일

| 목적 | 파일 |
|---|---|
| Android 수집·품질 계약 | [`../../screentime_analysis/contracts/android-data-contract.md`](../../screentime_analysis/contracts/android-data-contract.md) |
| 분석 출력 JSON Schema | [`../../screentime_analysis/contracts/output.schema.json`](../../screentime_analysis/contracts/output.schema.json) |
| 정상 주간 예제 | [`../../screentime_analysis/contracts/examples/complete-week.output.json`](../../screentime_analysis/contracts/examples/complete-week.output.json) |
| 데이터 부족 예제 | [`../../screentime_analysis/contracts/examples/insufficient-data.output.json`](../../screentime_analysis/contracts/examples/insufficient-data.output.json) |
| Kotlin 화면 전 분석 진입점 | `kotlin_port/src/main/kotlin/com/petox/screentime/Pipeline.kt` |

정본과 이 문서가 충돌하면 `output.schema.json`과 Kotlin 모델을 우선한다.

---

## 2. 화면 구조

디자인은 다음 8개 구역을 기준으로 한다.

1. **주 선택 헤더** — 선택 주, 이전/다음 주 이동, 주간 상태, 마지막 수집 시각
2. **이번 주 한줄 요약 카드** — `analysis.insights[0].text`를 최상단 핵심 문장으로 표시
3. **핵심 지표 카드** — 선택 앱 합계, 일평균, 야간 평균, 전주 비교
4. **일별 사용 그래프** — 전체 앱과 선택 앱을 나란히 표시
5. **야간 사용 그래프** — 취침 전 30분과 취침 후 사용량을 누적 또는 분리 표시
6. **앱별 상세** — 앱 이름, 시간, 비중, 전주 증감
7. **미션 성과** — 일일/야간 달성·미달성·확인 불가 현황
8. **추가 인사이트·다음 목표** — 나머지 template 설명과 목표 제안 수락/수정/유지

하나의 긴 스크롤 화면을 기본으로 한다. 상세 화면을 새로 만들지는 디자인 결정에 맡기되,
이 명세에 없는 데이터를 요구하는 UI는 제안 단계에서 표시해야 한다.

---

## 3. 화면 조회 API

### 3.1 제품 코드의 논리 인터페이스

```kotlin
interface WeeklyDashboardRepository {
    suspend fun getWeek(weekStart: LocalDate): DashboardUiState
    suspend fun refresh(weekStart: LocalDate): DashboardUiState
    suspend fun decideProposal(input: ProposalDecisionInput): ProposalDecisionResult
}
```

### 3.2 디자인·mock 도구용 가상 경로

```http
GET  /design-mock/v1/dashboard/weeks/{week_start}
POST /design-mock/v1/dashboard/weeks/{week_start}/proposal-decisions
```

이 경로를 실제 BE endpoint로 구현하지 않는다.

### 3.3 조회 요청

| 항목 | 타입 | 필수 | 규칙 |
|---|---|---:|---|
| `week_start` | `YYYY-MM-DD` | 예 | 월요일이어야 함 |
| `refresh` | boolean | 아니오 | `true`면 로컬 수집 후 다시 분석. 정확한 완료 시각을 보장하지 않음 |

### 3.4 `DashboardUiState`

```json
{
  "screen_version": "1",
  "week": {
    "week_start": "2026-09-07",
    "week_end": "2026-09-13",
    "is_current_week": false,
    "week_status": "ready",
    "last_collection_attempt_ms": 1789326000000
  },
  "analysis": {
    "schema_version": "1",
    "rules_version": "2026-09-10.1",
    "metrics": {},
    "mission_results": [],
    "proposals": [],
    "insights": []
  },
  "display_apps": {
    "com.example.video": {
      "label": "동영상 앱",
      "icon_key": "package:com.example.video",
      "purpose_label": "여가"
    }
  },
  "active_targets": {
    "daily_target_ms": 6480000,
    "night_target_ms": 1620000,
    "daily_is_temporary": false,
    "night_is_temporary": false
  },
  "capabilities": {
    "can_refresh": true,
    "can_accept_proposal": true,
    "needs_usage_access": false
  }
}
```

`analysis`의 내부 필드는 별도의 UI용 축약 응답이 아니라 Kotlin `AnalysisOutput` 전체다.
정상 응답 예시는 `complete-week.output.json`, 부족 응답 예시는
`insufficient-data.output.json`을 그대로 사용한다.

---

## 4. 필드 명세와 화면 매핑

### 4.1 `week`

| 필드 | 타입 | 화면 의미 |
|---|---|---|
| `week_start` | date | 선택 주 월요일 |
| `week_end` | date | 선택 주 일요일. `week_start + 6일` |
| `is_current_week` | boolean | 진행 중 배지 및 다음 주 이동 제한 판단 |
| `week_status` | enum | 아래 상태별 화면 분기 |
| `last_collection_attempt_ms` | `Long?` | 마지막 수집 시도 시각. `null`이면 "아직 수집하지 않음" |

#### `week_status`

| 값 | 사용자 문구 | UI 처리 |
|---|---|---|
| `in_progress` | `이번 주 진행 중` | 확보된 값만 표시. 확정 주간 성과처럼 표현하지 않음 |
| `awaiting_data` | `최근 기록을 확인하는 중` | refresh CTA 제공. 누락값을 0으로 표시하지 않음 |
| `ready` | `주간 분석 완료` | 모든 분석·비교·제안 구역 표시 가능 |
| `insufficient_data` | `분석할 기록이 부족해요` | 확보된 값 + 부족 안내. 자동 목표 제안이 없을 수 있음 |

### 4.2 `analysis.metrics`

| 필드 | 타입 | 화면 위치 | 표시 규칙 |
|---|---|---|---|
| `valid_days` | int | 헤더/데이터 품질 | `분석 가능한 날 N/7` |
| `valid_nights` | int | 헤더/데이터 품질 | `분석 가능한 야간 N/7` |
| `all_apps_total_ms` | `Long?` | 요약·일별 그래프 | `null`이면 `확인 불가` |
| `selected_total_ms` | `Long?` | 핵심 요약 | 선택한 앱들의 주간 합계 |
| `selected_daily_mean_ms` | `Double?` | 핵심 요약 | 7일 complete일 때만 값 존재 |
| `selected_night_mean_ms` | `Double?` | 핵심 요약 | 7개 야간 complete일 때만 값 존재 |
| `pre_bed_total_ms` | `Long?` | 야간 그래프 | 취침 전 30분 합계 |
| `after_bed_total_ms` | `Long?` | 야간 그래프 | 목표 취침 이후 합계 |
| `daily_success_count` | int | 미션 성과 | 일일 성공 횟수 |
| `daily_evaluable_count` | int | 미션 성과 | 일일 성공+실패 분모 |
| `night_success_count` | int | 미션 성과 | 야간 성공 횟수 |
| `night_evaluable_count` | int | 미션 성과 | 야간 성공+실패 분모 |
| `per_day` | array | 일별·야간 그래프 | 날짜순 7개 |
| `per_app` | array | 앱별 상세 | 시간순 정렬 결과 |
| `comparison` | object | 전주 비교 | `comparable=false`면 증감률 숨김 |

#### `comparison`

```json
{
  "comparable": true,
  "reason": null,
  "selected_delta_ms": -7200000,
  "selected_delta_pct": -12.5,
  "all_apps_delta_ms": 1800000
}
```

- 음수는 감소, 양수는 증가다.
- `selected_delta_pct=null`을 `0%`로 표시하지 않는다.
- `comparable=false`이면 `reason`을 UI 메시지 키로 사용한다.
- 이유 문구의 기본 fallback은 `비교할 이전 주 데이터가 부족해요`다.
- 비교 불가인데 색상·화살표로 증가/감소를 암시하지 않는다.

### 4.3 `per_day[]`

```json
{
  "date": "2026-09-07",
  "daily_quality": "complete",
  "pre_bed_quality": "complete",
  "after_bed_quality": "complete",
  "all_apps_ms": 9600000,
  "selected_ms": 7200000,
  "pre_bed_ms": 1200000,
  "after_bed_ms": 600000
}
```

| quality | 그래프 규칙 |
|---|---|
| `complete` | 실선/일반 막대. `0`이면 높이 0인 **확인된 값** |
| `partial` | 빗금/점선. tooltip에 `일부 기록만 확인됨` |
| `unavailable` | 빈칸 또는 끊긴 축. **0 높이 막대 금지** |
| quality 자체가 `null` | 해당 야간 구간이 요청 범위에 없음을 의미. 빈칸 처리 |

- 일별 그래프에서 `all_apps_ms`와 `selected_ms`는 겹치지 않는 두 막대로 오해하게 하지 않는다.
  선택 앱은 전체 앱 합계에 포함되는 부분집합이다.
- `pre_bed_ms`와 `after_bed_ms`는 같은 야간의 구성 요소이므로 누적 막대 사용 가능하다.
- `partial` 값은 화면에 보여줄 수 있지만 확정 합계·성공률에 포함된 값처럼 강조하지 않는다.

### 4.4 `per_app[]`

```json
{
  "package_name": "com.example.video",
  "is_target": true,
  "total_ms": 50400000,
  "share_pct": 75.0,
  "night_total_ms": 12600000,
  "night_share_pct": 100.0,
  "delta_ms": null,
  "delta_pct": null
}
```

표시 우선순위:

1. `display_apps[package_name].label`
2. 조회 실패 시 `package_name`

아이콘은 `icon_key`로 로컬 조회한다. 아이콘 조회 실패 시 공통 앱 placeholder를 사용한다.
`is_target=true`에는 `관리 중` 배지를 붙일 수 있다.

- `share_pct`: 전체 앱 합계에서 해당 앱의 비중
- `night_share_pct`: **선택 앱 야간 합계**에서 해당 선택 앱의 비중. 비선택 앱은 `null`
- `delta_pct=null`: 증감 배지 자체를 숨기고 `0%`로 표시하지 않음

### 4.5 `mission_results[]`

| status | 사용자 문구 | 권장 시각 상태 |
|---|---|---|
| `in_progress` | `진행 중` | neutral/progress |
| `succeeded` | `달성` | positive |
| `failed` | `미달성` | caution. 처벌·비난 문구 금지 |
| `unknown` | `확인 불가` | neutral/hatched |
| `not_applicable` | `해당 없음` | muted |

`daily_evaluable_count`와 `night_evaluable_count`가 0이면 성공률을 계산하거나
`0% 달성`으로 쓰지 않는다. `판정 가능한 미션이 없어요`라고 표시한다.

`unknown`, `in_progress`, `not_applicable`은 성공률 분모에서 제외한다.
예: 성공 2, 실패 0, unknown 5는 `2/2 달성 · 5일 확인 불가`이지 `주간 100% 달성`이 아니다.

### 4.6 `insights[]` — 한줄 요약

```json
{
  "code": "NIGHT_TOP_APP",
  "evidence": {
    "package_name": "com.example.video",
    "night_total_ms": 12600000,
    "night_share_pct": 100.0
  },
  "text": "야간 구간에서 가장 많이 사용한 앱은 …",
  "source": "template"
}
```

#### 메인 한줄 요약 카드

- 대시보드 상단에서 `analysis.insights[0].text`를 **이번 주 한줄 요약**으로 표시한다.
- 카드 제목 권장안: `이번 주 한줄 요약` 또는 `이번 주 사용 패턴`.
- 문장은 서버나 생성형 LLM이 아니라 Kotlin 분석 결과에 기반한 결정론적 template이다.
  따라서 `AI가 생성함`, `생성형 AI 요약` 같은 배지를 붙이지 않는다.
- `insights=[]`이면 카드를 숨긴다. UI가 임의 문장을 생성하거나 외부 AI를 호출하지 않는다.
- 한 문장이 길어져도 중간을 말줄임표로 숨기지 않는다. 기본 2~3줄까지 허용하고 전체 문장을 읽을 수 있어야 한다.
- `INSUFFICIENT_DATA`도 유효한 한줄 요약이다. 이 경우 부족 상태 안내와 중복되지 않도록
  상태 banner 또는 한줄 요약 카드 중 한 곳에서 문장을 대표 노출한다.
- 두 번째 이후 항목(`insights[1..]`)은 `추가 분석` 영역에 카드 또는 목록으로 표시한다.

#### 데이터 사용 규칙

- 화면에는 `text`를 그대로 표시한다. UI에서 숫자를 재계산해 문장을 덮어쓰지 않는다.
- `source`는 항상 `template`이며 사용자에게 `AI 생성` 배지를 붙이지 않는다.
- `evidence`는 QA·accessibility 설명 연결용이다. 사용자에게 raw JSON을 노출하지 않는다.
- 가능한 `code`:
  - `SELECTED_USAGE_DECREASED`
  - `OTHER_APPS_INCREASED`
  - `NIGHT_TOP_APP`
  - `DAILY_NIGHT_DIFFERENCE`
  - `INSUFFICIENT_DATA`

### 4.7 `proposals[]`

```json
{
  "kind": "daily",
  "target_ms": 6480000,
  "reason_code": "INITIAL_BASELINE",
  "basis_week": "2026-09-07",
  "profile_version": 1,
  "rules_version": "2026-09-10.1"
}
```

- 제안은 활성 목표가 아니다. 사용자가 선택하기 전까지 현재 미션을 바꾸지 않는다.
- `kind`: `daily` 또는 `night`
- `target_ms=null`이면 새 숫자 목표를 제안하지 않는다는 뜻이다. CTA를 억지로 만들지 않는다.
- 화면 CTA:
  1. `이 목표로 시작` (`accept`)
  2. `직접 수정` (`edit`)
  3. `현재 목표 유지` (`keep`)
- 수락 또는 수정 시 적용 시점을 반드시 보여준다. 이미 시작한 구간에는 소급 적용하지 않는다.

---

## 5. 목표 제안 결정 API

### 요청: `ProposalDecisionInput`

```json
{
  "basis_week": "2026-09-07",
  "kind": "daily",
  "profile_version": 1,
  "rules_version": "2026-09-10.1",
  "decision": "accept",
  "target_ms": 6480000
}
```

| 필드 | 타입 | 규칙 |
|---|---|---|
| `basis_week` | date | 원 제안과 같아야 함 |
| `kind` | `daily \| night` | 원 제안과 같아야 함 |
| `profile_version` | int | 현재 프로필과 같아야 함 |
| `rules_version` | string | 원 제안과 같아야 함 |
| `decision` | `accept \| edit \| keep` | 사용자 선택 |
| `target_ms` | `Long?` | `accept`: 제안값, `edit`: 사용자 수정값, `keep`: `null` |

동일 결정의 중복 저장 방지 키:

```text
(basis_week, kind, profile_version, rules_version)
```

### 응답: `ProposalDecisionResult`

```json
{
  "saved": true,
  "decision": "accept",
  "active_target_ms": 6480000,
  "effective_from_anchor_date": "2026-09-14",
  "message": "다음 시작 전 구간부터 적용돼요"
}
```

- 월요일 정오에 일일 목표를 수락해도 이미 시작한 월요일 일일 미션은 바뀌지 않는다.
- 다음 미시작 일일/야간 구간부터 적용한다.
- `keep`이면 기존 활성 목표를 유지한다.
- 저장 실패 시 현재 목표를 변경하지 않고 재시도 가능 상태를 보여준다.

---

## 6. 화면 상태 우선순위

아래 순서에서 먼저 일치하는 상태를 화면의 최상위 상태로 사용한다.

| 순위 | 조건 | 화면 |
|---:|---|---|
| 1 | `capabilities.needs_usage_access=true` | 사용 정보 접근 안내. 수치 dashboard를 가짜 0으로 채우지 않음 |
| 2 | 최초 수집 중이며 표시 가능한 값 없음 | loading skeleton + `기록을 불러오는 중` |
| 3 | `week_status=awaiting_data` | 마지막 수집 시각 + refresh CTA |
| 4 | `week_status=insufficient_data` | 부족 안내 + 확인된 값만 표시 |
| 5 | `week_status=in_progress` | 진행 중 배지 + 현재 확보값 |
| 6 | `week_status=ready` | 완료 dashboard |
| 7 | 로컬 분석 예외 | error + 다시 시도. 빈 성공 화면으로 치환 금지 |

### 로딩

- 기존 snapshot이 있으면 전체 skeleton으로 덮지 말고 기존 값을 유지하면서 refresh indicator만 표시한다.
- WorkManager는 정확한 실행 시각을 보장하지 않으므로 `매시 정각 업데이트` 같은 문구를 쓰지 않는다.

### 데이터 부족

- null 시간은 `—` 또는 `확인 불가`로 표시한다.
- 그래프는 해당 날짜를 빈칸/빗금으로 표시한다.
- 목표 제안이 비어 있으면 빈 CTA container를 남기지 않는다.
- `INSUFFICIENT_DATA` insight를 화면 상단 안내로 승격할 수 있다.

### 오류

화면에서 구분해야 하는 최소 오류:

| 오류 | 사용자 행동 |
|---|---|
| 사용 정보 접근 권한 없음 | `권한 설정 열기` |
| 로컬 수집 실패 | `다시 시도` |
| 분석 입력 검증 실패 | 일반 사용자에게 내부 필드명을 노출하지 않고 `기록을 다시 확인해 주세요` |
| 목표 결정 저장 실패 | 현재 목표 유지 + `다시 시도` |

---

## 7. 포맷 규칙

### 시간

- 내부: 밀리초
- 1분 미만의 양수: `1분 미만`
- 1~59분: `N분`
- 60분 이상: `N시간 M분`; `M=0`이면 `N시간`
- `null`: `확인 불가`
- `0`: `0분`

### 퍼센트

- 최대 소수점 1자리: `12.5%`
- 정수이면 `.0` 생략 가능: `75%`
- `null`: 숨김 또는 `비교 불가`; `0%`로 치환 금지
- 감소/증가 색상만으로 의미를 전달하지 말고 `감소`, `증가` 텍스트를 병기한다.

### 날짜

- 주 헤더: `9월 7일–9월 13일`
- 일별 그래프: `월 7`, `화 8`처럼 요일을 반드시 표시
- 과거 주를 현재 설정으로 재평가하지 않는다.

### 접근성

- 그래프의 각 막대에 날짜·품질·전체 시간·선택 시간 content description을 제공한다.
- 달성/실패/확인 불가를 색상만으로 구분하지 않는다.
- 앱 아이콘에 앱 이름과 동일한 중복 설명을 붙이지 않는다.
- tap target은 Android 권장 최소 크기를 따른다.

---

## 8. 디자인 검수 시나리오

| ID | 입력 상태 | 디자인에서 확인할 것 |
|---|---|---|
| D01 | `complete-week.output.json` | ready 전체 화면, **상단 한줄 요약**, 7일 그래프, 앱 2개, 제안 2개 |
| D02 | `insufficient-data.output.json` | `INSUFFICIENT_DATA` 한줄 요약, 모든 날짜 unavailable, 0 막대 금지, 부족 안내 중복 방지 |
| D03 | `week_status=in_progress` | 진행 중 배지, 확정 주간 성과처럼 표현하지 않음 |
| D04 | `week_status=awaiting_data` | refresh CTA와 마지막 수집 시각 |
| D05 | comparison `comparable=false` | 증감 화살표·0% 숨김, 비교 데이터 부족 문구 |
| D06 | 미션 `2 succeeded / 0 failed / 5 unknown` | `2/2 · 확인 불가 5`, `100% 주간 달성` 금지 |
| D07 | `partial` 하루 + `unavailable` 하루 | 빗금과 빈칸을 서로 구분 |
| D08 | 앱 이름 조회 실패 | package name fallback + placeholder 아이콘 |
| D09 | `proposals=[]` | 빈 CTA 영역 제거, 현재 목표 유지 문구 |
| D10 | 목표 수정 후 저장 실패 | 기존 목표 유지, 재시도 제공 |
| D11 | 사용 정보 접근 없음 | permission 화면, 가짜 사용량 0 금지 |
| D12 | 큰 글꼴/스크린리더 | 카드·그래프·CTA 순서와 의미 유지 |

### 디자이너가 임의로 만들면 안 되는 지표

- 중독 점수, 건강 점수, 의지 점수
- 실제 수면 시간 또는 잠든 시각
- 물리적인 화면 켜짐 시간
- 통계적 유의성
- 생성형 AI가 만든 것처럼 보이는 배지
- 확인 불가 데이터를 0으로 바꾼 합계·달성률

---

## 9. 디자인 인계용 한 페이지 요약

```text
화면: 주간 대시보드 1개, 세로 스크롤
최상단: analysis.insights[0].text를 `이번 주 한줄 요약` 카드로 표시
핵심: 선택 앱 사용량 / 야간 사용량 / 미션 성과 / 다음 목표
상태: in_progress / awaiting_data / ready / insufficient_data
품질: complete / partial / unavailable
미션: 진행 중 / 달성 / 미달성 / 확인 불가 / 해당 없음
그래프: 누락일을 0 막대로 표현하지 않음
문장: insights[].text 그대로, source=template. 생성형 AI 배지 금지
목표: 제안은 자동 적용 금지. 수락/수정/유지 후 다음 미시작 구간부터 적용
보안: 분석은 전부 온디바이스. 서버가 없어도 dashboard 동작
mock: complete-week.output.json + insufficient-data.output.json
```
