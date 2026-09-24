"""파인튜닝 데이터. 사실 문장은 분석기 템플릿(Narratives.kt)과 같은 문구, 정답은 펫 말투 틀에 숫자를 코드로 넣는다.

v2: 앱 이름은 모델에 넣지 않는다. 사실에는 `{앱}`, 정답에는 조사까지 표시한 `{앱:을}` 같은 자리표시를 쓰고
생성 뒤 [fill] 이 실제 이름과 받침에 맞는 조사로 바꾼다. 처음 보는 앱 이름(치지직 → 치지icks)이 깨지던 문제를 없앤다.

    python data.py        # data/train.jsonl, valid.jsonl, test_b.jsonl
"""

import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSTEM = "주간 스크린타임 사실 하나를 펫 캐릭터의 다정한 존댓말 한 문장으로 바꿔라. 숫자와 {앱} 표시는 그대로 옮기고 사실에 없는 말은 하지 마라."
APP = "{앱}"
PURPOSES = ["학습", "업무", "여가", "연락", "기타"]

# 자리표시 → (받침 있을 때, 없을 때)
JOSA = {"을": ("을", "를"), "이": ("이", "가"), "은": ("은", "는"), "과": ("과", "와"), "이었": ("이었", "였"), "이에": ("이에", "예")}
MARKER = re.compile(r"\{앱(?::(" + "|".join(JOSA) + r"))?\}")


def has_batchim(word: str) -> bool:
    ch = word.strip()[-1]
    if "가" <= ch <= "힣":
        return (ord(ch) - 0xAC00) % 28 != 0
    # 영문·숫자로 끝나면 읽는 소리 기준: TV(티비), X(엑스) 처럼 모음으로 끝나는 게 대부분이다
    return ch.lower() in "lmnr0136789"


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


# ── 사실 문장 (분석기와 같은 문구) ──────────────────────────────────────────

def fact_decreased(lead: int, dropped: int, mean: int | None, pct: float | None) -> str:
    text = f"지난주 선택한 앱 사용량은 하루 평균 {mean}분입니다. " if mean is not None else ""
    text += ["그 전주보다", "전주 대비", "지난주와 견주면"][lead] + f" 주간 합계가 {dropped}분 줄었습니다."
    if pct is not None:
        text += f" 변화율은 {pct:.1f}%입니다."
    return text


def fact_other(lead: int, other: int) -> str:
    return (["선택한 앱은 줄었지만", "선택한 앱 사용은 감소했고", "선택한 앱 사용량은 줄었지만"][lead]
            + f" 나머지 앱 사용이 {other}분 늘었습니다. 다른 앱 사용이 늘었다는 사실만 확인된 것이며 이유는 기록으로 알 수 없습니다.")


def fact_night(lead: int, mins: int, share: float | None, purpose: str | None) -> str:
    text = ["야간 구간에서 가장 많이 사용한 앱은", "취침 전후로 가장 오래 사용한 앱은", "밤 시간대 사용이 가장 많았던 앱은"][lead]
    text += f" {APP}이고 {mins}분입니다."
    if share is not None:
        text += f" 야간 사용의 {share:.1f}%입니다."
    if purpose:
        text += f" 이 앱의 사용 목적은 '{purpose}'로 설정되어 있습니다."
    return text


def mission_phrase(s: int, e: int) -> str:
    return "판정 가능한 미션 없음" if e == 0 else f"{e}개 중 {s}개 달성"


def fact_missions(lead: int, ds: int, de: int, ns: int, ne: int) -> str:
    tpl = ["이번 주 일일 미션은 {d}, 야간 미션은 {n}입니다.", "이번 주 판정 결과는 일일 {d}, 야간 {n}입니다.", "이번 주 성적은 일일 {d}, 야간 {n}입니다."][lead]
    return tpl.format(d=mission_phrase(ds, de), n=mission_phrase(ns, ne))


def fact_insufficient(lead: int, days: int, nights: int, active: bool) -> str:
    head = ["분석에 사용할 수 있는 날은", "이번 주 확인된 날은", "복원에 성공한 날은"][lead]
    tail = ("7개가 모이지 않아 이번 주 성과로는 다음 목표를 계산하지 않습니다. 현재 목표는 그대로 유지됩니다." if active
            else "각각 7개가 모여야 개인 기준선을 계산합니다. 그때까지는 처음 입력한 임시 목표를 사용합니다.")
    return f"{head} {days}일, 야간 구간은 {nights}개입니다. {tail}"


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
            f"밤 시간의 {s}를 {a('이')} 차지했어요.",
        ]
    if purpose:
        opts += [
            f"밤엔 {a('을')} {n} 썼어요, '{purpose}' 용도로 정해 둔 앱이에요.",
            f"'{purpose}'용으로 정한 {a('을')} 밤에 {n} 썼어요.",
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
    # 둘 다 전부 성공이거나 둘 다 0개면 한 절로 묶어 같은 말을 되풀이하지 않는다
    if de and ne and ds == de and ns == ne:
        return rng.choice([
            f"이번 주 일일 미션 {de}개, 야간 미션 {ne}개를 모두 해냈어요!",
            f"일일 {de}개, 야간 {ne}개 미션을 전부 성공했어요, 최고예요!",
        ])
    if de and ne and ds == 0 and ns == 0:
        return rng.choice([
            f"이번 주는 일일 {de}개, 야간 {ne}개 미션을 하나도 못 채웠지만 다음 주엔 같이 해봐요.",
            f"일일 미션 {de}개, 야간 미션 {ne}개 모두 아쉬웠어요, 다음 주에 다시 도전해요.",
        ])
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
    lead = rng.randrange(3)
    kind = rng.choice(["decreased", "other", "night", "missions", "insufficient"])
    if kind == "decreased":
        dropped = minutes(rng, extreme)
        mean = rng.randint(1, 600) if rng.random() < 0.7 else None
        pct = rng.uniform(0.1, 95) if rng.random() < 0.85 else None
        return fact_decreased(lead, dropped, mean, pct), target_decreased(rng, dropped, mean, pct)
    if kind == "other":
        other = minutes(rng, extreme)
        return fact_other(lead, other), target_other(rng, other)
    if kind == "night":
        mins = minutes(rng, extreme)
        share = rng.uniform(1, 100) if rng.random() < 0.9 else None
        purpose = rng.choice(PURPOSES) if rng.random() < 0.3 else None
        return fact_night(lead, mins, share, purpose), target_night(rng, mins, share, purpose)
    if kind == "missions":
        de, ne = rng.randint(0, 7), rng.randint(0, 7)
        if de == ne == 0:
            de = rng.randint(1, 7)
        r = rng.random()  # 전부 성공·전부 0 조합이 드물어서 일부러 섞는다
        ds = de if r < 0.2 else 0 if r < 0.35 else rng.randint(0, de)
        ns = ne if r < 0.2 else 0 if r < 0.35 else rng.randint(0, ne)
        return fact_missions(lead, ds, de, ns, ne), target_missions(rng, ds, de, ns, ne)
    days, nights, active = rng.randint(0, 6), rng.randint(0, 6), rng.random() < 0.5
    return fact_insufficient(lead, days, nights, active), target_insufficient(rng, days, nights, active)


def user_text(fact: str) -> str:
    return f"사실: {fact}"


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

    rng = random.Random(2000)
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
