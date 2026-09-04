"""반려동물 분류기를 안드로이드용 TFLite 로 변환한다.

    python export_tflite.py            # int8 양자화
    python export_tflite.py --no-quant
"""

import argparse
import csv
from pathlib import Path

import numpy as np
import tensorflow as tf

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "datasets" / "pets"
BUILD = Path(__file__).resolve().parent / "build"
IMG_SIZE = (224, 224)


def representative_dataset(limit: int = 100):
    with (DATA / "labels.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))[:limit]
    for row in rows:
        image = tf.io.decode_image(tf.io.read_file(str(DATA / row["filename"])), channels=3, expand_animations=False)
        yield [tf.expand_dims(tf.image.resize(image, IMG_SIZE), 0)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=BUILD / "best.keras")
    parser.add_argument("--no-quant", action="store_true")
    args = parser.parse_args()

    if not args.model.exists():
        raise SystemExit(f"{args.model} 가 없습니다. 먼저 train.py 를 실행하세요.")

    converter = tf.lite.TFLiteConverter.from_keras_model(tf.keras.models.load_model(args.model))
    if not args.no_quant:
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        converter.representative_dataset = representative_dataset

    tflite_model = converter.convert()
    out = BUILD / "pet_classifier.tflite"
    out.write_bytes(tflite_model)
    print(f"변환 완료: {out} ({len(tflite_model) / 1024 / 1024:.2f} MB)")

    interpreter = tf.lite.Interpreter(model_content=tflite_model)
    interpreter.allocate_tensors()
    for detail in interpreter.get_output_details():
        print(f"출력 {detail['name']}: {detail['shape']}")

    print("\nFE 전달: gh release create v0.1.0 " + str(out))


if __name__ == "__main__":
    main()
