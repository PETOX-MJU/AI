"""FE 포팅(slmCheck.ts) 대조용 JSON. Python 검사·fill 이 정본이고, TS 가 같은 판정을 내는지 jest 가 확인한다.

    python export_cases.py     # results/slmCases.json → FE __tests__/fixtures/slmCases.json 으로 복사
"""

import json
import random
import re
import sys
from pathlib import Path

import bench
import data
from data import fill, marker_errors

HERE = Path(__file__).resolve().parent
# v3 출력 + v3b 출력(두 미션을 묶는 틀 때문에 "전부 성공"을 잘못 쓴 실제 사례가 있다)
# 인자로 results/ 파일 이름을 주면 그것만 쓴다. 기본은 v4 온도 0.5·0 출력 —
# 예전 버전(v3b 등) 출력은 사실이 분석기 문장 형식이라 v4 입력과 맞지 않는다. 학습 정답(gold)은 항상 더한다
SOURCES = sys.argv[1:] or ["ft-v4-q4_t0.5_A.json", "ft-v4-q4_t0.5_B.json", "ft-v4-q4_A.json"]
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
        re.sub(r"\{앱(:[^}]*)?\}", "{앱:를}", out, count=1),
        out + " {앱}도요.",
        out + " 다음 주도 화이팅.",
        out.replace("요", "요 수면", 1),
        out.replace("요", "요 모두 달성", 1),
        out.replace("해냈어요", "하나도 못 채웠어요", 1),  # 미션 판정 뒤집기
        out.replace("아쉬웠어요", "모두 해냈어요", 1),
        out * 3,
        out + " ok",
        "",
    ]
    if first:
        muts.append(out[:first.start()] + str(int(first.group()) + 1) + out[first.end():])
    return [m for m in muts if m != out]


def fact_cases() -> list[dict]:
    """FE toFact 대조: 분석기 evidence(ms)·문장 → 수치 줄. 기대값은 data.fact_* (학습 입력과 같은 모양).
    ms 는 반올림하면 분이 되게 ±29초를 섞는다 — 분석기는 ms 로 계산하고 분으로 표시한다."""
    rng = random.Random(11)
    ms = lambda m: m * 60_000 + rng.randint(-29_000, 29_000)
    out = []
    for _ in range(30):
        dropped, mean, pct = rng.randint(1, 3000), rng.randint(1, 600), round(rng.uniform(0.1, 95), 3)
        has_mean, has_pct = rng.random() < 0.7, rng.random() < 0.85
        ev = {"selected_delta_ms": -ms(dropped), "selected_delta_pct": -pct if has_pct else None,
              "selected_daily_mean_ms": ms(mean) if has_mean else None}
        text = (f"지난주 선택한 앱 사용량은 하루 평균 {mean}분입니다. " if has_mean else "") + f"전주 대비 주간 합계가 {dropped}분 줄었습니다."
        text += f" 변화율은 {pct:.1f}%입니다." if has_pct else ""
        out.append({"code": "SELECTED_USAGE_DECREASED", "evidence": ev, "text": text,
                    "fact": data.fact_decreased(dropped, mean if has_mean else None, pct if has_pct else None)})
    for _ in range(10):
        other = rng.randint(1, 3000)
        out.append({"code": "OTHER_APPS_INCREASED", "evidence": {"other_apps_delta_ms": ms(other), "selected_delta_ms": -ms(9)},
                    "text": f"선택한 앱은 줄었지만 나머지 앱 사용이 {other}분 늘었습니다.", "fact": data.fact_other(other)})
    for _ in range(30):
        mins, share = rng.randint(1, 3000), round(rng.uniform(1, 100), 3)
        has_share, purpose = rng.random() < 0.9, rng.choice([*data.PURPOSES, None, "기타앱"])
        pkg = "com.google.android.youtube"
        text = f"취침 전후로 가장 오래 사용한 앱은 {pkg}이고 {mins}분입니다." + (f" 야간 사용의 {share:.1f}%입니다." if has_share else "")
        text += f" 이 앱의 사용 목적은 '{purpose}'로 설정되어 있습니다." if purpose else ""
        out.append({"code": "NIGHT_TOP_APP", "evidence": {"package_name": pkg, "night_total_ms": ms(mins), "night_share_pct": share if has_share else None},
                    "text": text,
                    # 학습에 없는 목적 값은 줄에서 뺀다
                    "fact": data.fact_night(mins, share if has_share else None, purpose if purpose in data.PURPOSES else None)})
    for _ in range(20):
        de, ne = rng.randint(0, 7), rng.randint(0, 7)
        ds, ns = rng.randint(0, de), rng.randint(0, ne)
        text = f"이번 주 일일 미션은 {data.mission_phrase(ds, de)}, 야간 미션은 {data.mission_phrase(ns, ne)}입니다."
        out.append({"code": "DAILY_NIGHT_DIFFERENCE",
                    "evidence": {"daily_success_count": ds, "daily_evaluable_count": de, "night_success_count": ns, "night_evaluable_count": ne},
                    "text": text, "fact": data.fact_missions(ds, de, ns, ne)})
    for _ in range(10):
        days, nights, active = rng.randint(0, 6), rng.randint(0, 6), rng.random() < 0.5
        out.append({"code": "INSUFFICIENT_DATA",
                    "evidence": {"valid_days": days, "valid_nights": nights, "has_active_target": int(active)},
                    "text": f"분석에 사용할 수 있는 날은 {days}일, 야간 구간은 {nights}개입니다. 7개가 모이지 않아 …",
                    "fact": data.fact_insufficient(days, nights, active)})
    # 못 만드는 경우: 늘어난 주, 모르는 코드, 문장과 숫자가 어긋남(반올림 차이)
    out += [
        {"code": "SELECTED_USAGE_DECREASED", "evidence": {"selected_delta_ms": 600_000, "selected_delta_pct": 5.0, "selected_daily_mean_ms": None},
         "text": "주간 합계가 10분 줄었습니다.", "fact": None},
        {"code": "SOMETHING_NEW", "evidence": {}, "text": "새 문장 12분", "fact": None},
        {"code": "SELECTED_USAGE_DECREASED", "evidence": {"selected_delta_ms": -5_700_000, "selected_delta_pct": None, "selected_daily_mean_ms": None},
         "text": "전주 대비 주간 합계가 94분 줄었습니다.", "fact": None},
        {"code": "DAILY_NIGHT_DIFFERENCE", "evidence": {"daily_success_count": 1}, "text": "일일 1개", "fact": None},
    ]
    return out


def main() -> None:
    rows = [r for name in SOURCES for r in json.loads((HERE / "results" / name).read_text())]
    # 학습 정답은 검사를 통과한 문장이라 통과 사례를 넉넉하게 해 준다 (python data.py 가 만든 valid·test_b)
    for name in ("valid", "test_b"):
        for line in open(HERE / "data" / f"{name}.jsonl", encoding="utf-8"):
            m = json.loads(line)["messages"]
            rows.append({"fact": m[1]["content"].removeprefix("수치:\n"), "out": m[2]["content"], "fail": []})
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
    path.write_text(json.dumps({"checks": checks, "fills": fills, "facts": fact_cases()}, ensure_ascii=False, indent=1))
    bad = sum(bool(c["fail"]) for c in checks)
    print(f"{path}: 검사 {len(checks)}개(실패 {bad}), fill {len(fills)}개")
    assert bad > 50 and len(checks) - bad > 100 and len(fills) > 100, "통과·실패 사례가 둘 다 충분해야 대조가 의미 있다"


if __name__ == "__main__":
    main()
