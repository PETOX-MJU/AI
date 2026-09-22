"""python test_eval.py — 연속 판정이 세션을 넘지 않고, 과거 프레임만 쓰는지 확인한다."""

import numpy as np

from eval import best_threshold, longest_false_run, smooth


def test_smooth_and_false_run():
    # 두 세션이 섞인 순서로 들어온다
    names = ["a_yt_s01_0002.jpg", "b_yt_s02_0001.jpg", "a_yt_s01_0001.jpg", "a_yt_s01_0003.jpg", "b_yt_s02_0002.jpg"]
    scores = np.array([0.2, 0.9, 1.0, 0.6, 0.7])

    out = smooth(scores, names, 2)
    # s01 순서: 0001(1.0) 0002(0.2) 0003(0.6) → 첫 장은 판정 안 함, 이후 최근 2장 평균
    assert out[2] == 0.0
    assert np.isclose(out[0], 0.6) and np.isclose(out[3], 0.4)
    # s02 순서: 0001(0.9) 0002(0.7) → 다른 세션 점수가 섞이지 않는다
    assert out[1] == 0.0 and np.isclose(out[4], 0.8)
    assert np.array_equal(smooth(scores, names, 1), scores)

    labels = np.array([0, 0, 0, 0, 1])
    pred = np.array([True, True, True, False, True])
    # s01: 0001 T, 0002 T, 0003 F → 2장 / s02: 0001 T(아님), 0002 T(숏폼) → 1장
    assert longest_false_run(pred, labels, names) == 2


def test_best_threshold_between_grid():
    # 정밀도 95% 는 0.93 이상에서만 나온다 (0.90 격자로는 오탐이 섞인다)
    scores = np.array([0.91] + [0.93 + 0.001 * i for i in range(19)] + [0.1] * 20)
    labels = np.array([0] + [1] * 19 + [0] * 20)
    best = best_threshold(scores, labels)
    assert np.isclose(best["threshold"], 0.93) and best["fp"] == 0 and best["recall"] == 1.0
    assert best_threshold(np.array([0.9, 0.9]), np.array([0, 1])) is None


if __name__ == "__main__":
    test_smooth_and_false_run()
    test_best_threshold_between_grid()
    print("OK")
