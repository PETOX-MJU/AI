# 한줄 요약 SLM 앱 연결 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FE 대시보드의 한줄 요약(`insights[0]`)을 v2 SLM 이 만든 반려견 말투 문장으로 바꾸고, 제목을 `${반려견 이름}의 한줄 요약`으로 달아 실기기에서 시연한다.

**Architecture:** 분석기(Kotlin)는 그대로 템플릿 문장을 낸다. FE 가 그 문장을 사실로 삼아 llama.rn 으로 한 문장을 생성하고,
Python 과 같은 규칙으로 검사해 통과할 때만 화면 문장을 바꾼다. 실패·오류·시간 초과·모델 없음은 전부 템플릿 문장 유지.
검사 규칙의 정본은 AI 저장소 Python 이고, TS 포팅은 Python 이 뽑은 대조 JSON 으로 일치를 강제한다.

**Tech Stack:** React Native 0.87 (New Architecture, Hermes), TypeScript, jest, `llama.rn` (MIT, llama.cpp 바인딩), Python 3 (AI 저장소)

**Spec:** `docs/superpowers/specs/2026-09-25-slm-summary-app-design.md`

## Global Constraints

- 분석기(`kotlin_port/`)와 출력 계약은 바꾸지 않는다. `insight.source` 는 `"template"` 고정.
- 생성 설정은 학습·평가와 같아야 한다: system = `data.SYSTEM` 원문, user = `사실: {fact}`, `jinja: true`, `enable_thinking: false`, `n_predict: 80`, `temperature: 0.5`, `n_ctx: 512`, `n_threads: 4`.
- `seed` = 리포트 주 시작일(`metrics.per_day[0].date`)의 epoch day.
- 검사 네 가지(`check`, `meaning_errors`, `marker_errors` + 빈 출력)를 모두 통과해야 교체한다. 하나라도 걸리면 템플릿.
- 시간 제한 15초. 모델은 성공·실패와 상관없이 해제한다. 동시에 두 모델을 올리지 않는다.
- 모델 경로(시연용 고정): `/data/data/com.petoxmju.petox/files/ft-v2-q4.gguf`
- 제목: `${이름}의 한줄 요약`, 이름 없으면 `한줄 요약`, 8자 초과면 8자 + `…`. 문장에 따옴표 없음. "AI" 표시 없음.
- FE 저장소: `PETOX-MJU/FE` 를 `/Users/parkhyunsik/파이썬/petox-FE` 에 클론, 브랜치 `feat/slm-summary`.
- AI 저장소 작업은 브랜치 `feat/slm-summary`(PR #6)에 이어서 커밋한다.
- 커밋 메시지 끝: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Review Focus

- **영문 앱 이름의 조사:** `TikTok` → "TikTok을", `YouTube` → "YouTube를", `TV` → "TV를". FE `APP_META` 이름이 영문이라 가장 먼저 눈에 띈다 → Task 1·2 테스트.
- **앱에 복귀할 때마다 재생성:** 대시보드는 `AppState` 가 `active` 가 될 때마다 다시 분석한다. 같은 주·같은 사실이면 모델을 다시 올리지 않아야 한다 → Task 4 메모 테스트.
- **분석 두 번이 겹칠 때 모델 두 개 동시 적재:** 메모리 1GB 이상이 두 배가 된다 → Task 4 직렬화 테스트.
- **불러오는 중 시간 초과:** 해제할 context 가 아직 없을 때도 적재가 끝난 뒤 해제해야 한다 → Task 4 시간 초과 테스트.
- **기기(Hermes) 정규식:** 검사가 lookbehind(`(?<!...)`)를 쓴다. jest(Node)는 통과해도 기기에서 다를 수 있다 → Task 6 에서 logcat 의 `[slm]` 판정 로그로 확인.

---

### Task 1: 받침 판정 고치기 + 대조 JSON 생성 (AI 저장소)

**Files:**
- Modify: `slm_summary/data.py:24-30` (`has_batchim`)
- Create: `slm_summary/export_cases.py`
- Output (커밋 안 함, Task 2 에서 FE 로 복사): `slm_summary/results/slmCases.json`

**Interfaces:**
- Produces: `slmCases.json` = `{"checks": [{"fact": str, "out": str, "fail": [str]}], "fills": [{"out": str, "app": str, "shown": str}]}`.
  `fail` 순서 = `check` 가 참인 키(딕셔너리 순서) + `meaning_errors` + `marker_errors` — `eval_ft.py` 와 같다.

- [ ] **Step 1: `has_batchim` 실패 확인**

```bash
cd /Users/parkhyunsik/파이썬/바이브코딩대회/slm_summary
python3 -c "from data import has_batchim as h; assert h('TikTok') and not h('구9'[-1]) and not h('TV') and not h('YouTube') and h('Instagram')"
```
Expected: `AssertionError` (지금은 `TikTok` 이 받침 없음, `9` 가 받침 있음)

- [ ] **Step 2: `has_batchim` 교체**

`data.py` 의 `has_batchim` 전체를 아래로 바꾼다.

```python
LETTER_BATCHIM = "lmnr013678"  # 약어·숫자는 글자 이름으로 읽는다: 엘·엠·엔·알, 영·일·삼·육·칠·팔 (구=9 는 받침 없음)


def has_batchim(word: str) -> bool:
    w = word.strip()
    ch = w[-1]
    if "가" <= ch <= "힣":
        return (ord(ch) - 0xAC00) % 28 != 0
    if w[-2:].isupper() or len(w) == 1 or ch.isdigit():  # TV(티비), KT(케이티), X(엑스)
        return ch.lower() in LETTER_BATCHIM
    # 단어는 소리 기준: TikTok(톡), Instagram(그램), Facebook(북), Bing(빙). 끝 e 는 대개 묵음(YouTube→튜브)
    return w.lower().endswith("ng") or ch.lower() in "lmnrkpt"
```

- [ ] **Step 3: 통과 확인**

```bash
python3 -c "
from data import has_batchim as h, fill
assert h('TikTok') and h('Instagram') and h('치지직') and h('KBL')
assert not h('9') and not h('TV') and not h('YouTube') and not h('아프리카TV') and not h('유튜브')
assert fill('{앱:을} 봤어요', 'TikTok') == 'TikTok을 봤어요'
print('ok')"
```
Expected: `ok`

- [ ] **Step 4: `export_cases.py` 작성**

```python
"""FE 포팅(slmCheck.ts) 대조용 JSON. Python 검사·fill 이 정본이고, TS 가 같은 판정을 내는지 jest 가 확인한다.

    python export_cases.py     # results/slmCases.json → FE __tests__/fixtures/slmCases.json 으로 복사
"""

import json
import re
from pathlib import Path

import bench
from data import fill, marker_errors

HERE = Path(__file__).resolve().parent
SOURCES = ["ft-v2-q4_t0.5_A.json", "ft-v2-q4_t0.5_B.json", "ft-v2-q4_A.json"]
APPS = ["YouTube", "Instagram", "TikTok", "치지직", "아프리카TV", "유튜브", "네이버 웹툰", "TV", "X", "Bing", "KT", "앱9"]


def fail(fact: str, out: str) -> list[str]:
    return ([k for k, v in bench.check([fact], out).items() if v] + bench.meaning_errors([fact], out)
            + marker_errors(fact, out))


def mutations(out: str) -> list[str]:
    """통과한 출력을 일부러 망가뜨린다: 숫자 +1, 방향 뒤집기, 자리표시 지우기·중복, 두 문장, 금지어, 로마자."""
    first = re.search(r"\d+", out)
    muts = [
        out.replace("줄", "늘", 1),
        out.replace("늘", "줄", 1),
        re.sub(r"\{앱(:[^}]*)?\}", "그 앱", out, count=1),
        out + " {앱}도요.",
        out + " 다음 주도 화이팅.",
        out.replace("요", "요 수면", 1),
        out + " ok",
        "",
    ]
    if first:
        muts.append(out[:first.start()] + str(int(first.group()) + 1) + out[first.end():])
    return [m for m in muts if m != out]


def main() -> None:
    rows = [r for name in SOURCES for r in json.loads((HERE / "results" / name).read_text())]
    checks, seen = [], set()
    for r in rows:
        outs = [r["out"]] + (mutations(r["out"]) if not r["fail"] and len(seen) < 400 else [])
        for out in outs:
            if (r["fact"], out) not in seen:
                seen.add((r["fact"], out))
                checks.append({"fact": r["fact"], "out": out, "fail": fail(r["fact"], out)})
    fills = [{"out": r["out"], "app": app, "shown": fill(r["out"], app)}
             for r in rows[:60] for app in APPS if "{앱" in r["out"]]
    path = HERE / "results" / "slmCases.json"
    path.write_text(json.dumps({"checks": checks, "fills": fills}, ensure_ascii=False, indent=1))
    bad = sum(bool(c["fail"]) for c in checks)
    print(f"{path}: 검사 {len(checks)}개(실패 {bad}), fill {len(fills)}개")
    assert bad > 50 and len(checks) - bad > 100 and len(fills) > 100, "통과·실패 사례가 둘 다 충분해야 대조가 의미 있다"


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 실행**

Run: `python3 export_cases.py`
Expected: `검사 N개(실패 M개), fill K개` 출력, assert 통과. 실패 종류가 골고루 있는지 확인:

```bash
python3 -c "import json,collections;d=json.load(open('results/slmCases.json'));print(collections.Counter(f.split()[0] if ' ' in f else f for c in d['checks'] for f in c['fail']).most_common())"
```
Expected: `숫자 오류`, `여러 문장`, `외국 문자`, `금지어`, `빈 출력`, `앱`, `잘못된`, 방향(`…방향(늘)`) 류가 모두 1개 이상.

- [ ] **Step 6: Commit**

```bash
cd /Users/parkhyunsik/파이썬/바이브코딩대회
git add slm_summary/data.py slm_summary/export_cases.py
git commit -m "fix(slm_summary): 영문 앱 이름 받침 판정(TikTok을), FE 대조용 사례 export

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: FE 검사·조사 채우기 포팅 (`slmCheck.ts`)

**Files:**
- Create: `/Users/parkhyunsik/파이썬/petox-FE/src/features/screentime/slmCheck.ts`
- Create: `/Users/parkhyunsik/파이썬/petox-FE/__tests__/slmCheck.test.ts`
- Create: `/Users/parkhyunsik/파이썬/petox-FE/__tests__/fixtures/slmCases.json` (Task 1 산출물 복사)

**Interfaces:**
- Consumes: `slmCases.json` (Task 1)
- Produces (Task 3·4 가 쓴다):
  - `SYSTEM: string`, `APP: '{앱}'`
  - `failures(fact: string, out: string): string[]` — 빈 배열이면 통과
  - `fill(text: string, app: string): string`
  - `hasBatchim(word: string): boolean`
  - `toFact(insight: { code: string; text: string; evidence: Record<string, unknown> }): string`
  - `weekSeed(date: string): number` — `'YYYY-MM-DD'` → epoch day

- [ ] **Step 1: FE 클론·브랜치·의존성**

```bash
cd /Users/parkhyunsik/파이썬
git clone https://github.com/PETOX-MJU/FE.git petox-FE
cd petox-FE && git checkout -b feat/slm-summary && npm install && npx jest 2>&1 | tail -5
cp /Users/parkhyunsik/파이썬/바이브코딩대회/slm_summary/results/slmCases.json __tests__/fixtures/slmCases.json
```
Expected: 기존 테스트 전부 PASS (기준선).

- [ ] **Step 2: 실패하는 테스트 작성** — `__tests__/slmCheck.test.ts`

```ts
import cases from './fixtures/slmCases.json';
import { failures, fill, hasBatchim, toFact, weekSeed } from '../src/features/screentime/slmCheck';

// Python(AI 저장소 slm_summary/export_cases.py)이 낸 판정과 전부 같아야 한다.
test.each(cases.checks.map(c => [c.out, c]))('Python 과 같은 판정: %s', (_out, c) => {
  expect(failures(c.fact, c.out)).toEqual(c.fail);
});

test.each(cases.fills.map(c => [c.app, c.out, c]))('Python 과 같은 fill: %s / %s', (_app, _out, c) => {
  expect(fill(c.out, c.app)).toBe(c.shown);
});

test('영문 앱 이름 조사', () => {
  expect(fill('{앱:을} 가장 많이 봤어요', 'TikTok')).toBe('TikTok을 가장 많이 봤어요');
  expect(fill('{앱:을} 가장 많이 봤어요', 'YouTube')).toBe('YouTube를 가장 많이 봤어요');
  expect(hasBatchim('TV')).toBe(false);
  expect(hasBatchim('9')).toBe(false);
});

test('NIGHT_TOP_APP 만 패키지명을 {앱} 으로 바꾼다', () => {
  const night = {
    code: 'NIGHT_TOP_APP',
    evidence: { package_name: 'com.google.android.youtube' },
    text: '취침 전후로 가장 오래 사용한 앱은 com.google.android.youtube이고 91분입니다. 야간 사용의 50.0%입니다.',
  };
  expect(toFact(night)).toBe('취침 전후로 가장 오래 사용한 앱은 {앱}이고 91분입니다. 야간 사용의 50.0%입니다.');
  const decreased = { code: 'SELECTED_USAGE_DECREASED', evidence: {}, text: '전주 대비 주간 합계가 94분 줄었습니다.' };
  expect(toFact(decreased)).toBe(decreased.text);
});

test('주 시작일 → epoch day (같은 주는 같은 시드)', () => {
  expect(weekSeed('1970-01-02')).toBe(1);
  expect(weekSeed('2026-09-14')).toBe(20710);
});
```

- [ ] **Step 3: 실패 확인**

Run: `npx jest __tests__/slmCheck.test.ts`
Expected: FAIL — `Cannot find module '../src/features/screentime/slmCheck'`

- [ ] **Step 4: 구현** — `src/features/screentime/slmCheck.ts`

```ts
/**
 * 한줄 요약 SLM 출력 검사와 앱 이름 채우기. 네이티브 의존 없는 순수 함수만 둔다.
 *
 * 정본은 AI 저장소 Python 이다: slm_summary/bench.py(check, meaning_errors), data.py(marker_errors, fill, has_batchim).
 * 규칙을 바꿀 때는 Python 을 먼저 고치고 export_cases.py 로 __tests__/fixtures/slmCases.json 을 다시 만든다.
 */

/** 학습 때와 한 글자도 다르면 안 된다 (slm_summary/data.py SYSTEM). */
export const SYSTEM =
  '주간 스크린타임 사실 하나를 펫 캐릭터의 다정한 존댓말 한 문장으로 바꿔라. 숫자와 {앱} 표시는 그대로 옮기고 사실에 없는 말은 하지 마라.';
export const APP = '{앱}';

const JOSA: Record<string, [string, string]> = {
  을: ['을', '를'],
  이: ['이', '가'],
  은: ['은', '는'],
  과: ['과', '와'],
  이었: ['이었', '였'],
  이에: ['이에', '예'],
};
const marker = () => /\{앱(?::(을|이|은|과|이었|이에))?\}/g;
const LETTER_BATCHIM = 'lmnr013678'; // 약어·숫자는 글자 이름으로 읽는다 (구=9 는 받침 없음)

export function hasBatchim(word: string): boolean {
  const w = word.trim();
  const ch = w.slice(-1);
  if (ch >= '가' && ch <= '힣') return (ch.charCodeAt(0) - 0xac00) % 28 !== 0;
  const tail = w.slice(-2);
  const upper = tail === tail.toUpperCase() && tail !== tail.toLowerCase(); // Python str.isupper()
  if (upper || w.length === 1 || /\d/.test(ch)) return LETTER_BATCHIM.includes(ch.toLowerCase());
  return w.toLowerCase().endsWith('ng') || 'lmnrkpt'.includes(ch.toLowerCase());
}

/** `{앱:을}` → "TikTok을". 화면에 보여 주기 직전에 부른다. */
export function fill(text: string, app: string): string {
  return text.replace(marker(), (_m, josa?: string) => {
    if (!josa) return app;
    const [withB, withoutB] = JOSA[josa];
    return app + (hasBatchim(app) ? withB : withoutB);
  });
}

const NUM = /\d+(?:\.\d+)?/g;
const BANNED = /중독|우울|불안|의지|게으|한심|실패자|잠든|수면/;

/** bench.check — 걸린 항목 이름을 Python 딕셔너리 순서대로. */
function check(fact: string, out: string): string[] {
  const factNums = new Set(fact.match(NUM) ?? []);
  const body = out.trim();
  const flags: Array<[string, boolean]> = [
    ['빈 출력', !body],
    ['숫자 오류', (body.match(NUM) ?? []).some(n => !factNums.has(n))],
    ['여러 문장', body.includes('\n') || (body.match(/[.!?](?=\s|$)/g) ?? []).length > 1],
    ['너무 김', Array.from(body).length > 90], // Python len 은 코드 포인트 수
    // 한자·가나는 늘 오류. 로마자는 사실에 나온 것만 허용
    ['외국 문자', /[一-鿿぀-ヿ]/.test(body) || (body.match(/[A-Za-z]+/g) ?? []).some(w => !fact.includes(w))],
    ['금지어', BANNED.test(body)],
  ];
  return flags.filter(([, bad]) => bad).map(([name]) => name);
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** bench.meaning_errors — 단위·방향까지 본다. 숫자는 앞뒤가 숫자가 아닐 때만 같은 숫자로 본다. */
function meaningErrors(fact: string, out: string): string[] {
  const body = out.replace(/(\d)\s+(분|개|일|%)/g, '$1$2');
  const at = (token: string) => {
    const m = new RegExp('(?<![\\d.])' + escapeRe(token)).exec(fact);
    return m ? { start: m.index, end: m.index + m[0].length } : null;
  };
  const errs: string[] = [];
  for (const [, n, unit] of body.matchAll(/(?<![\d.])(\d+(?:\.\d+)?)(분|%)/g)) {
    if (!at(`${n}${unit}`)) errs.push(`${n}${unit} 없음`);
  }
  for (const [, e, s] of body.matchAll(/(?<![\d.])(\d+)개 중 (\d+)개/g)) {
    if (!at(`${e}개 중 ${s}개`)) errs.push(`${e}개 중 ${s}개 없음`);
  }
  for (const m of body.matchAll(/(?<![\d.])(\d+(?:\.\d+)?)(분|%)?[^,.]{0,12}?(늘|증가|많아)/g)) {
    const hit = at(`${m[1]}${m[2] ?? ''}`);
    if (hit && !fact.slice(hit.end, hit.end + 40).includes('늘었')) errs.push(`${m[1]} 방향(늘) 틀림`);
  }
  for (const m of body.matchAll(/(?<![\d.])(\d+(?:\.\d+)?)(분|%)?[^,.]{0,12}?(줄|감소)/g)) {
    const hit = at(`${m[1]}${m[2] ?? ''}`);
    if (hit && !/줄었|변화율/.test(fact.slice(Math.max(0, hit.start - 25), hit.end + 25))) {
      errs.push(`${m[1]} 방향(줄) 틀림`);
    }
  }
  const allDone = Array.from(fact.matchAll(/(\d+)개 중 (\d+)개/g)).some(([, a, b]) => a === b);
  if (/모두 (달성|완료)|다 달성/.test(body) && !allDone) errs.push('모두 달성 아님');
  return errs;
}

/** data.marker_errors — `{앱}` 이 사실에 있으면 정확히 한 번, 없으면 0번. 그 밖의 중괄호는 오류. */
function markerErrors(fact: string, out: string): string[] {
  const want = fact.includes(APP) ? 1 : 0;
  const got = (out.match(marker()) ?? []).length;
  const errs = got === want ? [] : [`앱 표시 ${got}회(기대 ${want})`];
  const rest = out.replace(marker(), '');
  if (rest.includes('{') || rest.includes('}')) errs.push('잘못된 자리표시');
  return errs;
}

/** 걸린 검사 이름들. 빈 배열이어야 화면에 쓴다 (eval_ft.py 의 fail 과 같은 순서). */
export function failures(fact: string, out: string): string[] {
  return [...check(fact, out), ...meaningErrors(fact, out), ...markerErrors(fact, out)];
}

/** 분석기 문장 → 모델에 줄 사실. 분석기는 패키지명을 문장에 넣고, 모델은 `{앱}` 으로 학습했다. */
export function toFact(insight: { code: string; text: string; evidence: Record<string, unknown> }): string {
  const pkg = insight.evidence.package_name;
  return insight.code === 'NIGHT_TOP_APP' && typeof pkg === 'string' ? insight.text.split(pkg).join(APP) : insight.text;
}

/** 리포트 주 시작일 → epoch day. 생성 시드로 써서 같은 주는 같은 문장이 나오게 한다. */
export function weekSeed(date: string): number {
  const [y, m, d] = date.split('-').map(Number);
  return Date.UTC(y, m - 1, d) / 86_400_000;
}
```

- [ ] **Step 5: 통과 확인**

Run: `npx jest __tests__/slmCheck.test.ts`
Expected: PASS (대조 사례 전부). 하나라도 다르면 **TS 를 고친다** — Python 이 정본이다.

- [ ] **Step 6: Commit**

```bash
git add src/features/screentime/slmCheck.ts __tests__/slmCheck.test.ts __tests__/fixtures/slmCases.json
git commit -m "feat(screentime): 한줄 요약 SLM 출력 검사·앱 이름 채우기 (AI 저장소 Python 과 대조)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 대시보드 모델 — 제목·앱 이름·SLM 입력 필드

**Files:**
- Modify: `src/features/screentime/dashboard.ts` (`AnalysisOutput` 타입, `toDashboardModel` 반환값, 새 함수 2개)
- Test: `__tests__/screentimeDashboard.test.ts`

**Interfaces:**
- Consumes: 없음
- Produces (Task 5 가 쓴다):
  - `AnalysisOutput.insights: Array<{ code: string; text: string; evidence: Record<string, unknown> }>`
  - `toDashboardModel(...)` 반환값에 `insight: AnalysisOutput['insights'][number] | null`, `weekStart: string | null` 추가
  - `summaryTitle(petName: string | null | undefined): string`
  - `appName(packageName: string): string`

- [ ] **Step 1: 실패하는 테스트 추가** — `__tests__/screentimeDashboard.test.ts` 끝에

```ts
import { appName, summaryTitle } from '../src/features/screentime/dashboard';

test('한줄 요약 제목에 반려견 이름을 단다', () => {
  expect(summaryTitle('초코')).toBe('초코의 한줄 요약');
  expect(summaryTitle('  ')).toBe('한줄 요약');
  expect(summaryTitle(null)).toBe('한줄 요약');
  expect(summaryTitle('가나다라마바사아자')).toBe('가나다라마바사아…의 한줄 요약');
});

test('앱 표시명은 APP_META 이름, 없으면 패키지명', () => {
  expect(appName('com.zhiliaoapp.musically')).toBe('TikTok');
  expect(appName('com.example.unknown')).toBe('com.example.unknown');
});

test('SLM 입력으로 첫 insight 와 주 시작일을 넘긴다', () => {
  const dashboard = toDashboardModel(preview);
  expect(dashboard.insight?.code).toBe('SELECTED_USAGE_DECREASED');
  expect(dashboard.weekStart).toBe('2026-09-14');
});
```

(`import` 줄은 파일 맨 위 기존 import 옆으로 옮긴다.)

- [ ] **Step 2: 실패 확인**

Run: `npx jest __tests__/screentimeDashboard.test.ts`
Expected: FAIL — `summaryTitle is not a function` 등

- [ ] **Step 3: 구현** — `dashboard.ts`

`AnalysisOutput` 의 `insights` 줄을 바꾼다:

```ts
  insights: Array<{ code: string; text: string; evidence: Record<string, unknown> }>;
```

`APP_META` 선언 바로 아래에 추가:

```ts
/** 한줄 요약 문장에 넣을 앱 표시명. */
export const appName = (packageName: string) => APP_META[packageName]?.name ?? packageName;

const MAX_PET_NAME = 8; // 스티커가 넘치지 않게. 이름 입력에는 길이 제한이 없다.

/** "초코의 한줄 요약". 이름이 없으면(로그인 전·프로필 없음) "한줄 요약". "의" 는 받침과 상관없이 붙는다. */
export function summaryTitle(petName: string | null | undefined): string {
  const name = Array.from(petName?.trim() ?? '');
  if (!name.length) return '한줄 요약';
  const shown = name.length > MAX_PET_NAME ? `${name.slice(0, MAX_PET_NAME).join('')}…` : name.join('');
  return `${shown}의 한줄 요약`;
}
```

`toDashboardModel` 의 `summary:` 줄 아래에 추가:

```ts
    // SLM 이 바꿔 쓸 원문과 시드용 주 시작일
    insight: output.insights[0] ?? null,
    weekStart: output.metrics.per_day[0]?.date ?? null,
```

- [ ] **Step 4: 통과 확인**

Run: `npx jest __tests__/screentimeDashboard.test.ts && npx tsc --noEmit`
Expected: PASS, 타입 오류 없음

- [ ] **Step 5: Commit**

```bash
git add src/features/screentime/dashboard.ts __tests__/screentimeDashboard.test.ts
git commit -m "feat(screentime): 한줄 요약 제목에 반려견 이름, SLM 입력 필드

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: llama.rn 생성 (`slm.ts`)

**Files:**
- Modify: `package.json` (`llama.rn` 추가)
- Create: `src/features/screentime/slm.ts`
- Modify: `jest.setup.js` (`llama.rn` 목)
- Test: `__tests__/slm.test.ts`

**Interfaces:**
- Consumes: `SYSTEM`, `failures`, `fill` (Task 2)
- Produces (Task 5 가 쓴다): `rewriteSummary(fact: string, app: string, seed: number): Promise<string | null>` — 검사를 통과해 앱 이름까지 채운 문장, 아니면 `null`. 호출이 겹쳐도 모델은 한 번에 하나만 올리고, 같은 `(fact, seed)` 는 다시 생성하지 않는다.

- [ ] **Step 1: 설치**

```bash
npm install llama.rn
ls node_modules/llama.rn/android/src/main/jniLibs
```
Expected: `arm64-v8a`, `x86_64` 등 ABI 폴더(postinstall 이 GitHub 릴리스에서 받아 SHA-256 검증). 비어 있으면 `node ./node_modules/llama.rn/install/download-native-artifacts.js`.
`android/app/build.gradle` 은 `enableProguardInReleaseBuilds = false` 라 proguard 규칙은 필요 없다.

- [ ] **Step 2: jest 목** — `jest.setup.js` 끝에

```js
// 네이티브 모델 런타임. 테스트는 __tests__/slm.test.ts 에서 동작을 따로 정한다.
jest.mock('llama.rn', () => ({ initLlama: jest.fn(async () => { throw new Error('jest: 모델 없음'); }) }));
```

- [ ] **Step 3: 실패하는 테스트** — `__tests__/slm.test.ts`

```ts
const FACT = '지난주 선택한 앱 사용량은 하루 평균 38분입니다. 전주 대비 주간 합계가 29분 줄었습니다. 변화율은 9.8%입니다.';
const NIGHT = '취침 전후로 가장 오래 사용한 앱은 {앱}이고 32분입니다.';

function fakeContext(content: string, delayMs = 0) {
  return {
    completion: jest.fn(() => new Promise(r => setTimeout(() => r({ content, timings: { predicted_per_second: 20 } }), delayMs))),
    stopCompletion: jest.fn(async () => {}),
    release: jest.fn(async () => {}),
  };
}

// 모듈 안의 메모·대기열을 테스트마다 비운다. resetModules 뒤에는 llama.rn 목도 새 인스턴스라 다시 require 한다.
let rewriteSummary: typeof import('../src/features/screentime/slm').rewriteSummary;
let init: jest.Mock;
beforeEach(() => {
  jest.resetModules();
  init = require('llama.rn').initLlama;
  jest.spyOn(console, 'log').mockImplementation(() => {});
  jest.spyOn(console, 'warn').mockImplementation(() => {});
  ({ rewriteSummary } = require('../src/features/screentime/slm'));
});
afterEach(() => jest.useRealTimers());

test('검사를 통과하면 앱 이름을 채워 돌려주고 모델을 해제한다', async () => {
  const ctx = fakeContext('밤 시간엔 {앱:을} 32분 봤어요.');
  init.mockResolvedValue(ctx);
  await expect(rewriteSummary(NIGHT, 'TikTok', 1)).resolves.toBe('밤 시간엔 TikTok을 32분 봤어요.');
  expect(ctx.completion).toHaveBeenCalledWith(expect.objectContaining({
    jinja: true, enable_thinking: false, n_predict: 80, temperature: 0.5, seed: 1,
  }));
  expect(ctx.release).toHaveBeenCalled();
});

test('검사에 걸리면 null (숫자가 사실에 없음)', async () => {
  init.mockResolvedValue(fakeContext('그 전주보다 30분 줄였어요!'));
  await expect(rewriteSummary(FACT, 'YouTube', 1)).resolves.toBeNull();
});

test('모델 파일이 없으면(초기화 실패) null', async () => {
  init.mockRejectedValue(new Error('failed to load model'));
  await expect(rewriteSummary(FACT, 'YouTube', 1)).resolves.toBeNull();
});

test('15초가 지나면 null, 생성을 멈추고 해제한다', async () => {
  jest.useFakeTimers();
  const ctx = fakeContext('그 전주보다 29분 줄였어요!', 60_000);
  init.mockResolvedValue(ctx);
  const result = rewriteSummary(FACT, 'YouTube', 1);
  await jest.advanceTimersByTimeAsync(15_000);
  await jest.advanceTimersByTimeAsync(60_000);
  await expect(result).resolves.toBeNull();
  expect(ctx.stopCompletion).toHaveBeenCalled();
  expect(ctx.release).toHaveBeenCalled();
});

test('불러오는 중 시간 초과여도 적재가 끝나면 해제한다', async () => {
  jest.useFakeTimers();
  const ctx = fakeContext('그 전주보다 29분 줄였어요!');
  init.mockImplementation(() => new Promise(r => setTimeout(() => r(ctx), 20_000)));
  const result = rewriteSummary(FACT, 'YouTube', 1);
  await jest.advanceTimersByTimeAsync(25_000);
  await expect(result).resolves.toBeNull();
  expect(ctx.release).toHaveBeenCalled();
});

test('겹친 호출도 모델은 한 번에 하나만 올린다', async () => {
  let live = 0;
  let peak = 0;
  init.mockImplementation(async () => {
    peak = Math.max(peak, ++live);
    const ctx = fakeContext('그 전주보다 29분 줄였어요!', 10);
    ctx.release.mockImplementation(async () => { live--; });
    return ctx;
  });
  await Promise.all([rewriteSummary(FACT, 'YouTube', 1), rewriteSummary(FACT, 'YouTube', 2)]);
  expect(peak).toBe(1);
});

test('같은 사실·시드는 다시 생성하지 않는다 (앱 복귀 때마다 재분석)', async () => {
  init.mockResolvedValue(fakeContext('그 전주보다 29분 줄였어요!'));
  await rewriteSummary(FACT, 'YouTube', 1);
  await rewriteSummary(FACT, 'YouTube', 1);
  expect(init).toHaveBeenCalledTimes(1);
});
```

- [ ] **Step 4: 실패 확인**

Run: `npx jest __tests__/slm.test.ts`
Expected: FAIL — `Cannot find module '../src/features/screentime/slm'`

- [ ] **Step 5: 구현** — `src/features/screentime/slm.ts`

```ts
import { initLlama, type LlamaContext } from 'llama.rn';
import { SYSTEM, failures, fill } from '@/features/screentime/slmCheck';

// ponytail: 시연용 고정 경로 — adb 로 넣는다(AI 저장소 slm_summary/README). 배포 때는 모델 다운로드로 바꾼다.
const MODEL_PATH = 'file:///data/data/com.petoxmju.petox/files/ft-v2-q4.gguf';
const TIMEOUT_MS = 15_000;

let queue: Promise<unknown> = Promise.resolve();
let last: { key: string; out: string | null } | null = null;

/**
 * 분석기 사실 하나를 반려견 말투 한 문장으로. 검사를 통과해 앱 이름까지 채운 문장, 아니면 null.
 * null 이면 호출하는 쪽이 템플릿 문장을 그대로 쓴다.
 *
 * 모델은 1GB 가까이 메모리를 쓴다. 호출을 줄 세워 동시에 두 개를 올리지 않고,
 * 대시보드가 앱 복귀 때마다 다시 분석해도 같은 사실·시드면 지난 결과를 쓴다.
 */
export function rewriteSummary(fact: string, app: string, seed: number): Promise<string | null> {
  const key = `${seed}\n${fact}`;
  const run = async () => {
    if (last?.key !== key) last = { key, out: await generate(fact, seed) };
    return last.out === null ? null : fill(last.out, app);
  };
  const result = queue.then(run, run);
  queue = result.catch(() => {});
  return result;
}

async function generate(fact: string, seed: number): Promise<string | null> {
  const started = Date.now();
  const held: { ctx?: LlamaContext } = {};
  const work = (async () => {
    held.ctx = await initLlama({ model: MODEL_PATH, n_ctx: 512, n_threads: 4, n_gpu_layers: 0, use_mlock: false });
    const loadedMs = Date.now() - started;
    const result = await held.ctx.completion({
      messages: [
        { role: 'system', content: SYSTEM },
        { role: 'user', content: `사실: ${fact}` },
      ],
      jinja: true,
      enable_thinking: false,
      n_predict: 80,
      temperature: 0.5,
      seed,
    });
    return { result, loadedMs };
  })();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<null>(resolve => {
    timer = setTimeout(() => resolve(null), TIMEOUT_MS);
  });
  try {
    const done = await Promise.race([work, timeout]);
    if (done === null) {
      console.warn('[slm] 15초 초과, 템플릿 사용');
      return null;
    }
    const out = done.result.content.trim();
    const errs = failures(fact, out);
    // 시연 중 logcat(ReactNativeJS)으로 속도·판정을 본다
    console.log(
      `[slm] 적재 ${done.loadedMs}ms, 전체 ${Date.now() - started}ms, ${done.result.timings.predicted_per_second.toFixed(1)} tok/s`,
      errs.length ? `검사 실패 ${errs.join(', ')}` : '통과',
      out,
    );
    return errs.length ? null : out;
  } catch (e) {
    console.warn('[slm] 템플릿 사용:', e instanceof Error ? e.message : e);
    return null;
  } finally {
    clearTimeout(timer);
    // 시간 초과면 생성을 멈추고, 적재 중이었다면 끝날 때까지 기다렸다가 해제한다.
    await held.ctx?.stopCompletion().catch(() => {});
    await work.catch(() => {});
    await held.ctx?.release().catch(() => {});
  }
}
```

- [ ] **Step 6: 통과 확인**

Run: `npx jest && npx tsc --noEmit`
Expected: 전부 PASS (`App.test.tsx` 포함 — `llama.rn` 목 덕분), 타입 오류 없음.
`LlamaContext` 타입 import 가 안 되면 `type LlamaContext = Awaited<ReturnType<typeof initLlama>>` 로 바꾼다.

- [ ] **Step 7: Commit**

```bash
git add package.json package-lock.json jest.setup.js src/features/screentime/slm.ts __tests__/slm.test.ts
git commit -m "feat(screentime): 온디바이스 SLM 한줄 요약 생성 (llama.rn, 검사 실패 시 템플릿)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: 대시보드 화면 연결

**Files:**
- Modify: `src/screens/ScreentimeDashboardScreen.tsx` (import, 새 훅 2개, `AnalysisSections`, 스타일 없음)

**Interfaces:**
- Consumes: `rewriteSummary` (Task 4), `toFact`, `weekSeed` (Task 2), `summaryTitle`, `appName`, `keepWords`, `DashboardModel.insight/weekStart` (Task 3), `loadPetProfile` (`@/storage/petProfile`, 기존)
- Produces: 없음 (화면)

- [ ] **Step 1: import 추가**

```ts
import {
  appName,
  keepWords,
  localDateKey,
  monthCalendar,
  summaryTitle,
  toDashboardModel,
  toMissionCards,
  type DashboardModel,
  type MissionRow,
} from '@/features/screentime/dashboard';
import { rewriteSummary } from '@/features/screentime/slm';
import { toFact, weekSeed } from '@/features/screentime/slmCheck';
import { loadPetProfile } from '@/storage/petProfile';
```

- [ ] **Step 2: 훅 2개 추가** — `useOnDeviceAnalysis` 아래에

```ts
// 온보딩에서 지은 반려견 이름. 로그인 전·프로필 없음이면 null.
function usePetName(): string | null {
  const [name, setName] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    loadPetProfile()
      .then(profile => alive && setName(profile?.name ?? null))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);
  return name;
}

// 템플릿 문장을 먼저 보여 주고, SLM 문장이 검사를 통과하면 바꾼다. 실패하면 null 로 남아 템플릿 유지.
// 의존성을 문자열·숫자로 둔다: 앱 복귀 때마다 분석 객체가 새로 만들어져도 내용이 같으면 다시 돌지 않아 깜빡이지 않는다.
function useSlmSummary(dashboard: DashboardModel | null): string | null {
  const [text, setText] = useState<string | null>(null);
  const insight = dashboard?.insight ?? null;
  const fact = insight ? toFact(insight) : null;
  const pkg = insight?.evidence.package_name;
  const app = typeof pkg === 'string' ? appName(pkg) : '';
  const seed = dashboard?.weekStart ? weekSeed(dashboard.weekStart) : null;
  useEffect(() => {
    setText(null);
    if (fact === null || seed === null) return;
    let alive = true;
    rewriteSummary(fact, app, seed).then(out => alive && setText(out));
    return () => {
      alive = false;
    };
  }, [fact, app, seed]);
  return text;
}
```

- [ ] **Step 3: `AnalysisSections` 수정**

시그니처와 한줄 요약 블록을 바꾼다 (따옴표 제거, 이름 제목, SLM 문장 우선):

```tsx
function AnalysisSections({
  dashboard,
  chartWidth,
  title,
  slmText,
}: {
  dashboard: DashboardModel;
  chartWidth: number;
  title: string;
  slmText: string | null;
}) {
  const summary = slmText ? keepWords(slmText) : dashboard.summary;
  return (
    <>
        {summary && (
          <>
            <Sticker label={title} color={tone.summary} />
            <Text style={styles.summaryText}>{summary}</Text>
            <Divider />
          </>
        )}
```

(나머지 `AnalysisSections` 본문은 그대로.)

- [ ] **Step 4: 화면에서 호출**

`ScreentimeDashboardScreen` 안 `const analysis = useOnDeviceAnalysis();` 아래에:

```ts
  const petName = usePetName();
  const slmText = useSlmSummary(analysis.status === 'ready' ? analysis.dashboard : null);
```

`<AnalysisSections` 를 렌더하는 곳(파일 아래쪽, `analysis.status === 'ready'` 분기)에 prop 두 개를 더한다:

```tsx
<AnalysisSections dashboard={analysis.dashboard} chartWidth={chartWidth} title={summaryTitle(petName)} slmText={slmText} />
```

- [ ] **Step 5: 확인**

Run: `npx tsc --noEmit && npx jest && npx eslint src/screens/ScreentimeDashboardScreen.tsx src/features/screentime`
Expected: 전부 통과.
앱 복귀로 재분석해도 사실·시드가 같으면 효과가 다시 돌지 않는다(의존성이 문자열·숫자). 주가 바뀌어 다시 돌면 `rewriteSummary` 가 새로 생성한다.

- [ ] **Step 6: Commit**

```bash
git add src/screens/ScreentimeDashboardScreen.tsx
git commit -m "feat(dashboard): 반려견 이름 한줄 요약 제목, SLM 문장 표시, 따옴표 제거

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: 에뮬레이터에서 동작 확인 + FE PR

**Files:**
- Modify: `/Users/parkhyunsik/파이썬/바이브코딩대회/slm_summary/README.md` (「앱 연결 (시연)」 절: 모델 넣는 명령)

**Interfaces:**
- Consumes: Task 1~5 전부, 모델 `slm_summary/models/ft-v2-q4.gguf`
- Produces: 스크린샷 2장, FE PR

- [ ] **Step 1: 에뮬레이터 부팅·앱 설치**

```bash
export PATH="$HOME/Library/Android/sdk/platform-tools:$HOME/Library/Android/sdk/emulator:$PATH"
emulator -avd Pixel_8 -no-snapshot-save &
adb wait-for-device && adb shell getprop ro.product.cpu.abi
cd /Users/parkhyunsik/파이썬/petox-FE && npm run android
```
Expected: ABI `arm64-v8a`, 앱 실행. (Metro 는 `npm start` 가 따로 떠 있어야 한다. 빌드 오류는 kotlin-build-resolver 로.)

- [ ] **Step 2: 모델 없이 확인 (템플릿 경로)**

앱에서 로그인 → 사용 정보 접근 허용 → 대시보드. `adb logcat -s ReactNativeJS | grep slm` 에서
`[slm] 템플릿 사용: …` 가 보이고, 화면은 `${이름}의 한줄 요약` + 따옴표 없는 템플릿 문장.
스크린샷: `adb exec-out screencap -p > /tmp/…/dashboard-template.png` (scratchpad 에 저장)

- [ ] **Step 3: 모델 넣기**

```bash
adb push /Users/parkhyunsik/파이썬/바이브코딩대회/slm_summary/models/ft-v2-q4.gguf /data/local/tmp/
adb shell "cat /data/local/tmp/ft-v2-q4.gguf | run-as com.petoxmju.petox sh -c 'mkdir -p files && cat > files/ft-v2-q4.gguf'"
adb shell run-as com.petoxmju.petox ls -l files/
adb shell rm /data/local/tmp/ft-v2-q4.gguf
```
Expected: `files/ft-v2-q4.gguf` 약 541MB (568,000,000 바이트 안팎, 로컬 `ls -l` 과 같은 크기).

- [ ] **Step 4: 모델로 확인 (SLM 경로)**

앱을 완전히 종료 후 재실행(메모가 지난 실패를 기억한다) → 대시보드.
logcat 에 `[slm] 적재 …ms, 전체 …ms, … tok/s 통과 …` 가 보이고 화면 문장이 반려견 말투로 바뀐다.
**`검사 실패` 가 뜨면** 문장·실패 항목을 기록한다 — 기기(Hermes) 정규식 차이인지 Python 으로 같은 입력을 돌려 대조한다
(`python3 -c "import bench,data; print(bench.check([FACT], OUT), bench.meaning_errors([FACT], OUT), data.marker_errors(FACT, OUT))"`).
스크린샷: `dashboard-slm.png`. 에뮬레이터 속도는 실기기를 대표하지 않는다 — 수치는 기록만.

- [ ] **Step 5: README 에 시연 절 추가** — `slm_summary/README.md` 의 「설계」 절 위 인용문(`> 아직 앱에 붙이지 않았다 …`)을 바꾼다

```markdown
> **앱 연결(시연):** FE `feat/slm-summary` 가 대시보드 한줄 요약(`insights[0]`)을 이 모델로 바꿔 쓴다. 분석기 출력 계약은 그대로
> (`source: "template"`)이고, 검사에 실패하거나 모델이 없으면 템플릿 문장을 쓴다. 모델은 디버그 빌드에 adb 로 넣는다:
>
> ```bash
> adb push models/ft-v2-q4.gguf /data/local/tmp/
> adb shell "cat /data/local/tmp/ft-v2-q4.gguf | run-as com.petoxmju.petox sh -c 'mkdir -p files && cat > files/ft-v2-q4.gguf'"
> ```
>
> 검사 규칙을 바꾸면 `python export_cases.py` 결과를 FE `__tests__/fixtures/slmCases.json` 으로 복사한다.
```

- [ ] **Step 6: Commit·push (두 저장소)**

```bash
cd /Users/parkhyunsik/파이썬/바이브코딩대회 && git add slm_summary/README.md
git commit -m "docs(slm_summary): 앱 연결 시연 방법

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && git push
cd /Users/parkhyunsik/파이썬/petox-FE && git push -u origin feat/slm-summary
```

- [ ] **Step 7: FE PR** — 사용자 확인 뒤 `gh pr create --repo PETOX-MJU/FE --base main` (본문: 무엇이 바뀌는지, 모델 넣는 법, 스크린샷 2장 설명, 실기기 측정 전이라는 점, 끝에 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`)

---

### Task 7: 실기기 측정 + 루트 README 결정 갱신 (폰 연결 필요)

**Files:**
- Modify: `/Users/parkhyunsik/파이썬/바이브코딩대회/README.md` 「온디바이스 LLM — 검토했고 도입하지 않는다」 절
- Modify: `slm_summary/README.md` (실기기 수치 표)

**Interfaces:**
- Consumes: Task 6 의 FE 빌드, 폰(USB 디버깅)
- Produces: 기기명·RAM, 적재 시간, 생성 tok/s, 메모리 최대치

- [ ] **Step 1: 설치·모델 넣기** — Task 6 Step 3 과 같은 명령을 폰에 (`adb -s <기기> …`). `npm run android -- --deviceId <기기>`.

- [ ] **Step 2: 기기 정보**

```bash
adb shell getprop ro.product.model; adb shell getprop ro.soc.model; adb shell cat /proc/meminfo | head -1
```

- [ ] **Step 3: 메모리 최대치 재기** — 한 터미널에서 샘플링을 켠 채 앱을 재시작하고 대시보드를 연다

```bash
while true; do adb shell dumpsys meminfo com.petoxmju.petox | grep -E "TOTAL PSS|TOTAL:" | head -1; sleep 0.5; done | tee /tmp/…/meminfo.log
```
Expected: 생성 중 최대값을 기록(KB). logcat 의 `[slm] 적재 …ms, 전체 …ms, … tok/s` 도 기록. 3회 반복해 중앙값.

- [ ] **Step 4: README 갱신**

루트 README 「온디바이스 LLM」 절 제목을 `## 온디바이스 LLM — 한줄 요약에 선택 기능으로 시험 중` 으로 바꾸고, 표 아래에 한 단락:
실측 기기·RAM·메모리 최대치·적재/생성 시간, "분석기는 계속 템플릿만 만들고 FE 가 `insights[0]` 을 바꿔 쓴다.
모델이 없거나 검사에 실패하면 템플릿이 그대로 나간다. 배포(모델 다운로드·기기 판별·AI 표시)는 결정 전" 을 쓴다.
`slm_summary/README.md` 결과 절에 실기기 수치 표를 추가한다. 숫자는 Step 2·3 의 실측값만 쓴다.

- [ ] **Step 5: Commit·push**

```bash
cd /Users/parkhyunsik/파이썬/바이브코딩대회 && git add README.md slm_summary/README.md
git commit -m "docs: 한줄 요약 SLM 실기기 측정, 온디바이스 LLM 결정 갱신

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && git push
```
