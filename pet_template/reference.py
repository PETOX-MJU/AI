"""반려동물 사진 → 견종 템플릿 재색칠 기준 구현.

이 파일은 **Kotlin 이식용 기준**이다. 파라미터를 여기서 튜닝해 확정한 뒤
같은 알고리즘을 앱의 Bitmap 연산으로 옮긴다. 이식이 목적이므로
파이썬다운 축약보다 단계가 드러나는 쪽을 택했다.

앱에서의 대응:
    remove_background  → ML Kit Subject Segmentation (여기서는 rembg 로 근사)
    color_map          → 그대로 이식 (Lab 변환 포함)
    recolor_image      → Bitmap 픽셀 치환
"""

import argparse
import json
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


# ── 역할표 ─────────────────────────────────────────────
ROLES = ("main", "sub", "keep")
HEX = re.compile(r"^#[0-9a-f]{6}$")

# 역할표 초안용. 초안은 반드시 --roles-sheet 로 사람이 검수한다.
SUGGEST_DARK_L = 12  # 이보다 어두우면 외곽선·눈·코로 본다
SUGGEST_SUB_DIST = 25  # main 과 Lab 거리가 이보다 멀면 sub 무리 후보


def load_breeds(path: Path = HERE / "breeds.json") -> dict:
    """breeds.json 을 읽고 검사한다. 잘못되면 ValueError — 배포 전에 테스트가 잡는다."""
    data = json.loads(Path(path).read_text())
    for name, h in data["swatches"].items():
        if not HEX.match(h):
            raise ValueError(f"스와치 {name}: 잘못된 색 {h}")
    for name, breed in data["breeds"].items():
        for rel in breed["assets"].values():
            if not (ASSETS / rel).is_file():
                raise ValueError(f"{name}: 에셋 없음 {rel}")
        for h, role in breed["roles"].items():
            if not HEX.match(h) or role not in ROLES:
                raise ValueError(f"{name}: 잘못된 역할 {h} → {role}")
        if "main" not in breed["roles"].values():
            raise ValueError(f"{name}: main 역할이 없음")
    return data


def breed_colors(breed: dict) -> Counter:
    """견종 에셋 전체(모든 파일·모든 프레임)의 색 분포. 파일마다 색이 조금씩 달라 전부 모은다."""
    counts = Counter()
    for rel in breed["assets"].values():
        for frame in asset_frames(ASSETS / rel):
            counts += frame_colors(frame)
    return counts


def suggest_roles(counts: Counter) -> dict:
    """역할표 초안. 그대로 쓰지 말고 --roles-sheet 로 검수한 뒤 breeds.json 에 넣는다.

    어두운 색(외곽선·눈·코)과 분홍(귀 안쪽·혀)은 keep. 나머지 털색은
    가장 넓은 색(main)과, 그와 먼 첫 무리(sub) 중 가까운 쪽으로 나눈다.
    """
    labs = {h: hex_to_lab(h) for h in counts}
    roles, fur = {}, []
    for h, (L, a, b) in labs.items():
        if L < SUGGEST_DARK_L or (a > 12 and a > b):
            roles[h] = "keep"
        else:
            fur.append(h)
    fur.sort(key=lambda h: -counts[h])
    main = fur[0]

    def dist(h, ref):
        return float(np.linalg.norm(labs[h] - labs[ref]))

    sub = next((h for h in fur if dist(h, main) > SUGGEST_SUB_DIST), None)
    for h in fur:
        roles[h] = "sub" if sub and dist(h, sub) < dist(h, main) else "main"
    return dict(sorted(roles.items(), key=lambda kv: (ROLES.index(kv[1]), kv[0])))


# ── 재색칠 적용 ─────────────────────────────────────────
def recolor_image(img: Image.Image, cmap: dict) -> Image.Image:
    """색 치환표를 비트맵에 적용한다. 앱에서 이식할 부분은 이것 하나다 (SVG·GIF 공통)."""
    arr = np.array(img.convert("RGBA"))
    out = arr.copy()
    for src, dst in cmap.items():
        hit = (arr[..., :3] == hex_to_rgb8(src)).all(axis=-1) & (arr[..., 3] > 0)
        out[hit, :3] = hex_to_rgb8(dst)
    return Image.fromarray(out)


# ── 확인 시트 (눈 검수용) ────────────────────────────────
ROLE_PAINT = {"main": "#ff3b30", "sub": "#007aff"}  # 검수 시트에서 역할을 칠하는 색


def contact_sheet(rows: list, scale: int = 2, cell: int = 72) -> Image.Image:
    """행마다 프레임을 나란히 붙인다. 에셋 크기가 48·68·72 로 섞여 있어 칸을 72 로 고정한다."""
    width = max(len(r) for r in rows) * cell * scale
    out = Image.new("RGBA", (width, len(rows) * cell * scale), (255, 255, 255, 255))
    for y, row in enumerate(rows):
        for x, img in enumerate(row):
            big = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
            out.paste(big, (x * cell * scale, y * cell * scale), big)
    return out


def all_frames(breed: dict) -> list:
    return [f for rel in breed["assets"].values() for f in asset_frames(ASSETS / rel)]


def roles_sheet(data: dict) -> Image.Image:
    """견종마다 두 줄: 원본, 그리고 main=빨강·sub=파랑으로 칠한 것. 오분류가 한눈에 보인다."""
    rows = []
    for breed in data["breeds"].values():
        paint = {h: ROLE_PAINT[r] for h, r in breed["roles"].items() if r in ROLE_PAINT}
        frames = all_frames(breed)
        rows += [frames, [recolor_image(f, paint) for f in frames]]
    return contact_sheet(rows)


def draft_breeds() -> dict:
    """assets/ 를 훑어 breeds.json 초안을 만든다. 새 견종을 추가할 때 쓴다."""
    breeds = {}
    for folder in sorted(p for p in ASSETS.iterdir() if p.is_dir()):
        files = sorted(p for p in folder.iterdir() if p.suffix in (".svg", ".gif"))
        breed = {"assets": {p.stem: f"{folder.name}/{p.name}" for p in files}}
        breed["roles"] = suggest_roles(breed_colors(breed))
        breeds[folder.name] = breed
    return {"swatches": SWATCHES, "breeds": breeds}


# 사용자가 고를 털색. 사진 색은 여기 중 가장 가까운 것에 붙는다. 실사진으로 조정할 튜닝값.
SWATCHES = {
    "black": "#453d3e",  # L≈27. 더 어두우면 음영을 담을 밝기 여유가 없다
    "brown": "#6e4a32",
    "red": "#c47a45",
    "golden": "#e0a860",
    "cream": "#e8dcc0",
    "white": "#f4f2ee",
    "gray": "#8c8a90",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suggest-roles", action="store_true", help="breeds.json 초안을 출력한다")
    parser.add_argument("--roles-sheet", action="store_true", help="역할표 검수 시트를 만든다")
    args = parser.parse_args()

    if args.suggest_roles:
        print(json.dumps(draft_breeds(), ensure_ascii=False, indent=2))
    elif args.roles_sheet:
        out = HERE / "roles_sheet.png"
        roles_sheet(load_breeds()).save(out)
        print(f"역할 검수 시트 {out}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
