"""TFLite 모델을 검증셋으로 평가하고 판정 임계값을 고른다.

오탐(카톡 중에 캐릭터가 튀어나오는 것)이 미탐보다 치명적이므로
정확도보다 정밀도를 우선해 임계값을 잡는다.

    python eval.py
"""

import argparse
from pathlib import Path

import numpy as np
import tensorflow as tf

ROOT = Path(__file__).resolve().parent.parent
BUILD = Path(__file__).resolve().parent / "build"
VAL_DIR = ROOT / "datasets" / "split" / "val"
IMG_SIZE = (224, 224)
CLASS_NAMES = ("not_shorts", "shorts")


def predict_all(model_path: Path) -> tuple[np.ndarray, np.ndarray]:
    interpreter = tf.lite.Interpreter(model_path=str(model_path))
    interpreter.allocate_tensors()
    inp = interpreter.get_input_details()[0]
    outp = interpreter.get_output_details()[0]

    ds = tf.keras.utils.image_dataset_from_directory(
        VAL_DIR, image_size=IMG_SIZE, batch_size=1, label_mode="binary", shuffle=False, class_names=CLASS_NAMES
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

    return np.array(scores), np.array(labels)


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
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=BUILD / "shorts_classifier.tflite")
    args = parser.parse_args()

    if not args.model.exists():
        raise SystemExit(f"{args.model} 가 없습니다. 먼저 export_tflite.py 를 실행하세요.")

    scores, labels = predict_all(args.model)
    print(f"검증 샘플 {len(labels)}장 (숏폼 {int(labels.sum())} / 아님 {int((labels == 0).sum())})\n")

    print(f"{'임계값':>8}{'정확도':>10}{'정밀도':>10}{'재현율':>10}{'오탐':>8}{'미탐':>8}")
    rows = [metrics_at(scores, labels, t) for t in np.arange(0.3, 0.95, 0.05)]
    for r in rows:
        print(f"{r['threshold']:>8.2f}{r['accuracy']:>10.1%}{r['precision']:>10.1%}{r['recall']:>10.1%}{r['fp']:>8}{r['fn']:>8}")

    # 정밀도 90% 이상을 만족하는 것들 중 재현율이 가장 높은 임계값
    safe = [r for r in rows if r["precision"] >= 0.90]
    print("\n" + "=" * 56)
    if safe:
        best = max(safe, key=lambda r: r["recall"])
        print(f"권장 임계값 {best['threshold']:.2f} — 정밀도 {best['precision']:.1%}, 재현율 {best['recall']:.1%}")
        print(f"앱에 이 값을 상수로 넣으세요.")
        if best["recall"] < 0.80:
            print("\n[주의] 재현율이 80% 미만입니다. 숏폼을 자주 놓칩니다. 데이터를 더 모으세요.")
    else:
        print("[실패] 정밀도 90%를 넘는 임계값이 없습니다.")
        print("이대로 출시하면 엉뚱한 화면에서 캐릭터가 튀어나옵니다.")
        print("→ 데이터를 더 모으거나, 앱 단위 감지(A안)로 후퇴하세요.")


if __name__ == "__main__":
    main()
