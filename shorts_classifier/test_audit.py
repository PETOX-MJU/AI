"""python test_audit.py — 교차 채점 학습이 실패하면 원인을 보여 주고 멈추는지 확인한다. TensorFlow 없이 돈다."""

import sys

from audit_labels import run_train


def test_run_train_shows_failure_output():
    run_train([sys.executable, "-c", "print('학습 끝')"], "성공하는 학습")  # 성공하면 조용히 지나간다
    try:
        run_train([sys.executable, "-c", "print('epoch 1'); import no_such_module"], "[1/4] train.py")
    except SystemExit as e:
        message = str(e.code)
        assert "[1/4] train.py 실패 (종료 코드 1)" in message
        assert "epoch 1" in message and "No module named 'no_such_module'" in message  # 표준 출력·오류 모두
    else:
        raise AssertionError("학습 실패가 삼켜졌다")


if __name__ == "__main__":
    test_run_train_shows_failure_output()
    print("OK")
