"""python test_prepare.py — 분할이 녹화를 쪼개지 않고, (앱, 주된 라벨) 묶음별로 나뉘는지 확인한다."""

import random
from pathlib import Path

from prepare import session_of, split_sessions


def frames(session, label, start, n):
    return [(label, Path(f"{session}_{i:04d}.jpg")) for i in range(start, start + n)]


def test_split_sessions():
    items = (
        frames("a_yt_s01", "shorts", 0, 40) + frames("a_yt_s02", "shorts", 0, 40) + frames("b_yt_s03", "shorts", 0, 40)
        + frames("a_yt_s04", "not_shorts", 0, 40) + frames("a_yt_s05", "not_shorts", 0, 40)
        # 피드를 넘기다 릴스가 뜬 녹화: 두 라벨이 섞여 있다
        + frames("a_ig_s06", "not_shorts", 0, 20) + frames("a_ig_s06", "shorts", 20, 10)
        + frames("a_ig_s07", "not_shorts", 0, 30)
        + frames("a_ig_s08", "shorts", 0, 30)
    )
    for seed in range(20):
        b = split_sessions(items, 0.2, random.Random(seed))
        train = {session_of(p) for _, p in b["train"]}
        val = {session_of(p) for _, p in b["val"]}
        assert not train & val, "녹화가 train 과 val 양쪽에 있다 (라벨이 섞인 a_ig_s06 포함)"
        assert len(b["train"]) + len(b["val"]) == len(items)
        assert len(val & {"a_yt_s01", "a_yt_s02", "b_yt_s03"}) == 1, "유튜브 숏폼 120장의 20% → 세션 하나"
        assert len(val & {"a_yt_s04", "a_yt_s05"}) == 1
        assert len(val & {"a_ig_s06", "a_ig_s07"}) == 1, "a_ig_s06 은 주된 라벨(아님) 묶음으로 간다"
        assert "a_ig_s08" in train, "녹화가 하나뿐인 묶음은 전부 train"
        assert {lab for lab, p in b["train"] if "_yt_" in p.name} == {"shorts", "not_shorts"}


if __name__ == "__main__":
    test_split_sessions()
    print("OK")
