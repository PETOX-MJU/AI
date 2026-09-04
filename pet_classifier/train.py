"""반려동물 종·털길이 분류기 (MobileNetV3-Small, 2-헤드).

품종은 일부러 뺐다. 캐릭터 템플릿 선택에는 종·털길이·색이면 충분하고,
품종 데이터셋(Stanford Dogs 등)은 상업 이용 조건이 걸릴 수 있다.
LICENSING.md 「데이터 전략」 참고.

색은 모델이 아니라 color.py 의 팔레트 분석이 담당한다.

    datasets/pets/labels.csv  형식: filename,species,coat
    python train.py --epochs 20
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

SPECIES = ("개", "고양이", "기타")
COAT = ("단모", "장모", "곱슬")


def load_manifest() -> list[dict]:
    manifest = DATA / "labels.csv"
    if not manifest.exists():
        raise SystemExit(
            f"{manifest} 가 없습니다.\n"
            "형식: filename,species,coat\n"
            f"  species: {'|'.join(SPECIES)}\n"
            f"  coat: {'|'.join(COAT)}"
        )

    rows = []
    with manifest.open(encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            if row["species"] not in SPECIES or row["coat"] not in COAT:
                raise SystemExit(f"{manifest}:{i} 라벨 값이 잘못됐습니다: {row}")
            if not (DATA / row["filename"]).exists():
                raise SystemExit(f"{manifest}:{i} 파일이 없습니다: {row['filename']}")
            rows.append(row)

    if not rows:
        raise SystemExit("labels.csv 가 비어 있습니다.")
    return rows


def build_dataset(rows: list[dict], batch_size: int, shuffle: bool) -> tf.data.Dataset:
    paths = [str(DATA / r["filename"]) for r in rows]
    species = [SPECIES.index(r["species"]) for r in rows]
    coat = [COAT.index(r["coat"]) for r in rows]

    def load(path, s, c):
        image = tf.io.decode_image(tf.io.read_file(path), channels=3, expand_animations=False)
        image = tf.image.resize(image, IMG_SIZE)
        return image, {"species": s, "coat": c}

    ds = tf.data.Dataset.from_tensor_slices((paths, species, coat))
    if shuffle:
        ds = ds.shuffle(len(paths), reshuffle_each_iteration=True)
    return ds.map(load, num_parallel_calls=tf.data.AUTOTUNE).batch(batch_size).prefetch(tf.data.AUTOTUNE)


def build_model() -> tf.keras.Model:
    base = tf.keras.applications.MobileNetV3Small(
        input_shape=(*IMG_SIZE, 3), include_top=False, weights="imagenet", include_preprocessing=True
    )
    base.trainable = False

    augment = tf.keras.Sequential(
        [
            tf.keras.layers.RandomFlip("horizontal"),  # 동물은 좌우 대칭이라 반전해도 된다
            tf.keras.layers.RandomBrightness(0.2),
            tf.keras.layers.RandomRotation(0.08),
            tf.keras.layers.RandomZoom(0.15),
        ],
        name="augment",
    )

    inputs = tf.keras.Input(shape=(*IMG_SIZE, 3))
    x = base(augment(inputs), training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    return tf.keras.Model(
        inputs,
        {
            "species": tf.keras.layers.Dense(len(SPECIES), activation="softmax", name="species")(x),
            "coat": tf.keras.layers.Dense(len(COAT), activation="softmax", name="coat")(x),
        },
        name="pet_classifier",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    args = parser.parse_args()

    rows = load_manifest()
    rng = np.random.default_rng(42)
    rng.shuffle(rows)
    n_val = max(1, round(len(rows) * args.val_ratio))
    val_rows, train_rows = rows[:n_val], rows[n_val:]
    print(f"train {len(train_rows)} / val {len(val_rows)}")

    train_ds = build_dataset(train_rows, args.batch_size, shuffle=True)
    val_ds = build_dataset(val_rows, args.batch_size, shuffle=False)

    BUILD.mkdir(exist_ok=True)
    model = build_model()
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss={"species": "sparse_categorical_crossentropy", "coat": "sparse_categorical_crossentropy"},
        # 종을 틀리면 캐릭터가 통째로 어긋나므로 더 무겁게 본다
        loss_weights={"species": 1.0, "coat": 0.5},
        metrics={"species": "accuracy", "coat": "accuracy"},
    )
    model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=args.epochs,
        callbacks=[
            tf.keras.callbacks.ModelCheckpoint(BUILD / "best.keras", monitor="val_species_accuracy", mode="max", save_best_only=True),
            tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True),
        ],
    )
    model.save(BUILD / "final.keras")
    print(f"\n저장: {BUILD / 'best.keras'}\n다음: python export_tflite.py")


if __name__ == "__main__":
    main()
