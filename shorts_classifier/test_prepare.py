"""python test_prepare.py — 분할이 세션을 쪼개지 않고, 앱별로 나뉘는지 확인한다."""

import random
from pathlib import Path

from prepare import session_of, split_sessions


def test_split_sessions():
    def frames(session, n):
        return [Path(f"{session}_{i:04d}.jpg") for i in range(n)]

    # 유튜브 세션 3개, 인스타 세션 1개
    images = frames("a_yt_s01", 40) + frames("a_yt_s02", 40) + frames("b_yt_s03", 40) + frames("a_ig_s04", 90)
    for seed in range(20):
        b = split_sessions(images, 0.2, random.Random(seed))
        train = {session_of(p) for p in b["train"]}
        val = {session_of(p) for p in b["val"]}
        assert not train & val, "세션이 train 과 val 양쪽에 있다"
        assert len(b["train"]) + len(b["val"]) == len(images)
        assert "a_ig_s04" in train, "세션이 하나뿐인 앱은 전부 train"
        assert len(val) == 1, "유튜브 120장의 20% = 24장 → 40장 세션 하나면 충분"
        assert val <= {"a_yt_s01", "a_yt_s02", "b_yt_s03"}


if __name__ == "__main__":
    test_split_sessions()
    print("OK")
