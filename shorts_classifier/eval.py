"""TFLite 모델을 평가하고 판정 임계값을 고른다.

오탐(엉뚱한 화면에서 캐릭터가 튀어나오는 것)이 미탐보다 치명적이므로
정확도보다 정밀도를 우선해 임계값을 잡는다.

**연속 판정으로 평가한다.** 앱은 한 장으로 판정하지 않고 세션마다 최근 N장 점수의 평균으로
판정한다. 미래 프레임은 쓰지 않고, N장이 모이기 전에는 숏폼으로 판정하지 않는다.
프레임 순서는 파일명 `{기기}_{앱}_{세션}_{번호}` 의 번호로 정한다 (1fps 추출 기준 1장 = 1초).

    python eval.py                 # val, 최근 5장
    python eval.py --window 1      # 한 장씩 판정
    python eval.py --split test    # 잠근 test 세션. 임계값·N 을 정한 뒤 한 번만 본다
"""

import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np
import tensorflow as tf

from prepare import session_of

ROOT = Path(__file__).resolve().parent.parent
BUILD = Path(__file__).resolve().parent / "build"
SPLIT = ROOT / "datasets" / "split"
IMG_SIZE = (224, 224)
CLASS_NAMES = ("not_shorts", "shorts")


def predict_all(model_path: Path, split_dir: Path) -> tuple[np.ndarray, np.ndarray, list[str]]:
    interpreter = tf.lite.Interpreter(model_path=str(model_path))
    interpreter.allocate_tensors()
    inp = interpreter.get_input_details()[0]
    outp = interpreter.get_output_details()[0]

    ds = tf.keras.utils.image_dataset_from_directory(
        split_dir, image_size=IMG_SIZE, batch_size=1, label_mode="binary", shuffle=False, class_names=CLASS_NAMES
    )

    scores, labels = [], []
    for image, label in ds:
        interpreter.set_tensor(inp["index"], tf.cast(image, inp["dtype"]).numpy())
        interpreter.invoke()
        raw = interpreter.get_tensor(outp["index"])[0][0]
        if outp["dtype"] in (np.int8, np.uint8):  # 양자화 출력은 역스케일이 필요하다
            scale, zero_point = outp["quantization"]
            raw = (float(raw) - zero_point) * scale
        scores.append(float(raw))
        labels.append(int(label.numpy()[0][0]))

    return np.array(scores), np.array(labels), [Path(p).name for p in ds.file_paths]


def sessions(names: list[str]) -> list[list[int]]:
    """세션별 인덱스 목록. 각 목록은 프레임 순서대로 정렬돼 있다."""
    groups = defaultdict(list)
    for i, name in enumerate(names):
        groups[session_of(Path(name))].append(i)
    return [sorted(idx, key=lambda i: names[i]) for idx in groups.values()]


def smooth(scores: np.ndarray, names: list[str], window: int) -> np.ndarray:
    """세션마다 최근 window 장의 평균. window 장이 모이기 전 프레임은 0 (앱도 그때는 판정하지 않는다)."""
    out = np.zeros_like(scores)
    for idx in sessions(names):
        for k in range(window - 1, len(idx)):
            out[idx[k]] = scores[idx[k - window + 1 : k + 1]].mean()
    return out


def longest_false_run(pred: np.ndarray, labels: np.ndarray, names: list[str]) -> int:
    """숏폼이 아닌데 숏폼으로 판정한 프레임이 가장 길게 이어진 장수 (= 오탐이 떠 있는 초)."""
    best = 0
    for idx in sessions(names):
        run = 0
        for i in idx:
            run = run + 1 if pred[i] and labels[i] == 0 else 0
            best = max(best, run)
    return best


def metrics_at(scores: np.ndarray, labels: np.ndarray, threshold: float) -> dict:
    pred = scores >= threshold
    tp = int(np.sum(pred & (labels == 1)))
    fp = int(np.sum(pred & (labels == 0)))
    fn = int(np.sum(~pred & (labels == 1)))
    tn = int(np.sum(~pred & (labels == 0)))
    return {
        "threshold": threshold,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": (tp + tn) / len(labels),
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        # 정밀도는 숏폼 시청 비율에 따라 달라진다. 숏폼 아닌 화면에서 얼마나 자주 틀리는지는 이걸로 본다.
        "fpr": fp / (fp + tn) if fp + tn else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=BUILD / "shorts_classifier.tflite")
    parser.add_argument("--split", choices=("val", "test"), default="val")
    parser.add_argument("--window", type=int, default=5, help="최근 몇 장의 평균으로 판정할지")
    args = parser.parse_args()

    if not args.model.exists():
        raise SystemExit(f"{args.model} 가 없습니다. 먼저 export_tflite.py 를 실행하세요.")
    if not (SPLIT / args.split).exists():
        raise SystemExit(f"{SPLIT / args.split} 가 없습니다. prepare.py 를 확인하세요.")

    raw, labels, names = predict_all(args.model, SPLIT / args.split)
    scores = smooth(raw, names, args.window)
    n_sessions = len(sessions(names))
    print(f"{args.split} {len(labels)}장, 세션 {n_sessions}개 (숏폼 {int(labels.sum())} / 아님 {int((labels == 0).sum())})")
    print(f"판정: 최근 {args.window}장 평균\n")
    if n_sessions < 5:
        print("[주의] 세션이 적어 수치가 크게 흔들린다. 장수가 아니라 세션 수가 표본 크기다.\n")

    print(f"{'임계값':>8}{'정밀도':>10}{'재현율':>10}{'오탐률':>10}{'오탐':>8}{'미탐':>8}{'최장오탐':>10}")
    rows = [metrics_at(scores, labels, t) for t in np.arange(0.3, 0.95, 0.05)]
    for r in rows:
        r["run"] = longest_false_run(scores >= r["threshold"], labels, names)
        print(
            f"{r['threshold']:>8.2f}{r['precision']:>10.1%}{r['recall']:>10.1%}{r['fpr']:>10.1%}"
            f"{r['fp']:>8}{r['fn']:>8}{r['run']:>9}장"
        )

    # 정밀도 90% 이상을 만족하는 것들 중 재현율이 가장 높은 임계값
    safe = [r for r in rows if r["precision"] >= 0.90]
    print("\n" + "=" * 64)
    if safe:
        best = max(safe, key=lambda r: r["recall"])
        print(
            f"권장 임계값 {best['threshold']:.2f} (최근 {args.window}장 평균) — "
            f"정밀도 {best['precision']:.1%}, 재현율 {best['recall']:.1%}, 오탐률 {best['fpr']:.1%}, 최장 오탐 {best['run']}장"
        )
        print(f"앱에는 임계값과 창 크기({args.window})를 함께 넣으세요. 모델을 바꾸면 둘 다 다시 고릅니다.")
        if best["recall"] < 0.80:
            print("\n[주의] 재현율이 80% 미만입니다. 숏폼을 자주 놓칩니다. 데이터를 더 모으세요.")
    else:
        print("[실패] 정밀도 90%를 넘는 임계값이 없습니다.")
        print("이대로 출시하면 엉뚱한 화면에서 캐릭터가 튀어나옵니다.")
        print("→ 데이터를 더 모으거나, 앱 단위 감지(A안)로 후퇴하세요.")
    if args.split == "val":
        print("\n이 수치는 모델·임계값을 고른 데이터에서 나온 것이라 낙관적이다. 최종 판정은 --split test 로 한 번만.")


if __name__ == "__main__":
    main()
