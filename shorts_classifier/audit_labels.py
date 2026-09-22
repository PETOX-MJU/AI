"""녹화 단위 교차 채점으로 라벨이 의심스러운 프레임을 찾는다.

녹화를 K 묶음으로 나눠, 한 묶음을 빼고 학습한 모델로 그 묶음을 채점한다 (K번).
모든 프레임이 자기를 본 적 없는 모델에게 채점되므로, 모델이 틀린 라벨을 외워서 감추는 일이 없다.
라벨과 점수가 크게 어긋난 프레임을 세션별 격자로 모은다.

    python audit_labels.py              # 4묶음, 학습 4번 (약 25분)
    python audit_labels.py --folds 3

결과: datasets/review/audit/{세션}.jpg (의심 프레임만), datasets/review/audit/scores.csv (전체 점수)
이 스크립트는 raw 의 파일을 옮기지 않는다. 사람이 격자를 보고 라벨을 고친다.
test 로 잠근 세션은 채점하지 않는다 (test 는 한 번만 본다).
"""

import argparse
import csv
import random
import shutil
import subprocess
import sys
from pathlib import Path

import tensorflow as tf

from collect_android import review_sheet
from prepare import LABELS, ROOT, group_sessions, load_items, load_test_sessions, session_of, split_sessions

WORK = ROOT / "datasets" / "audit_work"
OUT = ROOT / "datasets" / "review" / "audit"


def assign_folds(items, k: int, seed: int) -> dict[str, int]:
    """세션 → 묶음 번호. (앱, 주된 라벨) 묶음마다 돌려 가며 배정해 묶음끼리 구성이 비슷하게 한다."""
    _, groups = group_sessions(items)
    rng, fold, i = random.Random(seed), {}, 0
    for group in sorted(groups):
        keys = groups[group][:]
        rng.shuffle(keys)
        for key in keys:
            fold[key] = i % k
            i += 1
    return fold


def link_split(items, fold: dict[str, int], k: int, root: Path, seed: int) -> None:
    """묶음 k 는 빼 두고(채점만), 나머지로 train/val 분할을 심볼릭 링크로 만든다.
    val 은 체크포인트·조기 종료에 쓰이므로 채점할 묶음과 겹치면 그 라벨이 모델 선택에 샌다."""
    rest = [x for x in items if fold[session_of(x[1])] != k]
    buckets = split_sessions(rest, 0.2, random.Random(seed))
    for split, split_items in buckets.items():
        for label in LABELS:
            (root / split / label).mkdir(parents=True)
        for label, p in split_items:
            (root / split / label / p.name).symlink_to(p)


def score(model: tf.keras.Model, paths: list[Path]) -> list[float]:
    h, w = model.input_shape[1:3]
    out = []
    for i in range(0, len(paths), 32):
        batch = [
            tf.image.resize(tf.io.decode_image(tf.io.read_file(str(p)), channels=3, expand_animations=False), (h, w))
            for p in paths[i : i + 32]
        ]  # 학습(image_dataset_from_directory)과 같은 bilinear 리사이즈
        out += model.predict(tf.stack(batch), verbose=0).ravel().tolist()
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--hi", type=float, default=0.7, help="숏폼 아님인데 이 점수 이상이면 의심")
    parser.add_argument("--lo", type=float, default=0.3, help="숏폼인데 이 점수 이하면 의심")
    args = parser.parse_args()

    test = load_test_sessions()
    items = [x for x in load_items() if session_of(x[1]) not in test]
    fold = assign_folds(items, args.folds, args.seed)

    scores = {}
    for k in range(args.folds):
        shutil.rmtree(WORK, ignore_errors=True)
        link_split(items, fold, k, WORK / "split", args.seed)
        held = [p for _, p in items if fold[session_of(p)] == k]
        print(f"[{k + 1}/{args.folds}] 녹화 {sum(v == k for v in fold.values())}개 ({len(held)}장)를 빼고 학습", flush=True)
        subprocess.run(
            [sys.executable, "train.py", "--split-dir", str(WORK / "split"), "--build-dir", str(WORK / "build"), "--seed", str(args.seed)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=Path(__file__).parent,
        )
        model = tf.keras.models.load_model(WORK / "build" / "best.keras")
        scores.update(zip(held, score(model, held)))
    shutil.rmtree(WORK, ignore_errors=True)

    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    with open(OUT / "scores.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["session", "file", "label", "score"])
        for label, p in items:
            writer.writerow([session_of(p), p.name, label, f"{scores[p]:.3f}"])

    def suspicious(label, p):
        return scores[p] >= args.hi if label == "not_shorts" else scores[p] <= args.lo

    print(f"\n의심 기준: 숏폼 아님인데 {args.hi} 이상, 숏폼인데 {args.lo} 이하")
    rows = []
    for key in sorted({session_of(p) for _, p in items}):
        frames = sorted(((label, p) for label, p in items if session_of(p) == key), key=lambda x: x[1].name)
        bad = [(label, p) for label, p in frames if suspicious(label, p)]
        rows.append((len(bad), key, len(frames), bad))
        if bad:
            review_sheet([p for _, p in bad], OUT / f"{key}.jpg", cols=6, width=160)
    for n, key, total, bad in sorted(rows, reverse=True):
        if n:
            detail = " ".join(f"{p.stem.split('_')[-1]}{'숏' if label == 'shorts' else '아'}({scores[p]:.2f})" for label, p in bad)
            print(f"{key:<22} {n:>3}/{total:<3} {detail}")
    print(f"\n의심 {sum(r[0] for r in rows)}장 / 전체 {len(items)}장. 격자: {OUT}")


if __name__ == "__main__":
    main()
