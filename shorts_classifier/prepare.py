"""수집한 스크린샷을 학습용으로 정리한다.

datasets/raw/{shorts,not_shorts}/ 에 스크린샷을 넣고 실행하면
datasets/split/{train,val}/{shorts,not_shorts}/ 로 나눠 준다.

**녹화(세션) 단위로 나눈다.** 같은 녹화에서 뽑은 프레임은 거의 똑같아서, 장 단위로 나누면
train 과 val 에 쌍둥이가 들어가 검증 점수만 부풀고 현장에서 무너진다.
한 녹화에 두 라벨이 섞여 있어도(예: 피드를 넘기다 릴스가 뜬 녹화) 통째로 한쪽에 간다.
파일명 `{기기}_{앱}_{세션}_{번호}.jpg` 의 앞 세 조각이 세션이다.

**(앱, 녹화의 주된 라벨) 묶음마다 따로 나눈다.** 한꺼번에 뽑으면 "train 숏폼은 전부 유튜브,
train 아님은 전부 인스타" 같은 분할이 나와 모델이 앱 모양만 외운다.
녹화가 하나뿐인 묶음은 통째로 train 에 간다.

**test 세션은 잠근다.** `datasets/test_sessions.txt` 에 한 줄에 하나씩 세션을 적으면
그 세션은 매번 `split/test/` 로만 가고 train·val 에는 절대 섞이지 않는다.
val 은 모델·임계값을 고르는 데 쓰여 수치가 낙관적이므로, 최종 판정은 test 로 한 번만 한다.

    python prepare.py --val-ratio 0.2
"""

import argparse
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "datasets" / "raw"
SPLIT = ROOT / "datasets" / "split"
TEST_LIST = ROOT / "datasets" / "test_sessions.txt"
LABELS = ("shorts", "not_shorts")
SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

Item = tuple[str, Path]  # (라벨, 파일)


def session_of(path: Path) -> str:
    """galaxyA_yt_s01_0007 → galaxyA_yt_s01. 규칙 밖 이름(Screenshot_20250915-123456)은 사실상 한 장이 한 세션."""
    return "_".join(path.stem.split("_")[:3])


def load_items() -> list[Item]:
    return [(label, p) for label in LABELS for p in sorted((RAW / label).glob("*")) if p.suffix.lower() in SUFFIXES]


def load_test_sessions() -> set[str]:
    if not TEST_LIST.exists():
        return set()
    lines = (line.split("#")[0].strip() for line in TEST_LIST.read_text().splitlines())
    return {line for line in lines if line}


def group_sessions(items: list[Item]) -> tuple[dict[str, list[Item]], dict[tuple[str, str], list[str]]]:
    """세션별 프레임, 그리고 (앱, 주된 라벨) 묶음별 세션 목록."""
    sessions = defaultdict(list)
    for label, p in items:
        sessions[session_of(p)].append((label, p))
    groups = defaultdict(list)
    for key, frames in sorted(sessions.items()):
        app = key.split("_")[1] if "_" in key else key
        main_label = Counter(label for label, _ in frames).most_common(1)[0][0]
        groups[(app, main_label)].append(key)
    return sessions, groups


def one_label_devices(items: list[Item]) -> dict[str, str]:
    """라벨 한쪽만 가진 기기 → 그 라벨. 이런 기기가 섞이면 모델이 화면 내용 대신 기기 모양(해상도·상태바)으로
    라벨을 맞힌다 (예전에 겪은 기기 지름길). 분할은 기기를 모르므로 여기서 따로 잡는다."""
    labels = defaultdict(set)
    for label, p in items:
        labels[p.stem.split("_")[0]].add(label)
    return {device: next(iter(found)) for device, found in sorted(labels.items()) if len(found) == 1}


def split_sessions(items: list[Item], val_ratio: float, rng: random.Random) -> dict[str, list[Item]]:
    sessions, groups = group_sessions(items)
    buckets = {"val": [], "train": []}
    for group in sorted(groups):
        keys = groups[group][:]
        rng.shuffle(keys)
        n_val = max(1, round(sum(len(sessions[k]) for k in keys) * val_ratio))
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

    items = load_items()
    test_sessions = load_test_sessions()
    # 오타가 나면 test 로 뺄 세션이 train 에 섞인다. 조용히 넘어가지 않는다.
    if missing := test_sessions - {session_of(p) for _, p in items}:
        raise SystemExit(f"{TEST_LIST} 의 세션이 datasets/raw 에 없습니다: {sorted(missing)}")

    buckets = split_sessions([x for x in items if session_of(x[1]) not in test_sessions], args.val_ratio, random.Random(args.seed))
    if test_sessions:
        buckets["test"] = [x for x in items if session_of(x[1]) in test_sessions]
    for split in ("train", "val"):
        for label in LABELS:
            if not any(lab == label for lab, _ in buckets[split]):
                raise SystemExit(f"{split} 에 {label} 가 없습니다. 녹화를 더 모으세요 (묶음마다 녹화가 2개 이상 필요).")

    if SPLIT.exists():
        shutil.rmtree(SPLIT)
    for split, pairs in buckets.items():
        for label in LABELS:
            (SPLIT / split / label).mkdir(parents=True, exist_ok=True)
        for label, src in pairs:
            shutil.copy2(src, SPLIT / split / label / src.name)

    splits = list(buckets)
    count = {(s, label): sum(lab == label for lab, _ in buckets[s]) for s in splits for label in LABELS}
    print(f"{'라벨':<12}" + "".join(f"{s:>8}" for s in splits))
    for label in LABELS:
        print(f"{label:<12}" + "".join(f"{count[s, label]:>8}" for s in splits))
    print(f"{'합계':<12}" + "".join(f"{len(buckets[s]):>8}" for s in splits))

    if test_sessions:
        print(f"\ntest 로 잠근 세션: {', '.join(sorted(test_sessions))}")
        if any(count["test", label] == 0 for label in LABELS):
            print("[경고] test 에 한쪽 라벨이 없습니다. 정밀도·재현율 중 하나를 잴 수 없습니다.")

    for split in buckets:  # 잠근 test 도 본다. test 에서 기기로 라벨이 갈리면 최종 평가가 부푼다
        if skewed := one_label_devices(buckets[split]):
            lines = ", ".join(f"{device}={label}" for device, label in skewed.items())
            print(f"\n[경고] {split} 에 라벨 한쪽만 있는 기기: {lines}")
            print("모델이 기기 모양으로 라벨을 맞힐 수 있습니다. 그 기기에서 반대 라벨 녹화를 더 모으세요.")

    ratio = count["train", "shorts"] / max(1, count["train", "not_shorts"])
    if not 0.5 <= ratio <= 2.0:
        print(f"\n[경고] 클래스 불균형 {ratio:.2f}:1 — train.py 가 가중치로 보정하지만 데이터를 더 모으는 편이 낫습니다.")


if __name__ == "__main__":
    main()
