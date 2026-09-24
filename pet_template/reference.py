"""반려동물 사진 → 견종 템플릿 재색칠 기준 구현.

이 파일은 **Kotlin 이식용 기준**이다. 파라미터를 여기서 튜닝해 확정한 뒤
같은 알고리즘을 앱의 Bitmap 연산으로 옮긴다. 이식이 목적이므로
파이썬다운 축약보다 단계가 드러나는 쪽을 택했다.

앱에서의 대응:
    remove_background  → ML Kit Subject Segmentation (여기서는 rembg 로 근사)
    color_map          → 그대로 이식 (Lab 변환 포함)
    recolor_image      → Bitmap 픽셀 치환
"""

import re
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).parent
ASSETS = HERE / "assets"

SVG_SIZE = re.compile(r"width='(\d+)' height='(\d+)'")
SVG_RECT = re.compile(
    r"<rect x='([\d.]+)' y='([\d.]+)' width='([\d.]+)' height='([\d.]+)' fill='(#[0-9a-fA-F]{6})'"
)

# ── 색 공간 ─────────────────────────────────────────────
# sRGB(D65) ↔ CIE Lab. 외부 라이브러리 없이 쓴다 — Kotlin 으로 그대로 옮기기 위해서다.
_M = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ]
)
_M_INV = np.linalg.inv(_M)
_WHITE = np.array([0.95047, 1.0, 1.08883])
_E = 6 / 29


def hex_to_rgb8(h: str) -> tuple:
    return tuple(int(h[i : i + 2], 16) for i in (1, 3, 5))


def rgb8_to_hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb)


def rgb_to_lab(rgb) -> np.ndarray:
    """rgb: (..., 3), 0~1."""
    rgb = np.asarray(rgb, dtype=float)
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = lin @ _M.T / _WHITE
    f = np.where(xyz > _E**3, np.cbrt(xyz), xyz / (3 * _E**2) + 4 / 29)
    return np.stack(
        [116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1
    )


def lab_to_rgb(lab) -> np.ndarray:
    """Lab → rgb 0~1. sRGB 밖으로 나가는 색은 잘라낸다."""
    lab = np.asarray(lab, dtype=float)
    fy = (lab[..., 0] + 16) / 116
    f = np.stack([fy + lab[..., 1] / 500, fy, fy - lab[..., 2] / 200], axis=-1)
    xyz = np.where(f > _E, f**3, 3 * _E**2 * (f - 4 / 29)) * _WHITE
    lin = np.clip(xyz @ _M_INV.T, 0, 1)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)


def hex_to_lab(h: str) -> np.ndarray:
    return rgb_to_lab(np.array(hex_to_rgb8(h)) / 255)


def lab_to_hex(lab) -> str:
    return rgb8_to_hex(np.round(lab_to_rgb(lab) * 255))


# ── 에셋 읽기 ───────────────────────────────────────────
def render_svg(text: str) -> Image.Image:
    """Pixelorama SVG 를 RGBA 비트맵으로. 픽셀당 <rect> 하나라 래스터라이저가 필요 없다."""
    w, h = map(int, SVG_SIZE.search(text).groups())
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for x, y, rw, rh, fill in SVG_RECT.findall(text):
        x, y = int(float(x)), int(float(y))
        draw.rectangle((x, y, x + int(float(rw)) - 1, y + int(float(rh)) - 1), fill=fill)
    return img


def asset_frames(path: Path) -> list:
    """SVG 는 한 장, GIF 는 전 프레임을 RGBA 로."""
    if path.suffix == ".svg":
        return [render_svg(path.read_text())]
    gif = Image.open(path)
    frames = []
    for i in range(gif.n_frames):
        gif.seek(i)
        frames.append(gif.convert("RGBA"))
    return frames


def frame_colors(img: Image.Image) -> Counter:
    """불투명 픽셀의 hex 별 개수. GIF 투명색(#00ff00)은 알파 0 이라 빠진다."""
    counts = Counter()
    for n, (r, g, b, a) in img.getcolors(img.width * img.height):
        if a:
            counts[rgb8_to_hex((r, g, b))] += n
    return counts
