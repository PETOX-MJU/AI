"""학습된 Keras 모델을 안드로이드용 TFLite로 변환한다.

    python export_tflite.py                # float16 (기본, 약 2MB, float32 와 점수 차 0.01 미만)
    python export_tflite.py --quant none   # float32
    python export_tflite.py --quant int8   # 실험용 — 아래 참고

int8 을 기본으로 쓰지 않는 이유: 실제 데이터로 보정한 MobileNetV3 int8 모델이
TFLite 기본 CPU 가속기(XNNPACK)에서 allocate 에 실패했고, 가속기를 꺼도 점수가 최대 0.24 틀어졌다.
"""

import argparse
from pathlib import Path

import numpy as np
import tensorflow as tf

ROOT = Path(__file__).resolve().parent.parent
BUILD = Path(__file__).resolve().parent / "build"
CALIB_DIR = ROOT / "datasets" / "split" / "train"
IMG_SIZE = (224, 224)


def representative_dataset(limit: int = 100):
    """양자화 보정용 실제 입력 샘플. 없으면 정확도가 크게 떨어진다."""
    ds = tf.keras.utils.image_dataset_from_directory(
        CALIB_DIR, image_size=IMG_SIZE, batch_size=1, label_mode=None, shuffle=True
    )
    for i, batch in enumerate(ds):
        if i >= limit:
            break
        yield [tf.cast(batch, tf.float32)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=BUILD / "best.keras")
    parser.add_argument("--quant", choices=("f16", "none", "int8"), default="f16")
    args = parser.parse_args()

    if not args.model.exists():
        raise SystemExit(f"{args.model} 가 없습니다. 먼저 train.py 를 실행하세요.")

    model = tf.keras.models.load_model(args.model)
    converter = tf.lite.TFLiteConverter.from_keras_model(model)

    if args.quant != "none":
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
    if args.quant == "f16":
        converter.target_spec.supported_types = [tf.float16]
    elif args.quant == "int8":
        converter.representative_dataset = representative_dataset

    tflite_model = converter.convert()
    out = BUILD / "shorts_classifier.tflite"
    out.write_bytes(tflite_model)

    size_mb = len(tflite_model) / 1024 / 1024
    print(f"변환 완료: {out} ({size_mb:.2f} MB)")

    # 기본 가속기(XNNPACK)로 로드되는지 확인한다. 여기서 실패하면 앱에서도 실패한다.
    interpreter = tf.lite.Interpreter(model_content=tflite_model)
    interpreter.allocate_tensors()
    inp = interpreter.get_input_details()[0]
    outp = interpreter.get_output_details()[0]
    print(f"입력  {inp['shape']} {inp['dtype'].__name__}")
    print(f"출력  {outp['shape']} {outp['dtype'].__name__}  (0에 가까울수록 숏폼 아님, 1에 가까울수록 숏폼)")

    if size_mb > 10:
        print("\n[경고] 10MB 초과 — APK가 무거워집니다. 양자화 옵션을 확인하세요.")

    print("\nFE 전달: gh release create v0.1.0 " + str(out))


if __name__ == "__main__":
    main()
