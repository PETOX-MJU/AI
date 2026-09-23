"""python test_eval.py — 연속 판정이 세션을 넘지 않고, 과거 프레임만 쓰는지 확인한다."""

import numpy as np

from eval import MIN_PRECISION, best_threshold, longest_false_run, metrics_at, smooth, threshold_text


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


def test_threshold_text_keeps_precision():
    # 리뷰 재현 사례: 0.45049 에서는 정밀도 100% 지만 0.450 으로 반올림하면 사이의 오탐 1장이 들어와 90%
    scores = np.array([0.45049 + 0.001 * i for i in range(9)] + [0.4502] + [0.1] * 10)
    labels = np.array([1] * 9 + [0] + [0] * 10)
    best = best_threshold(scores, labels)
    assert np.isclose(best["threshold"], 0.45049) and best["precision"] == 1.0
    assert metrics_at(scores, labels, round(best["threshold"], 3))["precision"] < MIN_PRECISION  # 반올림하면 깨진다
    text = threshold_text(best["threshold"])
    assert float(text) == best["threshold"]
    assert metrics_at(scores, labels, float(text)) == best


if __name__ == "__main__":
    test_smooth_and_false_run()
    test_best_threshold_between_grid()
    test_threshold_text_keeps_precision()
    print("OK")
