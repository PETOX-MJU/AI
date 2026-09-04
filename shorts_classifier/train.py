"""숏폼 화면 분류기 학습 (MobileNetV3-Small 전이학습).

출력이 TFLite여야 하므로 Keras로 학습한다. PyTorch→ONNX→TFLite 경로는 실패 지점이 많다.

    python prepare.py
    python train.py --epochs 15
"""

import argparse
from pathlib import Path

import tensorflow as tf

ROOT = Path(__file__).resolve().parent.parent
SPLIT = ROOT / "datasets" / "split"
BUILD = Path(__file__).resolve().parent / "build"
IMG_SIZE = (224, 224)
# 폴더명 알파벳 순으로 인덱스가 매겨진다: not_shorts=0, shorts=1
CLASS_NAMES = ("not_shorts", "shorts")


def load_datasets(batch_size: int):
    common = dict(image_size=IMG_SIZE, batch_size=batch_size, label_mode="binary", class_names=CLASS_NAMES)
    train = tf.keras.utils.image_dataset_from_directory(SPLIT / "train", shuffle=True, **common)
    val = tf.keras.utils.image_dataset_from_directory(SPLIT / "val", shuffle=False, **common)
    return train, val


def class_weights(train_ds) -> dict[int, float]:
    """숏폼 샘플이 적을 때 한쪽으로 쏠리는 걸 막는다."""
    counts = [0, 0]
    for _, labels in train_ds.unbatch():
        counts[int(labels.numpy()[0])] += 1
    total = sum(counts)
    return {i: total / (2 * c) if c else 1.0 for i, c in enumerate(counts)}


def build_model() -> tf.keras.Model:
    base = tf.keras.applications.MobileNetV3Small(
        input_shape=(*IMG_SIZE, 3),
        include_top=False,
        weights="imagenet",
        include_preprocessing=True,  # 0-255 입력을 그대로 받는다. 앱에서 전처리를 맞출 필요가 없다.
    )
    base.trainable = False

    augment = tf.keras.Sequential(
        [
            # 좌우 반전은 넣지 않는다 — 숏폼 UI 버튼이 항상 오른쪽에 있는 게 핵심 단서다.
            tf.keras.layers.RandomBrightness(0.2),
            tf.keras.layers.RandomContrast(0.2),
            tf.keras.layers.RandomZoom(0.1),
        ],
        name="augment",
    )

    inputs = tf.keras.Input(shape=(*IMG_SIZE, 3))
    x = augment(inputs)
    x = base(x, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    outputs = tf.keras.layers.Dense(1, activation="sigmoid", name="is_shorts")(x)
    return tf.keras.Model(inputs, outputs, name="shorts_classifier")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--finetune-epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    if not SPLIT.exists():
        raise SystemExit("datasets/split 이 없습니다. 먼저 `python prepare.py` 를 실행하세요.")

    train_ds, val_ds = load_datasets(args.batch_size)
    weights = class_weights(train_ds)
    print(f"클래스 가중치: {weights}")

    train_ds = train_ds.prefetch(tf.data.AUTOTUNE)
    val_ds = val_ds.prefetch(tf.data.AUTOTUNE)

    BUILD.mkdir(exist_ok=True)
    checkpoint = BUILD / "best.keras"
    metrics = [
        tf.keras.metrics.BinaryAccuracy(name="acc"),
        tf.keras.metrics.Precision(name="precision"),
        tf.keras.metrics.Recall(name="recall"),
    ]
    callbacks = [
        # 오탐이 사용자를 쫓아내므로 정밀도를 기준으로 저장한다.
        tf.keras.callbacks.ModelCheckpoint(checkpoint, monitor="val_precision", mode="max", save_best_only=True),
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True),
    ]

    model = build_model()
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="binary_crossentropy", metrics=metrics)

    print("\n[1/2] 헤드 학습")
    model.fit(train_ds, validation_data=val_ds, epochs=args.epochs, class_weight=weights, callbacks=callbacks)

    if args.finetune_epochs:
        print("\n[2/2] 백본 상위 레이어 미세조정")
        base = model.get_layer("MobilenetV3small")
        base.trainable = True
        for layer in base.layers[:-30]:
            layer.trainable = False
        model.compile(optimizer=tf.keras.optimizers.Adam(1e-5), loss="binary_crossentropy", metrics=metrics)
        model.fit(train_ds, validation_data=val_ds, epochs=args.finetune_epochs, class_weight=weights, callbacks=callbacks)

    model.save(BUILD / "final.keras")
    print(f"\n저장 완료: {checkpoint} (최고 정밀도), {BUILD / 'final.keras'} (최종)")
    print("다음: python export_tflite.py && python eval.py")


if __name__ == "__main__":
    main()
