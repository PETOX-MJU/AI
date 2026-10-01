"""FE 포팅(slmCheck.ts) 대조용 JSON. Python 검사·fill 이 정본이고, TS 가 같은 판정을 내는지 jest 가 확인한다.

    python export_cases.py     # results/slmCases.json → FE __tests__/fixtures/slmCases.json 으로 복사
"""

import json
import re
from pathlib import Path

import bench
import random

from data import fill, marker_errors, sample

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
        re.sub(r"\{앱(:[^}]*)?\}", "{앱:를}", out, count=1),
        out + " {앱}도요.",
        out + " 다음 주도 화이팅.",
        out.replace("요", "요 수면", 1),
        out.replace("요", "요 모두 달성", 1),
        out * 3,
        out + " ok",
        "",
    ]
    if first:
        muts.append(out[:first.start()] + str(int(first.group()) + 1) + out[first.end():])
    return [m for m in muts if m != out]


def load_rows() -> list[dict]:
    """eval 결과(results/*.json, 커밋 안 함)가 있으면 모델 출력 그대로, 없으면 학습 정답 문장(data.sample)으로 대신한다."""
    found = [HERE / "results" / n for n in SOURCES if (HERE / "results" / n).exists()]
    if found:
        return [r for path in found for r in json.loads(path.read_text())]
    rng = random.Random(11)
    rows = []
    for i in range(300):
        fact, target = sample(rng, extreme=i % 3 == 0)
        rows.append({"fact": fact, "out": target, "fail": fail(fact, target)})
    return rows


def main() -> None:
    rows = load_rows()
    checks, seen = [], set()
    for r in rows:
        outs = [r["out"]] + (mutations(r["out"]) if not r["fail"] and len(seen) < 400 else [])
        for out in outs:
            if (r["fact"], out) not in seen:
                seen.add((r["fact"], out))
                checks.append({"fact": r["fact"], "out": out, "fail": fail(r["fact"], out)})
    fills = [{"out": r["out"], "app": app, "shown": fill(r["out"], app)}
             for r in rows[:200] for app in APPS if "{앱" in r["out"]]
    path = HERE / "results" / "slmCases.json"
    path.write_text(json.dumps({"checks": checks, "fills": fills}, ensure_ascii=False, indent=1))
    bad = sum(bool(c["fail"]) for c in checks)
    print(f"{path}: 검사 {len(checks)}개(실패 {bad}), fill {len(fills)}개")
    assert bad > 50 and len(checks) - bad > 100 and len(fills) > 100, "통과·실패 사례가 둘 다 충분해야 대조가 의미 있다"


if __name__ == "__main__":
    main()
