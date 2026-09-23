"""숏폼 화면 분류기 학습 (MobileNetV3-Small 전이학습).

출력이 TFLite여야 하므로 Keras로 학습한다. PyTorch→ONNX→TFLite 경로는 실패 지점이 많다.

    python prepare.py
    python train.py --epochs 15

입력은 448x224(세로x가로)가 기본이다. 224x224 와 같은 조건(분할·seed)으로 비교했을 때
AUC 0.904 → 0.942, 오탐률 11.2% → 6.8% (임계값 0.5). 세로 화면을 정사각형으로 누르면
오른쪽 버튼 열·스토리 진행 막대 같은 작은 UI 가 뭉개진다. 모델 크기는 같고 연산만 약 2배.
"""

import argparse
from pathlib import Path

import tensorflow as tf

ROOT = Path(__file__).resolve().parent.parent
SPLIT = ROOT / "datasets" / "split"
BUILD = Path(__file__).resolve().parent / "build"
# 폴더명 알파벳 순으로 인덱스가 매겨진다: not_shorts=0, shorts=1
CLASS_NAMES = ("not_shorts", "shorts")


def load_datasets(split: Path, batch_size: int, img_size: tuple[int, int], seed: int):
    common = dict(image_size=img_size, batch_size=batch_size, label_mode="binary", class_names=CLASS_NAMES, seed=seed)
    train = tf.keras.utils.image_dataset_from_directory(split / "train", shuffle=True, **common)
    val = tf.keras.utils.image_dataset_from_directory(split / "val", shuffle=False, **common)
    return train, val


def class_weights(train_ds) -> dict[int, float]:
    """숏폼 샘플이 적을 때 한쪽으로 쏠리는 걸 막는다."""
    counts = [0, 0]
    for _, labels in train_ds.unbatch():
        counts[int(labels.numpy()[0])] += 1
    total = sum(counts)
    return {i: total / (2 * c) if c else 1.0 for i, c in enumerate(counts)}


def build_model(img_size: tuple[int, int]) -> tf.keras.Model:
    base = tf.keras.applications.MobileNetV3Small(
        input_shape=(*img_size, 3),
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

    inputs = tf.keras.Input(shape=(*img_size, 3))
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
    parser.add_argument("--input", default="448x224", help="입력 크기 세로x가로. 변환·평가는 모델에서 읽는다")
    parser.add_argument("--seed", type=int, default=42, help="같은 데이터로 설정을 비교할 때 고정한다")
    parser.add_argument("--split-dir", type=Path, default=SPLIT, help="train/ val/ 이 있는 폴더 (audit_labels.py 가 쓴다)")
    parser.add_argument("--build-dir", type=Path, default=BUILD)
    args = parser.parse_args()
    img_size = tuple(map(int, args.input.lower().split("x")))
    tf.keras.utils.set_random_seed(args.seed)  # 가중치 초기화·증강·셔플

    if not args.split_dir.exists():
        raise SystemExit(f"{args.split_dir} 가 없습니다. 먼저 `python prepare.py` 를 실행하세요.")

    train_ds, val_ds = load_datasets(args.split_dir, args.batch_size, img_size, args.seed)
    print(f"입력 {img_size[0]}x{img_size[1]}, seed {args.seed}")
    weights = class_weights(train_ds)
    print(f"클래스 가중치: {weights}")

    train_ds = train_ds.prefetch(tf.data.AUTOTUNE)
    val_ds = val_ds.prefetch(tf.data.AUTOTUNE)

    args.build_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = args.build_dir / "best.keras"
    metrics = [
        tf.keras.metrics.BinaryAccuracy(name="acc"),
        tf.keras.metrics.Precision(name="precision"),
        tf.keras.metrics.Recall(name="recall"),
    ]
    callbacks = [
        # 정밀도로 고르면 숏폼을 몇 장만 조심스럽게 맞히는 초반 모델이 100%로 뽑힌다.
        # 저장은 손실로 하고, 정밀도 우선 판정은 eval.py 의 임계값 선택에서 한다.
        tf.keras.callbacks.ModelCheckpoint(checkpoint, monitor="val_loss", mode="min", save_best_only=True),
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True),
    ]

    model = build_model(img_size)
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="binary_crossentropy", metrics=metrics)

    print("\n[1/2] 헤드 학습")
    model.fit(train_ds, validation_data=val_ds, epochs=args.epochs, class_weight=weights, callbacks=callbacks)

    if args.finetune_epochs:
        print("\n[2/2] 백본 상위 레이어 미세조정")
        # Keras 버전마다 이름 대소문자가 다르다 (2.x: MobilenetV3small, 3.x: MobileNetV3Small)
        base = next(l for l in model.layers if l.name.lower() == "mobilenetv3small")
        base.trainable = True
        for layer in base.layers[:-30]:
            layer.trainable = False
        model.compile(optimizer=tf.keras.optimizers.Adam(1e-5), loss="binary_crossentropy", metrics=metrics)
        model.fit(train_ds, validation_data=val_ds, epochs=args.finetune_epochs, class_weight=weights, callbacks=callbacks)

    model.save(args.build_dir / "final.keras")
    print(f"\n저장 완료: {checkpoint} (최저 검증 손실), {args.build_dir / 'final.keras'} (최종)")
    print("다음: python export_tflite.py && python eval.py")


if __name__ == "__main__":
    main()
