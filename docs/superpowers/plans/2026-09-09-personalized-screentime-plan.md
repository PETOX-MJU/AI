> **⚠️ 이 계획서는 완료된 작업의 기록이다. 이후 아키텍처 결정으로 일부가 무효화됐다.**
>
> | 이 문서의 서술 | 현재 결정 |
> |---|---|
> | BE가 분석 패키지를 호출한다 | **앱에서 Kotlin 이식본이 실행한다.** BE는 계정 동기화·백업만 |
> | 분석 서버 전송 동의 | 분석은 기기 안에서 끝난다. 서버 전송 동의 항목 없음 |
> | 외부 AI 제공자는 아직 선택되지 않았다 | **생성형 AI는 도입하지 않기로 확정.** 템플릿이 최종 설계 |
>
> 현재 유효한 아키텍처는 [루트 README](../../../README.md) 와
> [`kotlin-port.md`](../../../screentime_analysis/contracts/kotlin-port.md) 를 따른다.
> Python 패키지의 **계산 규칙은 계속 유효하다** — 무효가 된 것은 실행 위치와 AI 계획뿐이다.

# AI 담당자용 스크린타임 분석 라이브러리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Claude 실행 안내: 위 스킬이 설치되어 있지 않으면 동일한 작업 순서와 검증 기준을 일반 도구로 수행한다. 스킬 설치 때문에 구현을 중단하지 않는다. 이 문서를 전달받은 Claude가 코드 작성자이며, 제품에서 Claude API를 사용하라는 의미는 아니다.

**Goal:** 백엔드가 전달하는 사용 시간 집계로 주간 분석, 개인 기준선, 맞춤 미션 후보, 규칙 기반 판정 결과와 한국어 설명을 반환하는 Python 분석 라이브러리를 구현한다.

**Architecture:** FE가 Android 사용 기록을 수집하고 BE가 사용자·동의·기록·일정을 관리한다. AI 담당자는 BE가 호출할 수 있는 무상태 Python 패키지와 입력·출력 JSON Schema, 합성 데이터, 평가 테스트를 전달한다. 이 패키지는 HTTP 서버, DB, 인증, 스케줄러 없이 실행되며 결과의 저장·노출·미션 활성화는 BE와 FE가 담당한다.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, Ruff, build. FastAPI·Uvicorn·HTTPX·DB 드라이버는 이 패키지의 의존성에 넣지 않는다.

**Spec:** 이 문서의 1~10절이 제품 맥락·분석·연동 명세이며, 11~14절이 AI 담당자의 Python 구현 계획·완료 기준이다. 3~4절의 Android 동작과 사용자 데이터 운영은 FE/BE 전달 요구사항이며 AI 코드 작성자가 구현할 범위가 아니다. 다른 대화 내용을 읽지 않아도 구현 가능해야 한다.

## Global Constraints

- 이 문서는 구현 계획서다. 작성 시점에는 제품 코드를 생성하거나 실행하지 않았다.
- 기존 저장소는 `PETOX-MJU/AI`의 모델 학습·변환용이다. 루트 README는 온디바이스 우선과 FE/BE 별도 저장소를 명시한다.
- 이번 Python 분석 라이브러리는 대화에서 선택한 **별도 MVP 설계**다. 기존 펫톡스의 온디바이스 정책이 변경되었다고 해석하지 않는다. 기존 모델·캡처·픽셀화 코드를 수정하지 않는다.
- 사용자 최종 역할은 **AI 담당자이며 백엔드는 다른 사람이 담당**한다. 구현 범위는 Python 분석 라이브러리·설명 로직·평가·연동 계약이다. HTTP 서버·API 라우터·인증·DB·배포·Android 코드를 생성하지 않는다.
- 현재 AI 저장소의 신규 `screentime_analysis/` 아래만 구현하고 Python wheel로 BE에 전달한다. BE 저장소나 인프라를 이 작업에서 수정하지 않는다.
- UI 언어는 한국어. 하나의 기기·하나의 로컬 프로필을 MVP 범위로 한다.
- FE 연동 기준은 Android API 29 이상 이벤트 의미다. SDK·Gradle 구성은 이 Python 작업 범위 밖이다. Python 의존성은 구현 시점의 공식 호환성을 확인하고 실제 설치·검증한 버전을 잠금 파일에 고정한다.
- 사용 시간 내부 단위는 정수 밀리초, 시각은 UTC epoch milliseconds, 시간대는 IANA 식별자다. 화면에서만 분으로 표시한다.
- 데이터가 없다는 이유로 사용량을 0 또는 미션 성공으로 만들지 않는다.
- 앱 강제 차단, 화면 캡처, 접근성 서비스, 오버레이, 숏폼 분류, 보상·펫 성장, 소셜 기능, iOS는 범위 밖이다.
- 사용자 동의 없이 사용 기록을 서버 또는 외부 AI로 보내지 않는다. 서버 운영·유료 API 호출·스토어 배포는 이 문서 구현 범위에 포함하지 않는다.

---

### 담당 범위

| 담당 | 구현·전달할 것 |
|---|---|
| **AI — 사용자** | 입력 검증, 사용 패턴·기준선 분석, 미션 후보·판정 규칙, 설명 생성, Python 패키지, JSON Schema, 합성 데이터, 평가 결과 |
| **BE — 다른 담당자** | 앱용 HTTP API, 사용자 인증·인가, 동의 확인, DB, 데이터 조회·보관·삭제, AI 패키지 호출, 주간 작업 일정, 미션 수락·활성화·보고서 저장, 배포 |
| **FE — Android 담당자** | 사용 정보 접근 요청, OS 이벤트 수집·정규화, 사용 목적·일정 입력, 앱별 집계, 화면, 목표 수락 UI, 오프라인 상태 |

AI가 반환한 Proposal은 추천이며 활성 미션이 아니다. AI는 입력받은 Mission을 판정하는 순수 함수를 제공하고, BE가 기록·버전을 확인한 후 실제 서비스 상태로 저장한다. 실제 수집 여부·사용자 신원은 AI가 검증할 수 없으며 FE/BE가 보장한다.

```text
Android 수집·화면 → BE의 인증·기록 조회 → AI Python 패키지
Android 대시보드 ← BE의 결과 저장·응답 ← 분석·미션 후보·설명
```

## 1. 확정된 제품 요구사항

1. 사용자가 줄이고 싶은 앱을 직접 선택한다.
2. 사용 목적, 평일·주말 목표 취침 시각과 기상 시각을 입력받는다.
3. 취침 30분 전부터 목표 기상 시각까지 선택한 앱의 사용량을 관리한다.
4. 앱별 패턴을 분석하되 미션은 선택한 앱들의 **합산 사용 시간**으로 평가한다.
5. 일일 미션과 야간 미션을 각각 제공한다. 달성 여부는 사용 기록으로 확인한다.
6. 개인 기준선은 유효한 7일/7개 야간 구간의 평균이다. 기록이 부족하면 사용자가 입력한 임시 목표를 사용한다.
7. 목표는 주 단위로 유지한다. 다음 목표는 제안한 뒤 사용자가 수락·수정한다.
8. 전체 앱 사용 현황을 요약하고 선택한 앱을 상세 분석한다. 다른 앱의 사용 증가는 참고 정보이며 자동으로 목표 앱에 추가하지 않는다.
9. 보고서 기준은 월요일~일요일이다. 일요일 밤의 야간 구간이 월요일 아침 끝난 뒤 지난주 보고서를 확정할 수 있다.
10. 현재 진행 상황과 지난주 확정 보고서를 구분한다.
11. 생성형 AI(LLM)는 검증된 수치와 사용자 입력에 기반해 설명·미션 문구를 만든다. 목표 수치, 성공 여부, 심리·의학적 진단을 결정하지 않는다.

## 2. 확정 요구와 구분할 MVP 구현 기본값

다음 항목은 개발을 구체화하기 위해 정한 기본값이다. 검증된 행동과학 기준 또는 사용자가 직접 정한 수치로 표현하지 않는다.

| 항목 | MVP 기본값 |
|---|---|
| 초기 개인화 감축률 | 유효한 기준선보다 10% 낮은 목표 제안 |
| 목표 추가 감축 조건 | 직전 주 해당 미션의 판정 가능한 기록 7개, 달성 5개 이상 |
| 추가 감축 폭 | 직전 활성 목표에서 10% 감소, 사용자 최종 목표 아래로 내려가지 않음 |
| 감축 조건 미충족 | 현재 목표 유지 제안. 자동 완화하지 않음 |
| FE/BE 연동 권고: 동기화 | 앱 실행·복귀·수동 새로고침 + 1시간 주기 WorkManager의 지연 가능한 작업 |
| FE/BE 연동 권고: 로컬 보관 | 정규화 사용 구간 30일, 일별·야간 집계와 주간 보고서 90일 |
| 분석 모듈 | 무상태 순수 계산. 입력 데이터를 저장하거나 네트워크로 보내지 않음 |
| 백엔드 운영 | API·인증·DB·호출 일정·동의 확인은 BE 담당자가 구현 |
| 외부 생성형 AI | 제공자 미정. 기본 설명은 규칙 기반 템플릿으로 완전히 동작하며 AI 생성으로 표시하지 않음 |

단순 합계·평균·규칙 판정에는 pandas, 학습 모델, GPU, Redis, Celery, 벡터 DB를 도입하지 않는다.

## 3. 제품 흐름 — FE 연동 참고, 화면 구현 제외

### 3.1 온보딩

1. 앱의 분석 목적과 가져오는 정보 설명.
2. `사용 정보 접근 허용` 버튼으로 Android 설정 열기. 복귀 시 실제 허용 여부 재검사.
3. 최근 사용 기록 또는 조회 가능한 실행 앱 목록에서 대상 앱 선택. 앱 이름을 조회할 수 없으면 패키지명 표시.
4. 앱별 사용 목적은 `학습/업무/여가/연락/기타` 중 선택. 자유 입력은 선택사항.
5. 평일과 주말의 목표 취침·기상 시각 입력.
6. 일일·야간 각각 임시 목표와 최종 희망 목표를 분 단위로 입력. 임시 목표는 최종 목표 이상이어야 함.
7. 분석 서버 전송에 대해 별도 설명 및 동의. 동의하지 않아도 로컬 사용 현황·수동 목표 화면 사용 가능. 서버 분석 영역은 연결 안내 상태로 표시.

운영체제 사용 정보 접근 권한, 분석 서버 전송 동의, 외부 AI 전송 동의는 서로 다른 상태로 저장한다. 접근 권한 재허용으로 전송 동의를 자동 복구하지 않는다.

### 3.2 오늘

- 선택 앱 합산 사용량 / 오늘 일일 목표.
- 현재 또는 다음 야간 구간, 야간 사용량 / 목표.
- 미션 상태: `진행 중`, `달성`, `미달성`, `확인 불가`, `해당 없음`.
- 마지막 수집·분석 시각, 데이터 불완전 안내.
- 목표 초과 후 남은 시간이 음수가 되지 않게 표시한다.

### 3.3 주간 대시보드

- 주 선택, 주간 상태, 분석 가능한 일수·야간 구간 수.
- 일별 전체 앱 합계와 선택 앱 합계를 구분한 그래프.
- 앱별 시간·비중·전주 변화.
- 취침 직전 30분과 목표 취침 이후 사용량을 구분한 그래프.
- 일일·야간 미션 달성 횟수와 확인 불가 횟수.
- 근거 지표를 연결한 변화 설명 1~3개.
- 다음 목표 제안과 `수락`, `직접 수정`, `현재 목표 유지`.
- 누락일은 0 높이 막대로 그리지 않고 빈칸 또는 빗금으로 표시한다.

### 3.4 설정

- 대상 앱, 목적, 수면 일정, 최종 목표, 동의 상태 변경.
- 대상 앱·수면 일정 변경은 다음 월요일부터 적용하고 그 날짜를 화면에 표시한다. 기존 주간 목표와 판정을 소급 변경하지 않는다.
- 전체 로컬 데이터 삭제 시 예약 작업 취소, DB·캐시·프로필·동의 상태 제거. 재동의 전 재수집·전송하지 않는다.
- OS 사용 정보 접근 철회는 시스템 설정으로 안내한다. 앱이 직접 철회했다고 표시하지 않는다.

## 4. Android 데이터 생산자에게 전달할 수집·측정 명세

### 4.1 실제 데이터 출처

디지털 웰빙의 보고서·설정을 직접 읽는 것이 아니라 `UsageStatsManager`로 사용 기록을 조회한다. `PACKAGE_USAGE_STATS` 선언 후 `Settings.ACTION_USAGE_ACCESS_SETTINGS`에서 사용자가 허용해야 한다. 상세 이벤트 보관은 제한적이며 임의의 과거 전체 기록이 제공된다고 가정하지 않는다. [Android UsageStatsManager](https://developer.android.com/reference/android/app/usage/UsageStatsManager)

정확한 날짜·야간 경계의 판정은 `queryEvents()`에서 정규화한 사용 구간을 기반으로 한다. `queryUsageStats()`의 집계 구간이 요청 시간 범위와 정확히 일치한다고 가정해서 잘라 쓰지 않는다. 과거 OS 집계값을 참고 화면에 사용할 경우 `참고 통계`로 구분하며 이벤트 기반 목표 판정에 혼합하지 않는다.

### 4.2 사용 구간 정규화

- 입력: Activity 전경/배경 전환, 화면 interactive 변화, keyguard 변화, 종료·부팅 관련 이벤트.
- 같은 앱의 여러 Activity 전환 때문에 동일 시각을 중복 계산하지 않도록 앱별 Activity 상태와 구간 합집합을 관리한다.
- 앱 전경 상태이며 화면 interactive이고 잠금 상태가 아닌 구간만 이 제품의 사용량으로 계산한다.
- 종료 이벤트가 누락되거나 시작 상태를 복원할 수 없으면 불확실성을 기록한다. 새벽까지 사용했다고 임의로 연장하지 않는다.
- 현재 열린 구간은 조회 시점까지의 잠정값으로 표시하며 확정 판정에 바로 사용하지 않는다.
- 단일 앱의 겹치는 구간은 합집합. 다른 앱의 구간은 앱별로 각각 집계한다. 멀티윈도우 때문에 전체 앱 합계가 실제 경과 시간보다 클 수 있다.
- 측정 대상은 조회된 사용자 실행 앱이다. 자기 앱과 홈 런처·시스템 UI는 제외하며, 제외 목록과 판정 방식을 문서화한다. 다른 일반 앱을 이름 추측으로 제외하지 않는다.
- 백그라운드 오디오만 재생되는 시간은 이 전경 사용량에 포함하지 않는다.

이 규칙은 제품의 측정 정의다. 실제 이벤트 가용성과 동작은 Android 버전·기기에서 검증한다. 앱 사용 이벤트와 화면 상태 이벤트의 의미는 [UsageEvents.Event](https://developer.android.com/reference/android/app/usage/UsageEvents.Event)를 따른다.

화면에는 `앱 사용 시간 합계`로 표시한다. 실제 수면 시간, 물리적 화면 켜짐 시간, 디지털 웰빙과 일치하는 수치라고 표현하지 않는다.

### 4.3 수집 신뢰도

각 집계는 `complete / partial / unavailable`과 사유 코드를 갖는다.

- `complete`: 해당 구간이 끝났고, 시작 상태와 조회 범위가 복원됐으며 수집기가 알고 있는 미해결 공백이 없음.
- `partial`: 일부 시간만 확인되거나 진행 중인 구간. 확인된 사용량은 표시하되 확정 성공·기준선에는 사용하지 않음.
- `unavailable`: 권한 없음, 조회 실패, 보관 기간 초과로 복원 실패 등으로 집계 불가. 시간은 null.
- `complete`는 OS 원본이 완전하다는 절대 보증이 아니라 수집기의 확인 가능한 조건을 만족한다는 의미다.
- 허용 상태 한 번 확인 또는 빈 이벤트 배열만으로 `complete, 0`을 만들지 않는다. 조회 범위·수집 체크포인트·복원 가능한 상태가 함께 필요하다.
- 재부팅·시간 변경·시간대 변경·장기 미실행 경계는 복구 여부를 판단하고 복구하지 못하면 공백으로 기록한다.
- 같은 범위 재수집은 정규화 구간을 교체/병합하고 재집계한다. 누적 더하기로 중복 집계하지 않는다.

### 4.4 백그라운드와 패키지 이름

WorkManager는 정확한 실행 시각을 보장하지 않는다. 정시 수집·정시 월요일 보고서 알림을 약속하지 않고 다음 실행·동기화에서 갱신한다. 강제 종료나 장기 미사용으로 회복 불가능한 기록은 확인 불가로 남긴다. [PeriodicWorkRequest](https://developer.android.com/reference/androidx/work/PeriodicWorkRequest)

앱 이름·아이콘 조회의 패키지 가시성은 사용 기록 권한과 별개다. 필요한 `<queries>`를 좁게 선언하고 이름 조회 실패 시 패키지명으로 대체한다. 이 기능을 이유로 `QUERY_ALL_PACKAGES`를 기본 요청하지 않는다. [Android package visibility](https://developer.android.com/training/package-visibility)

## 5. 시간·주간 경계

### 5.1 공통

- 구간은 `[start, end)`로 계산한다. 자정 이벤트를 두 날짜에 중복 포함하지 않는다.
- 기기 시간대를 초기 프로필 시간대로 저장한다. 이미 시작한 목표·과거 보고서는 해당 프로필 버전의 시간대를 유지한다.
- 시간대·일정 변경은 다음 주부터 적용하며 과거 데이터를 다른 날짜로 이동시키지 않는다.
- UTC 저장 시각을 프로필 시간대로 변환해서 경계를 만들고 실제 경과 milliseconds를 계산한다. 하루를 무조건 86,400,000ms로 가정하지 않는다.
- DST의 존재하지 않는 로컬 시각은 전환 후 첫 유효 시각, 중복 시각은 먼저 오는 오프셋으로 해석한다. 이 정책을 Python/Kotlin 공통 fixture로 검증한다.

### 5.2 야간 기준일 anchor_date

`anchor_date`는 **밤을 시작하는 저녁이 속한 날짜**다. 평일은 월~금 저녁, 주말은 토~일 저녁으로 해석하며 온보딩에서 예시를 보여준다.

- 취침 입력이 12:00~23:59라면 anchor_date 당일의 취침 시각.
- 취침 입력이 00:00~11:59라면 anchor_date 다음 날의 취침 시각.
- 기상은 정한 취침 시각보다 뒤에 오는 최초의 해당 로컬 시각.
- 관리 구간: `[bedtime - 30분, wake_time)`.
- 취침 직전: `[bedtime - 30분, bedtime)`.
- 취침 이후: `[bedtime, wake_time)`.
- 같은 프로필의 연속 야간 구간이 겹치는 일정은 저장 시 거부하고 사용자에게 시각을 수정하도록 안내한다.

예: 일요일 저녁의 목표가 `00:00 / 07:00`이면 구간은 일요일 23:30~월요일 07:00이다. 이 야간 미션은 일요일, 즉 지난주에 속한다.

### 5.3 주간 상태와 비교

- `in_progress`: 이번 주의 날짜 또는 야간 구간이 아직 끝나지 않음.
- `awaiting_data`: 모든 구간은 끝났으나 닫힌 구간을 포함한 수집·동기화가 아직 이뤄지지 않음.
- `ready`: 7일·7야간이 모두 complete.
- `insufficient_data`: 수집을 수행했지만 일부 구간을 복원할 수 없음. 확보된 값은 표시하고 자동 다음 목표 생성은 해당 미션 유형에서 제한.
- 전체 앱 비교는 같은 측정 버전·시간대 조건을 만족해야 함. 선택 앱 비교는 같은 대상 앱 집합도 만족해야 함.
- 완전한 두 주가 아니면 정식 전주 증감률 대신 `비교 데이터 부족` 표시. 현재 주에는 진행 상황만 표시한다.
- 기준선은 처음 확보된 complete 7일/7야간으로 유형별 계산한다. 이후 목표는 직전 완료 주의 성과를 근거로 제안한다.
- 분모가 0이면 증감률은 null. `0분 → 20분`과 절대 차이로 설명한다.

## 6. 데이터 계약

Android가 원시 이벤트를 보관·정규화하고 서버에는 필요한 **앱별 일일·야간 집계만** 보낸다. 서버에 화면, 알림 내용, 웹 방문 주소, 원시 Activity 이름을 전송하지 않는다.

### 6.1 핵심 모델

| 모델 | 필드·타입 |
|---|---|
| Profile | `version: int`, `timezone: str`, `target_packages: list[str]`, `purposes: dict[str,str]`, `weekday_bed: HH:MM`, `weekday_wake: HH:MM`, `weekend_bed: HH:MM`, `weekend_wake: HH:MM`, `temporary_daily_ms: int`, `temporary_night_ms: int`, `final_daily_ms: int`, `final_night_ms: int`, `effective_from: YYYY-MM-DD` |
| AppDuration | `package_name: str`, `duration_ms: int` |
| WindowAggregate | `anchor_date: YYYY-MM-DD`, `kind: daily/pre_bed/after_bed`, `start_ms: int`, `end_ms: int`, `observed_until_ms: int`, `quality: complete/partial/unavailable`, `reason_codes: list[str]`, `profile_version: int`, `apps: list[AppDuration] 또는 null`, `measurement_version: str` |
| Mission | `id: str`, `anchor_date: YYYY-MM-DD`, `kind: daily/night`, `target_ms: int`, `profile_version: int`, `accepted_at_ms: int`, `window_start_ms: int`, `window_end_ms: int` |
| Proposal | `kind: daily/night`, `target_ms: int`, `reason_code: str`, `basis_week: YYYY-MM-DD`, `profile_version: int`, `rules_version: str` |
| MissionResult | `mission_id: str`, `status: in_progress/succeeded/failed/unknown/not_applicable`, `observed_ms: int 또는 null`, `evaluated_at_ms: int` |
| AnalysisInput | `schema_version: "1"`, `as_of_ms: int`, `last_collection_attempt_ms: int 또는 null`, `week_start: YYYY-MM-DD`, `profile: Profile`, `aggregates: list[WindowAggregate]`, `missions: list[Mission]`, `current_daily_target_ms: int 또는 null`, `current_night_target_ms: int 또는 null` |
| AnalysisOutput | `schema_version: "1"`, `week_status: str`, `metrics: WeeklyMetrics`, `mission_results: list[MissionResult]`, `proposals: list[Proposal]`, `insights: list[Insight]`, `rules_version: str` |
| WeeklyMetrics | `valid_days: int`, `valid_nights: int`, `all_apps_total_ms: int 또는 null`, `selected_total_ms: int 또는 null`, `selected_daily_mean_ms: float 또는 null`, `selected_night_mean_ms: float 또는 null`, `pre_bed_total_ms: int 또는 null`, `after_bed_total_ms: int 또는 null`, `daily_success_count: int`, `daily_evaluable_count: int`, `night_success_count: int`, `night_evaluable_count: int`, `per_day: list[dict]`, `per_app: list[dict]`, `comparison: dict` |
| Insight | `code: str`, `evidence: dict[str, int/float/str/null]`, `text: str`, `source: "template"` |

`per_day` 요소는 `date, daily_quality, pre_bed_quality, after_bed_quality, all_apps_ms, selected_ms, pre_bed_ms, after_bed_ms`를 갖는다. 품질은 각 구간별 enum이며 시간은 int 또는 null이다. `per_app` 요소는 `package_name: str, is_target: bool, total_ms: int 또는 null, share_pct: float 또는 null, night_total_ms: int 또는 null, night_share_pct: float 또는 null, delta_ms: int 또는 null, delta_pct: float 또는 null`를 갖는다. night_share_pct는 선택한 앱의 야간 합계가 분모이고 비선택 앱에서는 null이다. `comparison`은 `comparable: bool, reason: str 또는 null, selected_delta_ms: int 또는 null, selected_delta_pct: float 또는 null, all_apps_delta_ms: int 또는 null`이다.

`last_collection_attempt_ms`는 FE가 최근 수집을 시도한 시각이다. 닫힌 구간 이후의 수집 시도 자체가 없으면 awaiting_data, 시도했지만 해당 집계가 없거나 불완전하면 insufficient_data로 구분한다. 이 값만으로 집계 품질을 complete로 승격하지 않는다.

`current_daily_target_ms/current_night_target_ms`는 **사용자가 수락한 개인화 목표**이며 아직 임시 목표만 사용하는 유형은 null로 전송한다. 임시 목표는 Profile에서 읽는다. 발급한 미션은 임시 목표인 경우도 Mission 배열에 포함한다. 분석 결과의 proposal을 current 값에 자동 복사하지 않는다.

입출력 모델의 dict 자유도를 그대로 제품 코드에 남기지 말고, 위에 열거한 필드를 Pydantic 모델 및 BE/FE DTO의 명시적 필드로 옮긴다. `evidence`만 관찰 유형에 따라 달라지는 맵으로 둔다.

### 6.2 검증·중복

- 모든 duration/target은 0 이상의 정수. bool·음수·비정상적으로 큰 정수는 거부.
- `start_ms < end_ms`, `start_ms <= observed_until_ms <= end_ms`.
- complete는 `observed_until_ms == end_ms`이고 `end_ms <= as_of_ms`일 때만 허용.
- unavailable이면 apps=null, complete이면 apps는 빈 배열 또는 값 있는 배열. 빈 배열이 확인된 0이다.
- 같은 집계 안의 package_name 중복은 거부. 각 앱 시간은 해당 구간 길이를 초과할 수 없지만 서로 다른 앱들의 합계는 초과 가능.
- 집계 키는 `(anchor_date, kind, profile_version, measurement_version)`이며 입력 배열 내 중복 키는 ValidationError. 로컬 저장은 동일 키 최신 재집계로 upsert.
- daily/pre_bed/after_bed의 실제 start/end가 프로필로 계산한 구간과 맞는지 분석 모듈에서도 확인. 한 요청의 집계·미션 profile_version은 request.profile.version과 같아야 하며 측정 버전은 요청 내에서 같아야 함. 다른 버전의 보고서는 당시 Profile로 별도 요청한다.
- week_start는 월요일이어야 함. mission.id와 (anchor_date, kind) 중복은 거부. target_packages는 중복 없는 비어 있지 않은 배열. 모든 추가 필드는 오탈자를 숨기지 않도록 거부한다.
- duration/target 상한은 2**53-1ms, 시각은 2000-01-01~2100-01-01 UTC 범위. 프로필 목표 입력은 분 단위 정수이고 임시 목표는 최종 목표 이상. 분석 모듈 내부 기준선·판정은 ms 단위를 유지한다.
- 앱 집합·시간대·일정이 다른 이전 버전의 집계를 현재 프로필 집계인 것처럼 전송하지 않음. Android에서 현재 프로필에 맞게 재집계 가능한 범위만 포함.
- 분석 입력은 현재·이전 주를 포함하는 최대 21 anchor dates, 최대 200개 앱/구간으로 제한. 초과는 ValidationError. HTTP 본문 크기 제한과 인증 실패 처리 등 전송 계층 제약은 BE가 결정한다.
- 비교 가능하지 않은 과거 보고서는 로컬의 당시 스냅샷으로 열람 가능하되 현재 요청의 기준선으로 재사용하지 않음.

### 6.3 BE에 제공할 Python 진입점

```python
from screentime import AnalysisInput, AnalysisOutput, analyze


def run_analysis(payload: dict) -> dict:
    request = AnalysisInput.model_validate(payload)
    result: AnalysisOutput = analyze(request)
    return result.model_dump(mode="json")
```

`analyze(request: AnalysisInput) -> AnalysisOutput`가 유일한 상위 진입점이다. 내부 분석·판정 함수도 단위 테스트와 재사용을 위해 노출한다. 호출자가 입력을 전달하며 함수가 DB나 시스템 현재 시각을 직접 읽지 않는다. 동일한 입력과 rules_version은 동일한 출력을 반환한다.

- 구조·단위·범위 오류는 Pydantic `ValidationError`를 발생시킨다. 잘못된 입력을 빈 성공 결과로 치환하지 않는다.
- 데이터 부족은 예외가 아니라 `insufficient_data` 등의 정상 분석 결과다.
- 사용자 식별자·세션·토큰·HTTP 상태 코드는 AI 입력에 요구하지 않는다. BE가 올바른 사용자의 기록을 조회하고 사용자별 결과를 연결한다.
- BE가 Python이면 wheel을 설치해 함수를 직접 호출할 수 있다. BE 언어가 다르면 BE 담당자가 실행 경계·래퍼를 결정한다. 언어 미정 때문에 AI 측이 별도 서버를 선제 구축하지 않는다.
- AI 패키지는 함수 실행 중 입력·프로필·결과를 영구 저장하거나 외부 전송하지 않는다. BE의 저장 방식·데이터 보관 정책은 BE 담당 범위이며 이 문서에서 DB 사용을 금지하지 않는다.
- 입력·출력 JSON Schema와 실제 함수 실행으로 생성한 예제 JSON을 전달한다. HTTP 경로·OpenAPI·인증 구현은 BE가 이 계약에 맞춰 작성한다.

## 7. 분석 공식과 설명 규칙

### 7.1 계산

```text
selected_day_ms = sum(app.duration_ms for app in daily.apps if app.package_name in targets)
night_ms = selected_pre_bed_ms + selected_after_bed_ms
baseline_daily_ms = complete 7일 selected_day_ms의 산술평균
baseline_night_ms = complete 7야간 night_ms의 산술평균
share_pct = app_week_ms / all_apps_week_ms * 100  (분모 0이면 null)
delta_pct = (this_week_ms - last_week_ms) / last_week_ms * 100  (분모 0이면 null)
success_rate = succeeded_count / (succeeded_count + failed_count)
```

성공률에서 unknown/in_progress/not_applicable은 분모에서 제외하고 개수를 별도 표시한다. `2/2 달성, 5일 확인 불가`를 `주간 100% 달성`으로 표현하지 않는다.

partial 집계의 확인된 값은 per_day에 품질과 함께 표시하지만 주간 합계·기준선에는 섞지 않는다. `*_total_ms`는 해당 주의 complete 구간만 합산한 값이며 유효 구간이 하나도 없으면 null이다. 불완전한 주의 합계는 `확인된 사용량`과 유효 일수를 함께 표시한다. `selected_daily_mean_ms/selected_night_mean_ms`는 해당 주의 complete 구간이 각각 7개일 때만 반환하고 그 외에는 null이다. 최초 기준선은 별도로 요청 내 유효 기록을 날짜순으로 정렬해 처음 7개로 계산한다. 일일과 야간의 최초 기준선 확보 시점은 다를 수 있다.

per_app의 주간 앱별 시간·비중은 complete 일별 구간을, 야간 시간·비중은 pre_bed와 after_bed가 모두 complete인 야간을 사용한다. 데이터가 부족한 기간의 비중은 전체 주의 비중으로 단정하지 않는다. 달성률 분모가 0이면 null이며 설명 템플릿은 비율 대신 `판정 가능한 미션 없음`을 표시한다.

### 7.2 관찰 유형

- `SELECTED_USAGE_DECREASED`: 비교 가능한 두 주에서 선택 앱 합산 감소.
- `OTHER_APPS_INCREASED`: 선택 앱 감소와 동시에 비선택 앱 합산 증가. `다른 앱 사용이 늘었습니다`까지 표현하며 대체 사용의 원인을 확정하지 않음.
- `NIGHT_TOP_APP`: 야간 합산이 0보다 클 때 가장 비중이 높은 선택 앱과 비중.
- `DAILY_NIGHT_DIFFERENCE`: 유형별 판정 데이터가 있을 때 일일·야간 성과를 나란히 설명.
- `INSUFFICIENT_DATA`: 분석 불가 사유와 기록이 더 필요한 사실.

통계적 유의성, 중독, 불안·우울, 실제 잠든 시각, 의지 부족을 사용 기록으로 판단하지 않는다. 임의의 건강 점수·중독 점수는 추가하지 않는다.

## 8. 미션 생성과 상태

### 8.1 초기·다음 주 제안

숫자 계산은 `Decimal` 또는 정수 산술을 사용해 반올림 오차를 피한다. 분 단위 목표는 내림하되 **작은 양수가 반올림만으로 0이 되지 않게 최소 1분**을 유지한다. 목표 0은 사용자가 최종 목표를 0으로 두고 명시적으로 선택한 경우에만 적용한다.

```python
from decimal import Decimal, ROUND_FLOOR

MINUTE_MS = 60_000

def reduce_target(reference_ms: int, final_goal_ms: int) -> int:
    if reference_ms <= final_goal_ms:
        return reference_ms
    reduced = Decimal(reference_ms) * Decimal("0.90")
    minutes = int((reduced / MINUTE_MS).to_integral_value(rounding=ROUND_FLOOR))
    candidate = max(MINUTE_MS, minutes * MINUTE_MS)
    return min(reference_ms, max(final_goal_ms, candidate))
```

- 해당 유형 current_target이 null이며 유효한 7일/7야간 확보: 기준선 평균을 정수 ms로 내린 값에 `reduce_target` 적용하여 **최초 개인화 목표 제안**. 유효 7개가 없으면 그 유형의 proposals는 비워 두고 임시 목표 사용 이유를 설명한다.
- 최초 제안은 임시 목표를, 이후 제안은 current_target을 상한으로 삼아 제안이 그 목표보다 커지지 않게 제한. 완화는 사용자 직접 수정으로만 가능.
- current_target이 있는 유형의 기존 주간 목표 조절: 직전 주에 해당 유형 판정 가능한 미션 7개이며 성공 5개 이상이면 현재 목표에 `reduce_target` 적용. 아니면 유지 제안.
- 이미 최종 목표 이하로 사용하고 있으면 추가 감축 요구 대신 유지 설명.
- 최초 기준선이 1분 미만이면 새 숫자 목표를 제안하지 않고 낮은 사용량 유지 설명만 제공한다. 초 단위 기준선을 분 단위 입력 목표로 강제 변환하지 않는다.
- 사용자 미수락 시 현재 활성 목표 유지. 이전 목표가 없으면 임시 목표 사용.
- 제안은 각 유형별 한 개. 미션 타입·앱 목록·수치를 생성형 AI(LLM)가 바꿀 수 없음.

### 8.2 수락과 적용 시점

- 월요일 보고서가 확정된 뒤 제안을 수락하면 **아직 시작하지 않은 첫 해당 구간부터** 이번 주 남은 기간에 적용한다.
- 이미 시작한 오늘의 일일 미션이나 진행 중 야간 미션을 소급 변경하지 않는다.
- 이 때문에 월요일 일일 미션은 기존 목표이고 월요일 밤부터 새 야간 목표가 적용될 수 있다. 화면에 적용 시작일 표시.
- 한 주에 유형별 한 번 목표를 활성화하며 다음 변경은 다음 주 제안에서 처리. 첫 설치일의 부분 구간은 공식 미션 평가에서 제외하고 다음 완전한 구간부터 발급.
- FE/BE는 `(basis_week, kind, profile_version, rules_version)`별 제안 수락·수정·유지 선택을 저장한다. 무상태 분석 함수를 재호출해도 이미 결정한 같은 주 제안을 다시 적용하지 않는다.
- Mission은 실제 발급 당시 profile_version/target/window를 저장한다. 현재 설정으로 과거 결과를 재평가하지 않는다.

### 8.3 판정 순서

```text
미션이 구간 시작 전에 존재하지 않음 → not_applicable
구간 종료 전 → in_progress (확인된 사용량이 초과했어도 UI에서 초과 사실만 표시)
구간 종료 후, quality != complete → unknown
구간 종료 후, complete and observed_ms <= target_ms → succeeded
구간 종료 후, complete and observed_ms > target_ms → failed
```

야간 품질은 pre_bed와 after_bed 둘 다 complete일 때만 complete다. Python이 판정의 기준 구현이다. 공통 fixture를 제공해 FE가 로컬 판정을 구현할 때 같은 결과인지 검증할 수 있게 한다. FE 구현·검증 자체는 이번 범위 밖이다. 늦게 회복된 기록은 보고서 결과를 수정할 수 있지만 과거 목표는 그대로이며 이미 수락된 새 목표도 자동 변경하지 않는다.

## 9. 설명 생성 경계

AI 담당자는 우선 `render_insights(metrics, profile) -> list[Insight]`의 규칙 기반 한국어 템플릿을 구현한다. 예: `지난주 선택한 앱 사용량은 하루 평균 108분입니다. 그 전주보다 12분 줄었습니다.`

여기서 AI 담당 범위는 규칙 기반 분석을 포함한다. 학습 모델이 있어야만 분석 기능을 구현할 수 있는 것은 아니다. 외부 AI 제공자·모델·비용은 아직 선택되지 않았다. 임의로 유료 호출을 넣지 않는다. 별도 제공자가 지정되면 다음 계약으로 어댑터를 추가할 수 있도록 설명 함수 경계만 유지하고, 사용하지 않는 SDK·복잡한 플러그인 시스템은 만들지 않는다.

- 입력: 계산 완료된 지표, 사용 목적, 수락 가능한 목표 후보. 원시 이벤트·식별 토큰 제외.
- 출력: 구조화된 설명 문구. 수치·목표·판정 필드는 출력 권한 없음.
- 숫자는 가능하면 코드에서 문장 슬롯에 삽입해 외부 모델이 다시 계산하지 않게 함.
- 사용 목적의 자유 입력은 신뢰하지 않는 데이터로 취급하고 시스템 지시와 분리.
- 외부 AI 별도 동의, 시간 제한, 실패 시 템플릿 복귀 필요.
- 현재 버전에서 미연동 기능은 README와 화면에 정확히 표시. 템플릿을 AI 호출 결과라고 꾸미지 않음.

## 10. 필수 검증 fixture

아래는 모두 합성 데이터다. 실제 사용 기록을 테스트 파일·저장소에 넣지 않는다.

| ID | 입력·상황 | 기대 결과 |
|---|---|---|
| F01 | 7일 선택 앱 120분, 야간 30분으로 complete | 기준선 120분/30분, 제안 108분/27분 |
| F02 | 야간 목표 27분, complete 사용량 27분 | succeeded |
| F03 | 같은 목표에서 27분 1ms 사용 | failed |
| F04 | 이벤트 없음, quality unavailable | 시간 null, unknown. 0분 성공 금지 |
| F05 | complete이며 앱 목록 빈 배열 | 확인된 사용량 0, 종료된 미션 succeeded |
| F06 | 지난주 0분, 이번 주 20분 | delta_pct=null, 절대 증가 20분 |
| F07 | 일요일 23:50~월요일 00:10 사용, 목표 00:00/07:00 | 일별 10분씩 분리, 일요일 야간 pre_bed 10분+after_bed 10분 |
| F08 | 월요일 00:01 보고서 요청, 일요일 야간 종료는 07:00 | in_progress. 종료 후 미수집이면 awaiting_data |
| F09 | 성공 2, 실패 0, unknown 5 | `2/2, 확인 불가 5`; 7일 감축 조건 미충족 |
| F10 | 같은 범위 2번 수집·동기화 | 값이 2배가 되지 않음, 요청 결과 동일 |
| F11 | 설정 변경 후 과거 보고서 열기 | 과거 대상 앱·목표 유지, 다른 집합과 직접 증감 비교 금지 |
| F12 | 월요일 정오 목표 수락 | 월요일 일일 목표 불변, 다음 미시작 구간부터 적용 |
| F13 | 한 앱의 Activity A/B가 겹친 10분 | 같은 앱 시간 10분, 20분 아님 |
| F14 | 다른 앱 2개가 멀티윈도우로 각각 10분 | 앱 합계 20분 가능, 물리 화면 시간이라고 표시하지 않음 |
| F15 | 조회 실패 후 복구 불가, 재부팅 상태 불명 | 미해결 구간 partial/unavailable, 세션 임의 연장 금지 |
| F16 | 첫 설치가 수요일 정오 | 수요일 공식 일일 미션은 not_applicable; 완전 구간부터 시작 |
| F17 | 현재 목표 60분, 사용량이 100분으로 증가 | 다음 목표 자동 90분 완화 금지 |
| F18 | 최종 목표 60분, 현재 목표 65분에서 감축 | 60분 아래로 내려가지 않음 |
| F19 | 진행 중 complete 또는 음수·중복 패키지 입력 | ValidationError |
| F20 | 서버 동의 없음 / 네트워크 실패 | 원격 전송 없음 / 로컬 값·기존 미션 유지, 재시도 가능 |
| F21 | America/New_York DST 전환일의 일별 구간 | 실제 23시간 또는 25시간 경계, 24시간 상수로 계산 금지 |
| F22 | 알려진 잠금·화면 꺼짐 중 전경 앱 상태 잔존 | 잠금/꺼짐 구간은 사용량 제외 |

## 11. AI 담당자 산출물과 파일 구성

신규 구현 기본 경로는 `screentime_analysis/`다. 기존 모델 디렉터리에 섞지 않는다.

```text
screentime_analysis/
  README.md                         # 설치·함수 호출·입출력·평가·한계
  pyproject.toml                    # Python 패키징·개발 의존성
  requirements.lock                 # 설치·검증한 의존성 고정
  .gitignore                        # 캐시·실제 사용 데이터·빌드 결과 제외
  screentime/
    __init__.py                     # AnalysisInput, AnalysisOutput, analyze 노출
    __main__.py                     # 합성 입력 JSON → 출력 JSON 데모 CLI
    models.py                       # 명시적인 Pydantic 입력·출력 모델
    windows.py                      # 날짜·야간·주간·시간대 경계
    analytics.py                    # 합산·평균·비교·데이터 품질
    missions.py                     # 목표 제안·판정 순수 함수
    narratives.py                   # 근거 기반 한국어 템플릿
    pipeline.py                     # 순수 함수들을 묶는 analyze 진입점
  tests/
    conftest.py                     # 합성 프로필·사용량 fixture
    test_models.py
    test_windows.py
    test_analytics.py
    test_missions.py
    test_narratives.py
    test_pipeline.py
    test_contract_examples.py
    test_cli.py
  contracts/
    input.schema.json               # AnalysisInput에서 생성
    output.schema.json              # AnalysisOutput에서 생성
    be-handoff.md                   # BE 호출·오류·버전·저장 책임 안내
    android-data-contract.md        # FE가 만드는 집계·품질·경계 정의
    fixtures.json                   # 공통 계산·판정 입력과 기대값
    examples/
      complete-week.input.json
      complete-week.output.json
      insufficient-data.input.json
      insufficient-data.output.json
  evaluation/
    report.md                       # 규칙·경계·설명 정확성 평가 결과
```

최종 전달물은 설치 가능한 wheel, 입력·출력 스키마, 사용 예제, 테스트, 평가 보고서다. 작은 함수는 위 파일 안에 유지한다. HTTP 서버·DB·계정 시스템을 추가하지 않는다.

## 12. 단계별 구현 계획

각 단계는 테스트 작성 → 실패 원인 확인 → 최소 구현 → 통과 확인 → 변경 요약 순서로 수행한다. 사용자 요청 또는 실행 환경의 기존 정책 없이 자동 push·배포하지 않는다. 커밋을 하는 환경이면 단계별 관련 파일만 커밋한다.

### Task 1. 계약과 날짜 계산

**Files:** `screentime_analysis/tests/conftest.py`, `screentime_analysis/pyproject.toml`, `screentime_analysis/screentime/{__init__,models,windows}.py`, `screentime_analysis/tests/{test_models,test_windows}.py`, `screentime_analysis/contracts/fixtures.json`.

**Interfaces:** `night_windows(anchor_date: date, profile: Profile) -> tuple[Window, Window]`. `Window`는 `start_ms, end_ms` 필드를 가진다. 반환 순서는 pre_bed, after_bed. `Profile`은 6절 필드와 검증 규칙을 사용한다.

- [ ] Python 패키지와 pytest 실행 환경을 만들고 F07/F08/F19/F21 fixture를 작성한다.
- [ ] 아래와 같은 계약 테스트를 작성하고 실패를 확인한다.

```python
def test_sunday_midnight_belongs_to_sunday(seoul_profile):
    from datetime import date, datetime
    from zoneinfo import ZoneInfo
    from screentime.windows import night_windows
    pre, post = night_windows(date(2026, 9, 13), seoul_profile)
    zone = ZoneInfo("Asia/Seoul")
    assert datetime.fromtimestamp(pre.start_ms / 1000, zone).isoformat() == "2026-09-13T23:30:00+09:00"
    assert datetime.fromtimestamp(post.end_ms / 1000, zone).isoformat() == "2026-09-14T07:00:00+09:00"
```

`seoul_profile` fixture는 timezone=Asia/Seoul, 모든 취침=00:00·기상=07:00, 대상 앱=com.example.video, 임시 목표=120/30분, 최종 목표=60/0분, version=1, effective_from=2026-09-07로 생성한다.

- [ ] `Window`, `Profile`, 입력·출력 모델과 5절 경계 규칙을 구현한다. UTC 변환 전 시간대 경계를 결정한다.
- [ ] `python -m pytest tests/test_models.py tests/test_windows.py -q` 통과를 확인한다.

### Task 2. 주간 분석 순수 함수

**Files:** `screentime_analysis/screentime/analytics.py`, `screentime_analysis/tests/test_analytics.py`.

**Interfaces:** `analyze_week(request: AnalysisInput) -> WeeklyMetrics`, `get_week_status(request: AnalysisInput) -> str`. 입력 모델은 Task 1을 사용하며 숨겨진 시스템 현재 시각 대신 request.as_of_ms를 사용한다.

- [ ] F01/F04/F05/F06/F08/F09/F11 데이터로 테스트를 작성한다. 유효 주 7일 각각 120분이면 평균 120분, 총량 840분을 기대한다.
- [ ] 테스트 실패를 확인한 뒤 7절 공식을 구현한다. 미완료 값과 확정값을 섞지 않는다.

```python
def test_complete_week_average(full_week_request):
    from screentime.analytics import analyze_week
    result = analyze_week(full_week_request)
    assert result.valid_days == 7
    assert result.selected_total_ms == 840 * 60_000
    assert result.selected_daily_mean_ms == 120 * 60_000

def test_unknown_is_not_zero(unavailable_week_request):
    from screentime.analytics import analyze_week
    result = analyze_week(unavailable_week_request)
    assert result.valid_days == 0
    assert result.selected_daily_mean_ms is None
```

`full_week_request`는 F01 기준의 7일 daily/pre_bed/after_bed 및 종료 후 as_of_ms/last_collection_attempt_ms로 만든다. 두 current_target은 null, missions는 빈 배열로 두어 최초 개인화 제안을 검증한다. complete daily는 120분, pre_bed는 20분, after_bed는 10분이며 날짜 경계에 맞게 합성한다. 목적은 여가로 설정한다. `unavailable_week_request`는 같은 경계를 쓰되 모든 apps=null, quality=unavailable로 만든다.

- [ ] `python -m pytest tests/test_analytics.py -q`로 기간·누락·0분모·집합 변경을 검증한다.

### Task 3. 목표 제안과 미션 판정

**Files:** `screentime_analysis/screentime/missions.py`, `screentime_analysis/tests/test_missions.py`.

**Interfaces:** `reduce_target(reference_ms: int, final_goal_ms: int) -> int`, `evaluate_mission(mission: Mission, observed_ms: int | None, quality: str, as_of_ms: int) -> MissionResult`, `propose_targets(request: AnalysisInput, metrics: WeeklyMetrics) -> list[Proposal]`.

- [ ] F02/F03/F09/F12/F16/F17/F18 경계 테스트를 작성한다.

```python
def test_target_reduction_and_floor():
    from screentime.missions import reduce_target
    assert reduce_target(120 * 60_000, 60 * 60_000) == 108 * 60_000
    assert reduce_target(65 * 60_000, 60 * 60_000) == 60 * 60_000
    assert reduce_target(60_000, 0) == 60_000
```

- [ ] 실패 확인 후 8절의 수식과 판정 순서를 구현한다. `accepted_at_ms > window_start_ms`이면 해당 미션에 not_applicable을 반환한다.
- [ ] 7개 complete 판정 없이 감축하지 않으며 일일과 야간 조건이 독립임을 검증한다.
- [ ] `python -m pytest tests/test_missions.py -q` 통과를 확인한다.

### Task 4. 설명 생성과 분석 파이프라인

**Files:** `screentime_analysis/screentime/{narratives,pipeline,__init__}.py`, `screentime_analysis/tests/{test_narratives,test_pipeline}.py`.

**Interfaces:** `render_insights(metrics: WeeklyMetrics, profile: Profile) -> list[Insight]`, `analyze(request: AnalysisInput) -> AnalysisOutput`. 입력·출력은 6절 그대로다.

- [ ] F01 입력의 분석·제안·설명이 일치하는 통합 테스트를 작성한다. 데이터가 부족한 경우 임의의 목표·성공 판정을 생성하지 않는지도 검증한다.

```python
def test_pipeline_has_deterministic_proposals(full_week_request):
    from screentime import analyze
    result = analyze(full_week_request)
    daily = next(p for p in result.proposals if p.kind == "daily")
    assert daily.target_ms == 108 * 60_000
    assert result == analyze(full_week_request)
```

- [ ] 분석 → 미션 판정·유형별 성과 집계 → 다음 목표 제안 → 근거 설명 → AnalysisOutput 조립 순서를 구현한다. 모델·외부 API 호출을 넣지 않는다.
- [ ] 템플릿 문장은 근거 필드와 일치해야 한다. 확인 불가를 성공으로 설명하거나 사용 목적에서 심리 원인을 단정하는 문구를 만들지 않는다.
- [ ] `python -m pytest tests/test_pipeline.py tests/test_narratives.py -q` 통과를 확인한다.

### Task 5. BE 전달 계약과 JSON 예제

**Files:** `screentime_analysis/contracts/*`, `screentime_analysis/contracts/examples/*.json`, `screentime_analysis/tests/test_contract_examples.py`.

**Interfaces:** Task 1의 AnalysisInput/AnalysisOutput와 Task 4의 `analyze`. BE가 패키지를 설치하고 자신의 HTTP API·DB 흐름에 연결할 수 있게 한다.

- [ ] `AnalysisInput.model_json_schema()`와 `AnalysisOutput.model_json_schema()`로 JSON Schema를 생성한다.
- [ ] F01 완전 주와 F04 불완전 주의 입력 JSON을 작성한다. profile, as_of_ms, 수집 시각, 구간 경계, missions, 현재 목표를 생략하지 않는다.
- [ ] 실제 analyze 함수를 실행한 값으로 output 예제를 생성한다. 손으로 성공 수치나 가짜 분석 결과를 작성하지 않는다.

```python
import json
from pathlib import Path


def test_complete_week_example():
    from screentime import AnalysisInput, analyze
    root = Path(__file__).resolve().parents[1] / "contracts" / "examples"
    payload = json.loads((root / "complete-week.input.json").read_text())
    expected = json.loads((root / "complete-week.output.json").read_text())
    actual = analyze(AnalysisInput.model_validate(payload)).model_dump(mode="json")
    assert actual == expected
```

- [ ] BE 문서에 설치·함수 호출·필드·단위·enum·null/0·ValidationError·데이터 부족·버전·동일 입력 재실행을 설명한다.
- [ ] AI는 제안만 반환하고 실제 미션 수락·저장·활성화·알림·주간 호출은 BE/FE 책임임을 명시한다.
- [ ] F07/F13/F14/F15/F21/F22를 FE 생산자 검증 항목으로도 제공한다. Python은 집계 이후 산술·경계를 검증하며 원시 Android 이벤트를 검증했다고 주장하지 않는다.
- [ ] `python -m pytest tests/test_contract_examples.py -q`로 예제·스키마와 구현의 일치를 확인한다.

### Task 6. 패키징·실행 데모·평가 보고서

**Files:** `screentime_analysis/screentime/__main__.py`, `screentime_analysis/tests/test_cli.py`, `screentime_analysis/README.md`, `screentime_analysis/requirements.lock`, `screentime_analysis/evaluation/report.md`.

**Interfaces:** `python -m screentime --input INPUT_JSON --output OUTPUT_JSON`. CLI는 명시된 파일만 읽고 쓰며 DB·네트워크·서버를 사용하지 않는다. 성공 exit 0, 검증 실패 exit 2. 실패 시 원본 사용자 데이터를 출력하지 않고 필드 위치와 오류 유형만 stderr에 표시한다.

- [ ] 합성 2주 데이터로 전체·선택 앱·야간·주간 비교·미션·설명 흐름을 검증한다.
- [ ] CLI subprocess 테스트에서 정상 출력 파일과 exit 0, 잘못된 입력의 exit 2를 확인한다.
- [ ] 별도 프로세스에서 같은 입력이 같은 결과를 내는지 확인한다. 실제 현재 시각 대신 as_of_ms를 사용한다.
- [ ] `python -m build`로 wheel을 생성하고 임시 가상환경에 설치한 뒤 공개 진입점과 합성 JSON 데모를 실행한다.
- [ ] 평가 보고서에 계산 기대값 일치, 누락 처리, 목표 하한, 날짜·시간대 경계, 설명의 수치 일치를 기록한다. F01~F22의 AI/BE/FE 책임과 검증 상태를 구분한다.
- [ ] 실제 사용자 행동 개선 효과·모델 품질은 합성 데이터 테스트로 입증했다고 주장하지 않는다. 실사용 평가는 이후 단계다.
- [ ] README에 설치·함수 호출·CLI 예제·BE 전달 문서·한계를 적고 Python 전체 테스트와 Ruff를 실행한다.

## 13. 실행 명령과 완료 기준

다음 명령은 AI 저장소의 `screentime_analysis/`에서 실행한다. API 키·서버 토큰·DB 접속 정보가 없어도 전부 실행 가능해야 한다.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
python -m ruff check .
python -m screentime --input contracts/examples/complete-week.input.json --output /tmp/screentime-demo-output.json
python -m build
```

Python 3.12가 없으면 설치 가능한 환경을 확인한다. 테스트를 실행하지 못하면 차단 요인과 미실행 명령을 정확히 보고한다. BE 서버나 Android 개발 환경은 설치하지 않는다.

완료 기준:

- [ ] `from screentime import AnalysisInput, AnalysisOutput, analyze`로 사용할 수 있는 wheel을 제공함.
- [ ] 합성 JSON을 받아 분석 결과 JSON을 만드는 데모가 네트워크·키·DB 없이 동작함.
- [ ] F01~F22 중 AI 책임 항목은 테스트되고 BE/FE 책임 항목은 전달 체크리스트에 구분됨.
- [ ] null·0·partial·진행 중·부분 주·0분모가 구별됨.
- [ ] 일요일 야간·DST·대상 앱·버전 변경의 비교 가능 여부가 검증됨.
- [ ] 제안과 활성 목표가 분리되고 미션 판정은 전달받은 스냅샷을 사용함.
- [ ] 설명의 수치가 계산 결과와 일치하고 생성형 AI를 호출했다고 꾸미지 않음.
- [ ] JSON Schema와 예제 입력·출력이 실제 코드와 일치함.
- [ ] wheel 설치·데모·테스트·lint 결과와 평가 보고서를 제공함.
- [ ] 라이브러리는 사용자 입력을 영구 저장·로그·외부 전송하지 않음. CLI는 사용자가 지정한 데모 파일만 다룸.
- [ ] HTTP API·인증·DB·스케줄러·배포·Android 코드를 생성하지 않음.
- [ ] 기존 펫톡스 모델 코드가 바뀌지 않음.

## 14. Claude에 붙여넣을 실행 요청

```text
첨부한 2026-09-09-personalized-screentime-plan.md를 읽고 내 AI 담당 범위만 구현해줘. 백엔드는 다른 사람이 담당해.

현재 저장소의 AGENTS.md/CLAUDE.md를 확인하고 신규 screentime_analysis 폴더에 설치 가능한 Python 분석 라이브러리를 작성해.

구현할 것은 사용 패턴·기준선 분석, 개인 맞춤 미션 후보, 미션 판정 순수 함수, 근거 기반 한국어 설명, 입력·출력 JSON Schema, 합성 데이터 테스트, BE 전달 문서야.

백엔드가 from screentime import analyze로 가져다 쓸 수 있게 만들어줘. FastAPI, API 라우터, 인증, DB, 서버 스케줄러, 배포, Android 코드는 만들지 마. 서버 주소나 API 키가 없어도 합성 데이터로 실행·평가할 수 있어야 해.

Task 1부터 순서대로 구현하고 날짜 경계, 일요일 야간, 누락과 0, 미션 수락 시점, 목표 하한을 테스트해. 확정 요구사항과 문서의 MVP 기본값을 구분하고, 해결할 수 없는 실제 모순만 질문해.

외부 AI 제공자는 아직 정해지지 않았으므로 설명 생성 경계를 분리하고 우선 규칙 기반 템플릿을 구현해. 템플릿을 생성형 AI 호출 결과라고 표시하지 마.

wheel 빌드와 새 가상환경 설치, JSON 입력·출력 데모, 테스트·lint를 검증해. 기존 모델 코드를 임의로 수정하지 말고 실제 사용자 데이터나 키를 테스트·로그·저장소에 넣지 마. push·배포·유료 외부 API 호출은 하지 마.

마지막에 AI 측 구현 결과, 실행·평가 방법, BE에게 전달할 파일과 BE 담당자의 연동 작업, 미검증 사항을 정리해줘.
```

## 15. 공식 참고 문서

- [UsageStatsManager — 권한·조회·보관 범위](https://developer.android.com/reference/android/app/usage/UsageStatsManager)
- [UsageEvents.Event — 앱·화면·잠금 이벤트](https://developer.android.com/reference/android/app/usage/UsageEvents.Event)
- [WorkManager 주기 작업 제약](https://developer.android.com/reference/androidx/work/PeriodicWorkRequest)
- [패키지 가시성](https://developer.android.com/training/package-visibility)
- [Kotlin 우선 Android 개발](https://developer.android.com/kotlin/first)

공식 자료 확인일: 2026-09-09. 담당 범위 수정일: 2026-09-10. 구현 시 SDK·라이브러리 호환성과 해당 API 설명을 다시 확인한다.
