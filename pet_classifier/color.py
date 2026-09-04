"""배경 제거된 반려동물 이미지에서 대표 털색을 뽑는다.

모델이 아니라 팔레트 분석이다. `../pixelart/` 가 이미 같은 양자화를 하므로
앱에서는 그 결과를 재활용하면 연산이 한 번 더 들지 않는다.

    python color.py ../pixelart/samples/dog.jpg
"""

import argparse
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

# 앱이 쓰는 색 열거값. 한국어 표기는 여기서 결정한다.
PALETTE = {
    "검정": (35, 33, 38),
    "흰색": (245, 244, 242),
    "회색": (140, 140, 145),
    "갈색": (110, 75, 48),
    "황금색": (205, 155, 80),
    "크림색": (235, 215, 180),
    "주황색": (215, 125, 55),
}


def dominant_colors(image: Image.Image, top_k: int = 2, quantize_to: int = 16) -> list[tuple[str, float]]:
    """불투명 픽셀만 보고 팔레트 색으로 매핑한 뒤 비율 순으로 돌려준다."""
    rgba = image.convert("RGBA")
    arr = np.array(rgba)
    opaque = arr[:, :, 3] > 128
    pixels = arr[:, :, :3][opaque]

    if len(pixels) == 0:
        return []

    # 색 수를 줄여야 조명 편차에 흔들리지 않는다
    pixels = (pixels // (256 // quantize_to)) * (256 // quantize_to)

    names = np.array(list(PALETTE))
    refs = np.array(list(PALETTE.values()), dtype=np.int16)
    # 각 픽셀을 가장 가까운 팔레트 색으로. 유클리드 거리로 충분하다.
    distances = np.linalg.norm(pixels[:, None, :].astype(np.int16) - refs[None, :, :], axis=2)
    assigned = names[np.argmin(distances, axis=1)]

    counts = Counter(assigned.tolist())
    total = sum(counts.values())
    return [(name, count / total) for name, count in counts.most_common(top_k)]


def extract(image_path: Path, min_ratio: float = 0.15) -> dict:
    """main_color 는 항상 있고, sub_color 는 비율이 min_ratio 를 넘을 때만 준다."""
    ranked = dominant_colors(Image.open(image_path))
    if not ranked:
        return {"main_color": None, "sub_color": None}

    main = ranked[0][0]
    sub = ranked[1][0] if len(ranked) > 1 and ranked[1][1] >= min_ratio else None
    return {"main_color": main, "sub_color": sub}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    args = parser.parse_args()

    for name, ratio in dominant_colors(Image.open(args.image), top_k=4):
        print(f"{name:>6}  {ratio:5.1%}")
    print("\n->", extract(args.image))


if __name__ == "__main__":
    main()
