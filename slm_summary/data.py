"""파인튜닝 데이터. 입력은 분석기 evidence 의 수치를 줄마다 하나씩 적은 것이고, 정답은 펫 말투 틀에 숫자를 코드로 넣는다.

v4: 입력을 분석기 템플릿 문장이 아니라 수치 줄(`주간 감소량: 298분`)로 바꿨다. 정답 틀은 v3 그대로라서 입력 형식만의 효과를 볼 수 있다.
계산은 여전히 분석기 몫이다 — 모델은 받은 수치를 옮기고 종류·방향 라벨에 맞는 말을 고른다.

v2: 앱 이름은 모델에 넣지 않는다. 사실에는 `{앱}`, 정답에는 조사까지 표시한 `{앱:을}` 같은 자리표시를 쓰고
생성 뒤 [fill] 이 실제 이름과 받침에 맞는 조사로 바꾼다. 처음 보는 앱 이름(치지직 → 치지icks)이 깨지던 문제를 없앤다.

    python data.py        # data/train.jsonl, valid.jsonl, test_b.jsonl
"""

import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSTEM = "주간 스크린타임 수치를 펫 캐릭터의 다정한 존댓말 한 문장으로 써라. 숫자와 {앱} 표시는 그대로 옮기고 수치에 없는 말은 하지 마라."
APP = "{앱}"
PURPOSES = ["학습", "업무", "여가", "연락", "기타"]

# 자리표시 → (받침 있을 때, 없을 때)
JOSA = {"을": ("을", "를"), "이": ("이", "가"), "은": ("은", "는"), "과": ("과", "와"), "이었": ("이었", "였"), "이에": ("이에", "예")}
MARKER = re.compile(r"\{앱(?::(" + "|".join(JOSA) + r"))?\}")


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


def fill(text: str, app: str) -> str:
    """`{앱:을}` → "유튜브를". 앱 화면에 보여 주기 직전에 부른다."""
    def one(m: re.Match) -> str:
        if not m.group(1):
            return app
        with_b, without_b = JOSA[m.group(1)]
        return app + (with_b if has_batchim(app) else without_b)
    return MARKER.sub(one, text)


def a(josa: str = "") -> str:
    return "{앱:" + josa + "}" if josa else APP


# ── 입력 수치 (분석기 evidence 를 줄마다 하나씩) ────────────────────────────
# 라벨에 방향을 담는다(감소량·증가량). bench.meaning_errors 가 숫자가 붙은 줄의 라벨로 방향 말을 검사한다.
# FE 의 toFact 가 같은 줄을 만든다 — 바꾸면 양쪽을 같이 고친다.

def fact_decreased(dropped: int, mean: int | None, pct: float | None) -> str:
    lines = ["종류: 관리 앱 사용 감소"]
    if mean is not None:
        lines.append(f"하루 평균: {mean}분")
    lines.append(f"주간 감소량: {dropped}분")
    if pct is not None:
        lines.append(f"감소율: {pct:.1f}%")
    return "\n".join(lines)


def fact_other(other: int) -> str:
    return f"종류: 관리 앱 감소, 다른 앱 증가\n다른 앱 증가량: {other}분"


def fact_night(mins: int, share: float | None, purpose: str | None) -> str:
    lines = ["종류: 야간 최다 사용 앱", f"앱: {APP}", f"야간 사용: {mins}분"]
    if share is not None:
        lines.append(f"야간 비중: {share:.1f}%")
    if purpose:
        lines.append(f"사용 목적: {purpose}")
    return "\n".join(lines)


def mission_phrase(s: int, e: int) -> str:
    return "판정 가능한 미션 없음" if e == 0 else f"{e}개 중 {s}개 달성"


def fact_missions(ds: int, de: int, ns: int, ne: int) -> str:
    return f"종류: 미션 결과\n일일 미션: {mission_phrase(ds, de)}\n야간 미션: {mission_phrase(ns, ne)}"


def fact_insufficient(days: int, nights: int, active: bool) -> str:
    goal = "기존 목표 유지" if active else "임시 목표 사용"
    return f"종류: 기록 부족\n확인된 날: {days}일\n확인된 야간 구간: {nights}개\n필요한 기록: 각각 7개\n목표: {goal}"


# ── 정답 (펫 말투). 숫자는 코드가 넣는다 ─────────────────────────────────────

def target_decreased(rng, dropped, mean, pct) -> str:
    d = f"{dropped}분"
    opts = [
        f"지난주는 그 전주보다 {d}이나 줄였어요, 정말 잘했어요!",
        f"지난주 사용 시간이 그 전주보다 {d} 줄었어요, 이 흐름 그대로 가봐요.",
        f"그 전주보다 {d} 덜 썼어요, 조금씩 달라지고 있어요.",
        f"지난주엔 {d}을 되찾았어요, 그 전주보다 확실히 줄었네요.",
        f"한 주 동안 {d}을 줄였어요, 멋져요!",
        f"지난주는 그 전주보다 {d} 줄었어요, 그만큼 다른 일에 쓸 수 있었겠네요.",
        f"와, 그 전주보다 {d}이나 덜 썼어요!",
        f"지난주에 줄인 시간은 {d}이에요, 꾸준히 해봐요.",
        f"그 전주보다 {d} 줄인 한 주, 정말 수고했어요.",
    ]
    if pct is not None:
        p = f"{pct:.1f}%"
        opts += [
            f"지난주 사용 시간을 그 전주보다 {p} 줄였어요, 대단해요!",
            f"그 전주보다 {p}, {d}이나 줄었어요, 잘하고 있어요.",
            f"지난주는 사용 시간이 {p} 줄었어요, 이대로만 해요.",
            f"{d}, 비율로는 {p}를 줄인 한 주였어요.",
        ]
    if mean is not None:
        m = f"{mean}분"
        opts += [
            f"지난주 하루 평균은 {m}이고, 그 전주보다 {d} 줄였어요.",
            f"그 전주보다 {d} 줄여서 지난주는 하루 평균 {m}을 썼어요.",
            f"하루 평균 {m}, 그 전주보다 {d} 줄어든 한 주였어요.",
            f"지난주는 하루에 평균 {m}을 썼고, 그 전주보다 {d} 덜 썼어요.",
        ]
    return rng.choice(opts)


def target_other(rng, other) -> str:
    o = f"{other}분"
    return rng.choice([
        f"관리하는 앱은 줄었지만 다른 앱 사용이 {o} 늘었어요.",
        f"관리하는 앱은 잘 줄였는데, 다른 앱에서 {o} 더 썼어요.",
        f"다른 앱 사용이 {o} 늘었어요, 관리하는 앱은 잘 줄였고요.",
        f"관리 앱은 줄었고 다른 앱은 {o} 늘었어요, 한번 살펴볼까요?",
        f"관리하는 앱 대신 다른 앱을 {o} 더 쓴 한 주였어요.",
        f"관리하는 앱은 줄었어요, 다만 다른 앱이 {o} 늘었네요.",
        f"줄인 앱 말고 다른 앱에서 {o}이 늘었어요.",
        f"다른 앱 쪽 사용이 {o} 늘었어요, 관리하는 앱은 줄였어요.",
    ])


def target_night(rng, mins, share, purpose) -> str:
    n = f"{mins}분"
    opts = [
        f"밤에는 {a('을')} 가장 오래 썼어요, {n}이었어요.",
        f"잠들기 전후로 {a('을')} {n} 썼어요.",
        f"밤에 가장 많이 쓴 앱은 {a()}, {n}이에요.",
        f"밤 시간엔 {a()}에서 {n}을 보냈어요.",
        f"취침 전후로는 {a('이')} {n}으로 가장 길었어요.",
        f"밤에 제일 오래 붙잡은 앱은 {a('이었')}어요, {n}이요.",
        f"잘 시간 즈음엔 {a('을')} {n} 봤어요.",
    ]
    if share is not None:
        s = f"{share:.1f}%"
        opts += [
            f"밤 사용의 {s}가 {a('이었')}어요, {n}이었어요.",
            f"밤에는 {a('을')} {n} 썼어요, 밤 사용의 {s}예요.",
            f"밤 사용의 {s}를 {a('이')} 차지했어요.",  # v2 의 "밤 시간의" 는 틀린 말이었다: 밤 시간 전체가 아니라 관리 앱 야간 사용 중 비중
        ]
    if purpose:
        opts += [
            # 용도는 문장 끝에만 둔다. v2 에서 "'{용도}'용으로 정한 …" 으로 시작하는 틀이 비중 틀과 섞여
            # "'학습'용 92.8%를 틱톡이 차지했어요" 같은 문장이 나왔다
            f"밤엔 {a('을')} {n} 썼어요, '{purpose}' 용도로 정해 둔 앱이에요.",
            f"잠들기 전후로 {a('을')} {n} 썼어요, '{purpose}'용으로 정해 둔 앱이죠.",
        ]
    return rng.choice(opts)


def mission_clause(rng, kind: str, s: int, e: int) -> str:
    if e == 0:
        return rng.choice([f"{kind} 미션은 판정할 수 있는 날이 없었어요", f"{kind} 미션은 이번엔 판정할 게 없었어요"])
    if s == e:
        return rng.choice([f"{kind} 미션 {e}개를 모두 해냈어요", f"{kind} 미션은 {e}개 중 {s}개, 전부 성공이에요"])
    if s == 0:
        return rng.choice([f"{kind} 미션은 {e}개 중 {s}개로 아쉬웠어요", f"{kind} 미션은 {e}개 중 {s}개였지만 다음엔 해낼 수 있어요"])
    return rng.choice([f"{kind} 미션은 {e}개 중 {s}개 해냈어요", f"{kind} 미션 {e}개 중 {s}개를 달성했어요"])


def target_missions(rng, ds, de, ns, ne) -> str:
    # 두 미션을 한 절로 묶는 틀("일일 …, 야간 … 미션을 전부 성공했어요")은 쓰지 않는다. 0.8B 는 이 틀의 앞부분만 보고
    # 뒤를 "전부 성공"으로 이어 붙여, 일일 5개 중 0개인 주에도 전부 성공이라고 썼다(v3a·v3b). 두 절로 나눠 절마다 판정한다
    daily, night = mission_clause(rng, "일일", ds, de), mission_clause(rng, "야간", ns, ne)
    return rng.choice([f"{daily}, {night}.", f"이번 주 {daily}, {night}."])


def target_insufficient(rng, days, nights, active) -> str:
    if active:
        return rng.choice([
            f"기록이 {days}일, 밤 {nights}개만 모여서 지금 목표를 그대로 둘게요.",
            f"확인된 날이 {days}일이라 이번 주는 목표를 바꾸지 않고 유지해요.",
            f"이번 주는 기록이 {days}일치라 지금 목표를 그대로 이어가요.",
            f"기록이 {days}일뿐이라 목표는 지금 그대로 가요.",
        ])
    return rng.choice([
        f"아직 기록이 {days}일, 밤 {nights}개 모였어요, 7개씩 모이면 나만의 목표를 계산해 드릴게요.",
        f"기록이 {days}일치 모였어요, 7일이 채워질 때까지는 처음 정한 목표로 가요.",
        f"지금까지 {days}일, 밤 {nights}개가 모였어요, 조금만 더 모이면 맞춤 목표를 알려 드릴게요.",
        f"{days}일치 기록이 모였어요, 7개씩 채워지면 딱 맞는 목표를 찾아 드릴게요.",
    ])


# ── 샘플러 ─────────────────────────────────────────────────────────────────

def minutes(rng: random.Random, extreme: bool) -> int:
    """주간 값은 수천 분도 나온다. v1 은 420분까지만 학습해 1848 → 184 로 잘라 옮겼다."""
    if extreme:
        return rng.choice([1, 2, rng.randint(1000, 9999)])
    r = rng.random()
    return rng.randint(1, 9) if r < 0.1 else rng.randint(10, 420) if r < 0.7 else rng.randint(421, 5000)


def sample(rng: random.Random, extreme: bool = False) -> tuple[str, str]:
    kind = rng.choice(["decreased", "other", "night", "missions", "insufficient"])
    if kind == "decreased":
        dropped = minutes(rng, extreme)
        mean = rng.randint(1, 600) if rng.random() < 0.7 else None
        pct = rng.uniform(0.1, 95) if rng.random() < 0.85 else None
        return fact_decreased(dropped, mean, pct), target_decreased(rng, dropped, mean, pct)
    if kind == "other":
        other = minutes(rng, extreme)
        return fact_other(other), target_other(rng, other)
    if kind == "night":
        mins = minutes(rng, extreme)
        share = rng.uniform(1, 100) if rng.random() < 0.9 else None
        purpose = rng.choice(PURPOSES) if rng.random() < 0.3 else None
        return fact_night(mins, share, purpose), target_night(rng, mins, share, purpose)
    if kind == "missions":
        de, ne = rng.randint(0, 7), rng.randint(0, 7)
        if de == ne == 0:
            de = rng.randint(1, 7)
        # 전부 성공·전부 0 조합이 드물어서 일부러 섞는다. v3 첫 학습에서 각 25% 로 올렸더니 묶는 틀을
        # 맞지 않는 경우에까지 썼다 — v2 비율로 되돌린다
        r = rng.random()
        ds = de if r < 0.2 else 0 if r < 0.35 else rng.randint(0, de)
        ns = ne if r < 0.2 else 0 if r < 0.35 else rng.randint(0, ne)
        return fact_missions(ds, de, ns, ne), target_missions(rng, ds, de, ns, ne)
    days, nights, active = rng.randint(0, 6), rng.randint(0, 6), rng.random() < 0.5
    return fact_insufficient(days, nights, active), target_insufficient(rng, days, nights, active)


def scenario(rng: random.Random) -> list[tuple[str, str | None]]:
    """세트 A 용 한 주 분량. bench.scenario(v2·v3 평가 세트)와 난수를 같은 순서로 뽑아 같은 수치를 만들고,
    사실만 수치 줄로 적는다 — 학습 입력 형식이 바뀐 것 말고는 v2·v3 결과와 같은 조건으로 잴 수 있다.
    (사실, 앱 이름 또는 None)"""
    apps = ["인스타그램", "유튜브", "틱톡"]  # bench.APPS
    facts: list[tuple[str, str | None]] = []
    rng.randrange(3)  # bench.scenario 의 lead — 난수 순서를 맞추려고 뽑기만 한다
    if rng.random() < 0.25:
        days, nights = rng.randint(0, 6), rng.randint(0, 6)
        facts.append((fact_insufficient(days, nights, rng.random() < 0.5), None))
    else:
        if rng.random() < 0.7:
            dropped, mean = rng.randint(5, 400), rng.randint(20, 240)
            pct = dropped / (mean * 7 + dropped) * 100
            facts.append((fact_decreased(dropped, mean, pct), None))
            if rng.random() < 0.4:
                facts.append((fact_other(rng.randint(5, 300)), None))
        if rng.random() < 0.9:
            app, mins, share = rng.choice(apps), rng.randint(3, 300), rng.uniform(20, 100)
            purpose = rng.choice(PURPOSES) if rng.random() < 0.3 else None
            facts.append((fact_night(mins, share, purpose), app))
    if rng.random() < 0.8:
        de, ne = rng.randint(0, 7), rng.randint(0, 7)
        ds, ns = rng.randint(0, de), rng.randint(0, ne)
        if de or ne:
            facts.append((fact_missions(ds, de, ns, ne), None))
    return facts or [(fact_insufficient(0, 0, False), None)]


def user_text(fact: str) -> str:
    return f"수치:\n{fact}"


def marker_errors(fact: str, out: str) -> list[str]:
    """`{앱}` 이 사실에 있으면 정답에 정확히 한 번. 없으면 한 번도 없어야 한다. 그 밖의 중괄호는 오류."""
    want = 1 if APP in fact else 0
    got = len(MARKER.findall(out))
    errs = [] if got == want else [f"앱 표시 {got}회(기대 {want})"]
    if re.sub(MARKER, "", out).count("{") or re.sub(MARKER, "", out).count("}"):
        errs.append("잘못된 자리표시")
    return errs


def to_chat(fact: str, target: str) -> dict:
    return {"messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_text(fact)},
        {"role": "assistant", "content": target},
    ]}


def main() -> None:
    import bench  # 정답도 같은 검사를 통과해야 한다

    rng = random.Random(4001)  # v4
    out = HERE / "data"
    out.mkdir(exist_ok=True)
    for name, n, extreme in (("train", 3000, False), ("valid", 150, False), ("test_b", 200, True)):
        rows = []
        while len(rows) < n:
            fact, target = sample(rng, extreme=extreme and rng.random() < 0.5)
            bad = ([k for k, v in bench.check([fact], target).items() if v] + bench.meaning_errors([fact], target)
                   + marker_errors(fact, target))
            if bad:
                raise SystemExit(f"정답이 검사를 통과하지 못했습니다: {bad}\n  사실: {fact}\n  정답: {target}")
            rows.append(to_chat(fact, target))
        with open(out / f"{name}.jsonl", "w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(name, len(rows))


if __name__ == "__main__":
    assert fill("밤에는 {앱:을} 썼어요, {앱:이었}어요.", "유튜브") == "밤에는 유튜브를 썼어요, 유튜브였어요."
    assert fill("{앱:이} 가장 길었어요", "인스타그램") == "인스타그램이 가장 길었어요"
    assert fill("{앱:을}", "아프리카TV") == "아프리카TV를" and fill("{앱:을}", "치지직") == "치지직을"
    assert marker_errors("앱은 {앱}이고", "{앱:을} 썼어요") == [] and marker_errors("앱은 {앱}이고", "{앱:이} {앱:이었}어요")
    main()
