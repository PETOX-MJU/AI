"""수집한 스크린샷을 학습용으로 정리한다.

datasets/raw/{shorts,not_shorts}/ 에 스크린샷을 넣고 실행하면
datasets/split/{train,val}/{shorts,not_shorts}/ 로 나눠 준다.

**세션 단위로 나눈다.** 같은 녹화에서 뽑은 프레임은 거의 똑같아서, 장 단위로 나누면
train 과 val 에 쌍둥이가 들어가 검증 점수만 부풀고 현장에서 무너진다.
파일명 `{기기}_{앱}_{세션}_{번호}.jpg` 의 앞 세 조각이 세션이다.

**앱별로 따로 나눈다.** 라벨 전체에서 한꺼번에 뽑으면 "train 숏폼은 전부 유튜브,
train 아님은 전부 인스타" 같은 분할이 나와 모델이 앱 모양만 외운다.
세션이 하나뿐인 앱은 통째로 train 에 간다.

**test 세션은 잠근다.** `datasets/test_sessions.txt` 에 한 줄에 하나씩 세션을 적으면
그 세션은 매번 `split/test/` 로만 가고 train·val 에는 절대 섞이지 않는다.
val 은 모델·임계값을 고르는 데 쓰여 수치가 낙관적이므로, 최종 판정은 test 로 한 번만 한다.

    python prepare.py --val-ratio 0.2
"""

import argparse
import random
import shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "datasets" / "raw"
SPLIT = ROOT / "datasets" / "split"
TEST_LIST = ROOT / "datasets" / "test_sessions.txt"
LABELS = ("shorts", "not_shorts")
SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def session_of(path: Path) -> str:
    """galaxyA_yt_s01_0007 → galaxyA_yt_s01. 규칙 밖 이름(Screenshot_20250915-123456)은 사실상 한 장이 한 세션."""
    return "_".join(path.stem.split("_")[:3])


def split_sessions(images: list[Path], val_ratio: float, rng: random.Random) -> dict[str, list[Path]]:
    by_app = defaultdict(lambda: defaultdict(list))
    for p in images:
        session = session_of(p)
        app = session.split("_")[1] if "_" in session else session
        by_app[app][session].append(p)

    buckets = {"val": [], "train": []}
    for app in sorted(by_app):
        sessions = by_app[app]
        keys = sorted(sessions)
        rng.shuffle(keys)
        n_val = max(1, round(sum(map(len, sessions.values())) * val_ratio))
        val = []
        for i, key in enumerate(keys):
            # 목표 장수를 채울 때까지 세션째로 val 에 넣는다. 마지막 세션은 항상 train.
            (buckets["train"] if len(val) >= n_val or i == len(keys) - 1 else val).extend(sessions[key])
        buckets["val"].extend(val)
    return buckets


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    images_by_label = {
        label: [p for p in sorted((RAW / label).glob("*")) if p.suffix.lower() in SUFFIXES] for label in LABELS
    }
    test_sessions = set()
    if TEST_LIST.exists():
        lines = (line.split("#")[0].strip() for line in TEST_LIST.read_text().splitlines())
        test_sessions = {line for line in lines if line}
        # 오타가 나면 test 로 뺄 세션이 train 에 섞인다. 조용히 넘어가지 않는다.
        found = {session_of(p) for images in images_by_label.values() for p in images}
        if missing := test_sessions - found:
            raise SystemExit(f"{TEST_LIST} 의 세션이 datasets/raw 에 없습니다: {sorted(missing)}")

    if SPLIT.exists():
        shutil.rmtree(SPLIT)

    rng = random.Random(args.seed)
    summary = {}

    for label in LABELS:
        images = [p for p in images_by_label[label] if session_of(p) not in test_sessions]
        if not images:
            raise SystemExit(f"{RAW / label} 에 이미지가 없습니다.")

        buckets = split_sessions(images, args.val_ratio, rng)
        if not buckets["val"]:
            raise SystemExit(f"{RAW / label}: 세션이 2개 이상인 앱이 없어 val 을 만들 수 없습니다.")
        if test_sessions:
            buckets["test"] = [p for p in images_by_label[label] if session_of(p) in test_sessions]

        for split, files in buckets.items():
            target = SPLIT / split / label
            target.mkdir(parents=True, exist_ok=True)
            for src in files:
                shutil.copy2(src, target / src.name)

        summary[label] = {k: len(v) for k, v in buckets.items()}

    splits = ("train", "val", "test") if test_sessions else ("train", "val")
    print(f"{'라벨':<12}" + "".join(f"{s:>8}" for s in splits))
    for label, counts in summary.items():
        print(f"{label:<12}" + "".join(f"{counts[s]:>8}" for s in splits))
    print(f"{'합계':<12}" + "".join(f"{sum(c[s] for c in summary.values()):>8}" for s in splits))

    if test_sessions:
        print(f"\ntest 로 잠근 세션: {', '.join(sorted(test_sessions))}")
        if any(summary[label]["test"] == 0 for label in LABELS):
            print("[경고] test 에 한쪽 라벨이 없습니다. 정밀도·재현율 중 하나를 잴 수 없습니다.")

    ratio = summary["shorts"]["train"] / max(1, summary["not_shorts"]["train"])
    if not 0.5 <= ratio <= 2.0:
        print(f"\n[경고] 클래스 불균형 {ratio:.2f}:1 — train.py 가 가중치로 보정하지만 데이터를 더 모으는 편이 낫습니다.")


if __name__ == "__main__":
    main()
