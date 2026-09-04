"""수집한 스크린샷을 학습용으로 정리한다.

datasets/raw/{shorts,not_shorts}/ 에 스크린샷을 넣고 실행하면
datasets/split/{train,val}/{shorts,not_shorts}/ 로 나눠 준다.

    python prepare.py --val-ratio 0.2
"""

import argparse
import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "datasets" / "raw"
SPLIT = ROOT / "datasets" / "split"
LABELS = ("shorts", "not_shorts")
SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if SPLIT.exists():
        shutil.rmtree(SPLIT)

    rng = random.Random(args.seed)
    summary = {}

    for label in LABELS:
        images = [p for p in sorted((RAW / label).glob("*")) if p.suffix.lower() in SUFFIXES]
        if not images:
            raise SystemExit(f"{RAW / label} 에 이미지가 없습니다.")

        rng.shuffle(images)
        n_val = max(1, round(len(images) * args.val_ratio))
        buckets = {"val": images[:n_val], "train": images[n_val:]}

        for split, files in buckets.items():
            target = SPLIT / split / label
            target.mkdir(parents=True, exist_ok=True)
            for src in files:
                shutil.copy2(src, target / src.name)

        summary[label] = {k: len(v) for k, v in buckets.items()}

    print(f"{'라벨':<12}{'train':>8}{'val':>8}")
    for label, counts in summary.items():
        print(f"{label:<12}{counts['train']:>8}{counts['val']:>8}")

    totals = [sum(c[s] for c in summary.values()) for s in ("train", "val")]
    print(f"{'합계':<12}{totals[0]:>8}{totals[1]:>8}")

    ratio = summary["shorts"]["train"] / max(1, summary["not_shorts"]["train"])
    if not 0.5 <= ratio <= 2.0:
        print(f"\n[경고] 클래스 불균형 {ratio:.2f}:1 — train.py 가 가중치로 보정하지만 데이터를 더 모으는 편이 낫습니다.")


if __name__ == "__main__":
    main()
