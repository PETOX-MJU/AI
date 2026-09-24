# 견종 템플릿 재색칠 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 반려동물 사진에서 털색을 뽑아, 사용자가 고른 견종 픽셀 템플릿을 그 색으로 재색칠하는 Kotlin 이식용 Python 기준 구현을 만들고 `pixelart/` 를 대체한다.

**Architecture:** 단일 모듈 `pet_template/reference.py`. 에셋(SVG·GIF)을 RGBA 프레임으로 읽고, 견종별 역할표(`breeds.json`, hex → main/sub/keep)에 따라 Lab 공간에서 색 치환표 `{원본 hex: 새 hex}` 를 만든다. 사진 쪽은 배경 제거 → 불투명 픽셀마다 가장 가까운 스와치에 붙여 면적을 세서 main·sub 스와치 이름을 낸다.

**Tech Stack:** Python 3.13, Pillow, NumPy (rembg 는 사진 CLI 에서만, 선택)

**Spec:** `docs/superpowers/specs/2026-09-23-pet-template-design.md`

## Global Constraints

- 의존성은 `pillow`, `numpy` 만. `rembg` 는 사진 배경 제거용 선택 의존성(없으면 건너뜀). scikit-image 등 추가 금지 — Lab 변환은 직접 구현한다 (Kotlin 이식 대상).
- 생성형 모델 금지. 전부 결정론적 연산.
- hex 는 항상 소문자 `#rrggbb`.
- 역할은 `main`, `sub`, `keep` 세 가지뿐.
- 튜닝 상수: `SUB_RATIO = 0.2`, `CHROMA_KEEP = 0.3`, `MIN_FUR_L = 15`.
- 이식 대상 함수(`color_map`, `recolor_image`, `extract_colors`)는 Pillow 고유 알고리즘(양자화 등)에 기대지 않는다 — Kotlin 에서 같은 입력에 같은 결과가 나와야 한다.
- 배경 제거 실패·사진 없음은 "색 추출 실패" 와 같다 → `color_map(breed, None, None) == {}` → 원본색.
- 테스트는 저장소 관례대로 평범한 `test_*` 함수 + `__main__` 러너. 실행: `cd pet_template && python test_reference.py` (pytest 로도 돈다).
- 주석·문서는 한국어, 기존 `pixelart/reference.py` 문체(단계가 드러나게, 이유를 적는 주석)를 따른다.
- 사진 분석 실패가 가입 흐름을 막으면 안 된다 — 실패는 "원본색 그대로" 로 귀결.

## 파일 구조

| 파일 | 책임 |
|---|---|
| `pet_template/reference.py` | 색 공간, 에셋 읽기, 역할표, 재색칠, 털색 추출, CLI — 전부 한 파일 (이식 기준이라 한눈에 보여야 한다) |
| `pet_template/breeds.json` | 스와치 + 견종별 에셋 목록·역할표 (Task 2 에서 생성·검수) |
| `pet_template/test_reference.py` | 테스트 |
| `pet_template/README.md` | 사용법, 튜닝, 견종 추가 절차, 이식 주의 |
| `pet_template/requirements.txt` | pillow, numpy, rembg(선택) |
| `pet_template/samples/testdog.png` | `pixelart/samples/` 에서 이동 |
| `pet_template/assets/` | 이미 커밋됨 (`135220a`) |

---

### Task 1: 색 공간과 에셋 읽기

**Files:**
- Create: `pet_template/reference.py`
- Create: `pet_template/test_reference.py`

**Interfaces:**
- Produces: `hex_to_rgb8(h) -> tuple[int,int,int]`, `rgb8_to_hex(rgb) -> str`, `rgb_to_lab(rgb01) -> ndarray`, `lab_to_rgb(lab) -> ndarray(0~1)`, `hex_to_lab(h) -> ndarray(3)`, `lab_to_hex(lab) -> str`, `render_svg(text) -> Image(RGBA)`, `asset_frames(path) -> list[Image]`, `frame_colors(img) -> Counter[hex,int]`, 상수 `HERE`, `ASSETS`

- [ ] **Step 1: 실패하는 테스트 작성**

`pet_template/test_reference.py`:

```python
"""python test_reference.py — 재색칠 기준 구현 검사."""

from collections import Counter

from reference import ASSETS, asset_frames, frame_colors, hex_to_lab, lab_to_hex, render_svg


def test_lab_round_trip():
    for h in ("#000000", "#ffffff", "#ca895a", "#4a4755", "#e7e2c7"):
        assert lab_to_hex(hex_to_lab(h)) == h
    assert abs(hex_to_lab("#ffffff")[0] - 100) < 0.01


def test_render_svg_and_colors():
    svg = (
        "<svg version= '1.1'\n\twidth='3' height='2'\n\txmlns='http://www.w3.org/2000/svg'>\n"
        "<rect x='0.0' y='0.0' width='1.0' height='1.0' fill='#ca895a' />\n"
        "<rect x='2.0' y='1.0' width='1.0' height='1.0' fill='#181313' />\n</svg>"
    )
    img = render_svg(svg)
    assert img.size == (3, 2)
    assert img.getpixel((0, 0)) == (0xCA, 0x89, 0x5A, 255)
    assert img.getpixel((1, 0))[3] == 0
    assert frame_colors(img) == Counter({"#ca895a": 1, "#181313": 1})


def test_asset_frames_reads_real_assets():
    assert len(asset_frames(ASSETS / "golden" / "walk_right.gif")) == 6
    (front,) = asset_frames(ASSETS / "shiba" / "front.svg")
    assert front.size == (48, 48)
    assert sum(frame_colors(front).values()) == 321  # 시바 앞모습의 <rect> 수


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK")
```

- [ ] **Step 2: 실패 확인**

Run: `cd pet_template && python test_reference.py`
Expected: `ModuleNotFoundError: No module named 'reference'`

- [ ] **Step 3: 구현**

`pet_template/reference.py`:

```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `cd pet_template && python test_reference.py`
Expected: `OK`

- [ ] **Step 5: 커밋**

```bash
git add pet_template/reference.py pet_template/test_reference.py
git commit -m "feat(pet_template): Lab 변환과 SVG·GIF 에셋 읽기"
```

---

### Task 2: 역할표 — 초안 생성, 검수 시트, breeds.json, 커버리지 검사

**Files:**
- Modify: `pet_template/reference.py` (역할표·재색칠 적용·시트·CLI 추가)
- Create: `pet_template/breeds.json`
- Modify: `pet_template/test_reference.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Task 1 전부
- Produces: `ROLES`, `load_breeds(path=HERE/"breeds.json") -> dict`, `breed_colors(breed: dict) -> Counter`, `suggest_roles(counts: Counter) -> dict[hex, role]`, `recolor_image(img, cmap: dict) -> Image`, `contact_sheet(rows: list[list[Image]], scale=2, cell=72) -> Image`, `main()` (CLI: `--suggest-roles`, `--roles-sheet`)
- `breeds.json` 스키마: `{"swatches": {이름: hex}, "breeds": {견종: {"assets": {이름: "견종/파일"}, "roles": {hex: role}}}}`

- [ ] **Step 1: 실패하는 테스트 추가**

`test_reference.py` 의 import 를 바꾸고 테스트를 추가한다:

```python
import json
import tempfile
from collections import Counter
from pathlib import Path

from PIL import Image

from reference import (
    ASSETS,
    asset_frames,
    breed_colors,
    frame_colors,
    hex_to_lab,
    lab_to_hex,
    load_breeds,
    recolor_image,
    render_svg,
    suggest_roles,
)
```

```python
def test_suggest_roles_splits_fur_and_keeps_details():
    counts = Counter(
        {"#ca895a": 600, "#bd855c": 40, "#e7e2c7": 300, "#edebdb": 20, "#181313": 120, "#da94ad": 25}
    )
    assert suggest_roles(counts) == {
        "#bd855c": "main",
        "#ca895a": "main",
        "#e7e2c7": "sub",
        "#edebdb": "sub",
        "#181313": "keep",  # 어두움 — 외곽선·눈
        "#da94ad": "keep",  # 분홍 — 귀 안쪽
    }


def test_recolor_image_swaps_exact_pixels_only():
    img = Image.new("RGBA", (2, 1))
    img.putpixel((0, 0), (0xCA, 0x89, 0x5A, 255))
    img.putpixel((1, 0), (0x18, 0x13, 0x13, 255))
    out = recolor_image(img, {"#ca895a": "#6e4a32"})
    assert out.getpixel((0, 0)) == (0x6E, 0x4A, 0x32, 255)
    assert out.getpixel((1, 0)) == (0x18, 0x13, 0x13, 255)


def test_load_breeds_rejects_bad_role():
    bad = {
        "swatches": {"black": "#453d3e"},
        "breeds": {"shiba": {"assets": {"front": "shiba/front.svg"}, "roles": {"#ca895a": "outline"}}},
    }
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "breeds.json"
        path.write_text(json.dumps(bad))
        try:
            load_breeds(path)
        except ValueError as e:
            assert "잘못된 역할" in str(e)
        else:
            raise AssertionError("ValueError 가 나야 한다")


def test_breeds_json_covers_every_asset_color():
    """디자이너가 에셋을 바꾸면 여기서 잡힌다."""
    data = load_breeds()
    assert set(data["breeds"]) == {p.name for p in ASSETS.iterdir() if p.is_dir()}
    for name, breed in data["breeds"].items():
        on_disk = {
            p.relative_to(ASSETS).as_posix() for p in (ASSETS / name).iterdir() if p.suffix in (".svg", ".gif")
        }
        assert set(breed["assets"].values()) == on_disk, name
        colors, roles = set(breed_colors(breed)), set(breed["roles"])
        assert not colors - roles, f"{name}: 역할표에 없는 색 {sorted(colors - roles)}"
        assert not roles - colors, f"{name}: 에셋에 없는 색 {sorted(roles - colors)}"
```

- [ ] **Step 2: 실패 확인**

Run: `cd pet_template && python test_reference.py`
Expected: `ImportError: cannot import name 'breed_colors'`

- [ ] **Step 3: 구현**

`reference.py` 상단 import 를 바꾼다:

```python
import argparse
import json
import re
from collections import Counter
from pathlib import Path
```

`frame_colors` 아래에 추가:

```python
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
```

- [ ] **Step 4: 초안 생성**

Run: `cd pet_template && python reference.py --suggest-roles > breeds.json`
그다음 `test_suggest_roles_splits_fur_and_keeps_details`, `test_recolor_image_swaps_exact_pixels_only`, `test_load_breeds_rejects_bad_role`, `test_breeds_json_covers_every_asset_color` 가 통과하는지:
Run: `cd pet_template && python test_reference.py`
Expected: `OK` (초안은 에셋 색을 전부 덮으므로 커버리지 검사도 통과한다)

- [ ] **Step 5: 검수 시트 생성 및 수정**

Run: `cd pet_template && python reference.py --roles-sheet`
`roles_sheet.png` 를 열어 견종별로 확인한다:
- 빨강(main)이 주 털 전체를 덮는가, 파랑(sub)이 흰·크림 부분(코기·시바·허스키의 배·얼굴, 골든의 밝은 털)만 덮는가
- 눈·코·외곽선·귀 안쪽·혀는 원본색 그대로인가 (keep)
- 닥스훈트: 검은 털이 main, 탄색(눈썹·주둥이)이 sub, 눈 흰자(`#fcfcfc`, `#e4e6e9`)는 keep 이어야 한다 — 초안이 틀릴 가능성이 가장 큰 곳
틀린 hex 는 `breeds.json` 에서 역할을 직접 고치고 시트를 다시 만든다.

- [ ] **Step 6: 사용자 검수** — `roles_sheet.png` 를 사용자에게 보내고 확인을 받는다. 확인 전에는 다음 단계로 가지 않는다.

- [ ] **Step 7: 생성물 무시 설정**

`.gitignore` 끝의 pixelart 블록 아래에 추가 (pixelart 블록 삭제는 Task 5):

```
# 템플릿 확인 시트·결과 (눈 검수용 생성물)
pet_template/*_sheet.png
pet_template/samples/*_character.png
```

- [ ] **Step 8: 테스트 재확인 및 커밋**

Run: `cd pet_template && python test_reference.py`
Expected: `OK`

```bash
git add pet_template/reference.py pet_template/test_reference.py pet_template/breeds.json .gitignore
git commit -m "feat(pet_template): 견종 역할표 — 초안 생성, 검수 시트, 커버리지 검사"
```

---

### Task 3: 재색칠 치환표

**Files:**
- Modify: `pet_template/reference.py`
- Modify: `pet_template/test_reference.py`

**Interfaces:**
- Consumes: `load_breeds`, `breed_colors`, `hex_to_lab`, `lab_to_hex`, `recolor_image`, `contact_sheet`, `asset_frames`, `SWATCHES`
- Produces: `CHROMA_KEEP = 0.3`, `MIN_FUR_L = 15`, `color_map(breed: dict, main: str | None, sub: str | None) -> dict[hex, hex]` (main·sub 는 **hex**), `recolor_svg(text, cmap) -> str`, `swatch_sheet(data) -> Image`, CLI `--sheet`

- [ ] **Step 1: 실패하는 테스트 추가**

import 목록에 `MIN_FUR_L, color_map, recolor_svg` 를 추가하고:

```python
def _shiba_mains():
    shiba = load_breeds()["breeds"]["shiba"]
    counts = breed_colors(shiba)
    mains = [h for h, r in shiba["roles"].items() if r == "main"]
    return shiba, mains, max(mains, key=lambda h: counts[h])


def test_color_map_moves_base_exactly_and_keeps_shading():
    shiba, mains, base = _shiba_mains()
    cmap = color_map(shiba, "#6e4a32", None)
    assert cmap[base] == "#6e4a32"
    assert set(cmap) == set(mains)  # sub 목표가 없으면 sub 는 원본, keep 은 손대지 않는다
    by_light = sorted(mains, key=lambda h: hex_to_lab(h)[0])
    after = [hex_to_lab(cmap[h])[0] for h in by_light]
    assert all(a <= b + 0.5 for a, b in zip(after, after[1:])), "명암 순서가 뒤집혔다"


def test_extreme_targets_keep_every_shade():
    """검정·흰색은 밝기 여유가 없다. 음영 단계가 하나로 뭉개지거나 외곽선과 붙으면 안 된다."""
    for name, breed in load_breeds()["breeds"].items():
        mains = [h for h, r in breed["roles"].items() if r == "main"]
        for target in ("#453d3e", "#f4f2ee", "#000000"):
            cmap = color_map(breed, target, None)
            if target != "#000000":  # 순검정은 여유가 0 이라 뭉개지는 게 정상 — 하한만 본다
                assert len(set(cmap.values())) == len(mains), f"{name} {target}: 음영이 합쳐졌다"
            assert min(hex_to_lab(v)[0] for v in cmap.values()) >= MIN_FUR_L - 0.5, f"{name} {target}"


def test_no_target_keeps_original():
    shiba, _, _ = _shiba_mains()
    assert color_map(shiba, None, None) == {}


def test_recolor_svg_replaces_only_mapped():
    svg = "<rect x='0.0' y='0.0' width='1.0' height='1.0' fill='#ca895a' /><rect fill='#181313' />"
    out = recolor_svg(svg, {"#ca895a": "#6e4a32"})
    assert "fill='#6e4a32'" in out and "fill='#181313'" in out and "#ca895a" not in out
```

- [ ] **Step 2: 실패 확인**

Run: `cd pet_template && python test_reference.py`
Expected: `ImportError: cannot import name 'MIN_FUR_L'`

- [ ] **Step 3: 구현**

`recolor_image` 위에 추가:

```python
# ── 재색칠 ─────────────────────────────────────────────
CHROMA_KEEP = 0.3  # 색조 차를 얼마나 남길지. 1 이면 원본 색조 편차 그대로, 0 이면 단색
MIN_FUR_L = 15  # 털 밝기 하한. 외곽선(L≈3~8)과 붙지 않게 한다
SVG_FILL = re.compile(r"fill='(#[0-9a-fA-F]{6})'")


def color_map(breed: dict, main: str | None, sub: str | None) -> dict:
    """역할표 + 목표색(hex) → {원본 hex: 새 hex}.

    역할의 기준색(픽셀 수 최다)이 목표색이 되도록 역할 전체를 Lab 에서 옮긴다.
    색조 차는 CHROMA_KEEP 배로 줄이고, 밝기 차(명암)는 유지하되 [MIN_FUR_L, 100] 에
    들어가도록 어두운 쪽·밝은 쪽을 각각 비율로 줄인다. 잘라내면(클램프) 음영이 한 색으로 뭉개진다.
    목표가 None 인 역할은 원본을 유지한다 — 사진 분석이 실패해도 캐릭터는 나온다.
    """
    counts = breed_colors(breed)
    out = {}
    for role, target in (("main", main), ("sub", sub)):
        colors = [h for h, r in breed["roles"].items() if r == role]
        if target is None or not colors:
            continue
        base = hex_to_lab(max(colors, key=lambda h: counts[h]))
        goal = hex_to_lab(target)
        deltas = {h: hex_to_lab(h) - base for h in colors}
        darkest = min(d[0] for d in deltas.values())  # ≤ 0 (기준색 자신이 0)
        brightest = max(d[0] for d in deltas.values())  # ≥ 0
        squeeze_dark = min(1.0, max(0.0, goal[0] - MIN_FUR_L) / -darkest) if darkest < 0 else 1.0
        squeeze_bright = min(1.0, max(0.0, 100 - goal[0]) / brightest) if brightest > 0 else 1.0
        for h, d in deltas.items():
            dl = d[0] * (squeeze_dark if d[0] < 0 else squeeze_bright)
            out[h] = lab_to_hex(goal + np.array([dl, d[1] * CHROMA_KEEP, d[2] * CHROMA_KEEP]))
    return out


def recolor_svg(text: str, cmap: dict) -> str:
    """SVG 는 fill 문자열만 바꾸면 된다. 앱이 SVG 를 직접 그린다면 이쪽을 쓴다."""
    return SVG_FILL.sub(lambda m: f"fill='{cmap.get(m.group(1).lower(), m.group(1))}'", text)
```

`roles_sheet` 아래에 추가:

```python
def swatch_sheet(data: dict) -> Image.Image:
    """견종마다 한 줄: 원본 앞모습 + 스와치별 재색칠. 명암이 어색한 조합을 찾는 용도다."""
    rows = []
    for breed in data["breeds"].values():
        (front,) = asset_frames(ASSETS / breed["assets"]["front"])
        rows.append([front] + [recolor_image(front, color_map(breed, h, None)) for h in data["swatches"].values()])
    return contact_sheet(rows)
```

`main()` 에 인자와 분기를 추가:

```python
    parser.add_argument("--sheet", action="store_true", help="견종 × 스와치 확인 시트를 만든다")
```

```python
    elif args.sheet:
        out = HERE / "swatch_sheet.png"
        swatch_sheet(load_breeds()).save(out)
        print(f"스와치 시트 {out}")
```

- [ ] **Step 4: 통과 확인**

Run: `cd pet_template && python test_reference.py`
Expected: `OK`

- [ ] **Step 5: 눈 검수**

Run: `cd pet_template && python reference.py --sheet`
`swatch_sheet.png` 를 열어 확인하고 사용자에게 보낸다. 특히 볼 곳:
- 검은 닥스 → white·cream: 명암이 뭉개지거나 얼룩지지 않는가
- black: 털이 외곽선과 구분되고, 음영 단계가 눈에 보이는가 (압축 후 L 15~35 사이에 몰린다)
어색하면 `CHROMA_KEEP`, `MIN_FUR_L`, 스와치 값을 조정하고 결과를 커밋 메시지에 적는다.

- [ ] **Step 6: 커밋**

```bash
git add pet_template/reference.py pet_template/test_reference.py
git commit -m "feat(pet_template): 역할 기반 Lab 재색칠과 스와치 확인 시트"
```

---

### Task 4: 사진 털색 추출과 사진 CLI

**Files:**
- Modify: `pet_template/reference.py`
- Modify: `pet_template/test_reference.py`

**Interfaces:**
- Consumes: `hex_to_rgb8`, `hex_to_lab`, `rgb_to_lab`, `load_breeds`, `color_map`, `recolor_image`, `asset_frames`
- Produces: `SUB_RATIO = 0.2`, `extract_colors(img | None, swatches: dict[name, hex]) -> tuple[name | None, name | None]` (**스와치 이름**을 돌려준다 — 앱 UI 가 스와치를 선택 상태로 보여줘야 해서. `img` 가 None 이면 (None, None)), `load_upright(path)`, `remove_background(img) -> Image | None` (배경 제거를 못 하면 None), CLI `photo --breed NAME [--out PATH]`

- [ ] **Step 1: 실패하는 테스트 추가**

import 목록에 `extract_colors, hex_to_rgb8` 를 추가하고:

```python
def _photo(parts):
    """[(hex, 칸 수)] 를 가로로 잇고 오른쪽 끝 10칸은 투명으로 둔다 — 배경 제거 결과 흉내."""
    img = Image.new("RGBA", (sum(n for _, n in parts) + 10, 10), (0, 0, 0, 0))
    x = 0
    for h, n in parts:
        img.paste(Image.new("RGBA", (n, 10), hex_to_rgb8(h) + (255,)), (x, 0))
        x += n
    return img


def test_extract_single_color():
    sw = load_breeds()["swatches"]
    assert extract_colors(_photo([(sw["brown"], 100)]), sw) == ("brown", None)


def test_extract_two_tone():
    sw = load_breeds()["swatches"]
    assert extract_colors(_photo([(sw["white"], 70), (sw["brown"], 30)]), sw) == ("white", "brown")


def test_small_second_color_is_dropped():
    sw = load_breeds()["swatches"]
    assert extract_colors(_photo([(sw["white"], 90), (sw["brown"], 10)]), sw) == ("white", None)


def test_nothing_opaque_means_no_colors():
    sw = load_breeds()["swatches"]
    assert extract_colors(Image.new("RGBA", (10, 10), (0, 0, 0, 0)), sw) == (None, None)


def test_no_mask_means_no_colors():
    """배경 제거에 실패하면 배경 섞인 색을 뽑지 말고 원본색으로 간다."""
    assert extract_colors(None, load_breeds()["swatches"]) == (None, None)


def test_near_colors_snap_to_swatch():
    """조명에 조금 틀어진 색도 가장 가까운 스와치로 붙는다. FE 이식 결과를 맞출 기준 사례."""
    sw = load_breeds()["swatches"]
    assert extract_colors(_photo([("#6a4830", 60), ("#f0eee8", 40)]), sw) == ("brown", "white")
```

- [ ] **Step 2: 실패 확인**

Run: `cd pet_template && python test_reference.py`
Expected: `ImportError: cannot import name 'extract_colors'`

- [ ] **Step 3: 구현**

`reference.py` 상단 import 에 `ImageOps` 추가: `from PIL import Image, ImageDraw, ImageOps`

`# ── 재색칠 ──` 위에 추가 (`load_upright`, `remove_background` 는 `pixelart/reference.py` 에서 그대로 옮긴다):

```python
# ── 사진 → 털색 ────────────────────────────────────────
SUB_RATIO = 0.2  # 두 번째 색이 이 비율 이상이어야 sub 로 인정. 눈·코·혀가 sub 가 되지 않게 한다


def load_upright(path: Path) -> Image.Image:
    """폰 사진은 EXIF 회전 정보를 갖는다. 적용하지 않으면 마스크가 어긋난다."""
    return ImageOps.exif_transpose(Image.open(path)).convert("RGBA")


def remove_background(image: Image.Image) -> Image.Image | None:
    """배경을 지우고 RGBA 로 돌려준다. 앱에서는 ML Kit 이 담당한다.

    못 지우면 None. 배경 섞인 사진으로 색을 뽑으면 벽지 색 강아지가 나온다 — 원본색이 낫다.
    """
    try:
        from rembg import remove
    except ImportError:
        print("[알림] rembg 미설치 — 배경 제거 불가, 원본색으로 진행합니다 (pip install rembg)")
        return None
    return remove(image).convert("RGBA")


def extract_colors(img: Image.Image | None, swatches: dict) -> tuple:
    """배경을 지운 RGBA → (main 스와치 이름, sub 스와치 이름 또는 None).

    img 가 None(배경 제거 실패)이거나 불투명 픽셀이 없으면 (None, None) — 호출 측은 원본색으로 간다.
    불투명 픽셀 하나하나를 Lab 에서 가장 가까운 스와치에 붙이고 면적을 센다.
    양자화를 거치지 않는 건 Kotlin 에서 같은 결과를 내기 위해서다 (Pillow MEDIANCUT 은 재현이 어렵다).
    사진 색을 그대로 쓰지 않고 스와치에 붙이는 건, 조명에 탁해진 색을 피하고
    사용자가 바꿀 선택지를 주기 위해서다.
    """
    if img is None:
        return None, None
    img = img.convert("RGBA")
    img.thumbnail((256, 256))  # 폰 사진 원본은 너무 크다. 색 비율에는 영향이 없다
    arr = np.array(img)
    fur = arr[arr[..., 3] > 128][:, :3]
    if len(fur) == 0:
        return None, None

    names = list(swatches)
    swatch_labs = np.array([hex_to_lab(swatches[n]) for n in names])
    labs = rgb_to_lab(fur / 255)
    nearest = np.argmin(np.linalg.norm(labs[:, None, :] - swatch_labs[None, :, :], axis=2), axis=1)
    area = Counter({names[i]: int(n) for i, n in zip(*np.unique(nearest, return_counts=True))})

    (main, _), *rest = area.most_common()
    sub = rest[0][0] if rest and rest[0][1] / len(fur) >= SUB_RATIO else None
    return main, sub
```

`main()` 을 사진 처리까지 받도록 바꾼다. 인자 추가:

```python
    parser.add_argument("photo", type=Path, nargs="?", help="반려동물 사진")
    parser.add_argument("--breed", help="견종 (breeds.json 의 키)")
    parser.add_argument("--out", type=Path, default=None)
```

`if args.suggest_roles:` 앞에 분기 추가:

```python
    if args.photo:
        data = load_breeds()
        if args.breed not in data["breeds"]:
            parser.error(f"--breed 는 {', '.join(data['breeds'])} 중 하나")
        breed = data["breeds"][args.breed]
        main_name, sub_name = extract_colors(remove_background(load_upright(args.photo)), data["swatches"])
        cmap = color_map(breed, data["swatches"].get(main_name), data["swatches"].get(sub_name))
        (front,) = asset_frames(ASSETS / breed["assets"]["front"])
        sprite = recolor_image(front, cmap)
        out = args.out or args.photo.with_name(f"{args.photo.stem}_character.png")
        sprite.resize((sprite.width * 8, sprite.height * 8), Image.NEAREST).save(out)
        print(f"털색 main={main_name} sub={sub_name}")
        print(f"캐릭터 {out}")
        return
```

(`data["swatches"].get(None)` 은 None 이라 배경 제거·추출 실패 시 원본색이 된다.)

- [ ] **Step 4: 통과 확인**

Run: `cd pet_template && python test_reference.py`
Expected: `OK`

- [ ] **Step 5: 샘플 동작 확인 (실사진 검증 아님)**

`pixelart/samples/testdog.png` 를 옮긴다:

```bash
mkdir -p pet_template/samples && git mv pixelart/samples/testdog.png pet_template/samples/testdog.png
```

Run: `cd pet_template && python reference.py samples/testdog.png --breed golden`
Expected: `털색 main=... sub=...` 와 `samples/testdog_character.png`. `testdog.png` 는 **합성 도형**이다 — CLI 경로가 끝까지 도는지만 확인한다. rembg 가 없으면 `[알림]` 과 함께 `main=None sub=None`, 원본색 캐릭터가 나와야 한다. 결과를 사용자에게 보내고, 실사진 털색 추출은 README 검증 상태에 **미검증**으로 남긴다.

- [ ] **Step 6: 커밋**

```bash
git add pet_template/reference.py pet_template/test_reference.py pet_template/samples/testdog.png
git commit -m "feat(pet_template): 사진 털색 추출과 사진 → 캐릭터 CLI"
```

---

### Task 5: pixelart 제거와 문서 정리

**Files:**
- Delete: `pixelart/` (남은 파일 전부)
- Create: `pet_template/README.md`, `pet_template/requirements.txt`
- Modify: `README.md`, `pet_validation/README.md`, `experiments/pet_analysis_vlm/README.md`, `LICENSING.md`, `.gitignore`

- [ ] **Step 1: pixelart 삭제**

```bash
git rm -r pixelart
```

`git grep -n pixelart` 로 남은 참조를 확인한다. 아래 단계에서 전부 없어져야 한다 (spec·plan 문서 안의 언급은 제외).

- [ ] **Step 2: `pet_template/requirements.txt`**

```
pillow
numpy
# 사진 배경 제거 프로토타입용. 앱에서는 ML Kit Subject Segmentation 이 이 역할을 한다.
rembg
```

- [ ] **Step 3: `pet_template/README.md`**

````markdown
# 견종 템플릿 재색칠

반려동물 사진에서 털색을 뽑아, 사용자가 고른 견종 픽셀 템플릿을 그 색으로 다시 칠한다.
사진을 픽셀화하던 `pixelart/` 를 대체했다.

## 이 디렉터리의 목적

`reference.py` 는 **Kotlin 이식용 기준 구현**이다. 파라미터를 여기서 튜닝해 확정한 뒤
같은 알고리즘을 앱의 `Bitmap` 연산으로 옮긴다.

## 파이프라인

```
사진 → 배경 제거 (앱: ML Kit Subject Segmentation / 여기: rembg)
     → 픽셀마다 가까운 스와치로 → 면적 순   main·sub 털색 (스와치 이름)
견종(사용자 선택) + main·sub → 색 치환표 {원본 hex: 새 hex}
     → 에셋 프레임 픽셀 치환              캐릭터
```

**생성형 모델은 쓰지 않는다.** 전부 결정론적 연산이라 온디바이스에서 즉시 돌고 같은 입력에 같은 결과가 나온다.
견종 분류기도 없다. 견종은 사용자가 고르므로 오답이 없다.

**사진이 없거나 배경 제거·털색 추출이 실패하면** `color_map(breed, None, None)` 이 빈 표를 돌려주고
견종 템플릿 원본색이 그대로 나온다. 가입 흐름을 막지 않는다.

## 에셋과 역할표

- `assets/<견종>/` — 디자인 드라이브 `peTox_픽셀` 의 파일. 앞·뒤·오·왼 SVG + 견종에 따라 걷기·짖기 GIF.
- `breeds.json` — 스와치, 견종별 에셋 목록, **역할표**(hex → `main`/`sub`/`keep`).
  - `main` 주 털색 계열, `sub` 보조 털색 계열(흰 배·크림 얼굴 등), `keep` 외곽선·눈·코·귀 안쪽·혀
  - 역할의 기준색은 그 역할에서 픽셀 수가 가장 많은 색이다

## 사용

```
python reference.py samples/testdog.png --breed golden   # 사진 → 캐릭터 (8배 확대 PNG)
python reference.py --sheet                              # 견종 × 스와치 확인 시트
python reference.py --roles-sheet                        # 역할표 검수 시트
python reference.py --suggest-roles                      # breeds.json 초안 출력
python test_reference.py
```

## 견종 추가·에셋 교체 절차

1. 드라이브 파일을 `assets/<견종>/` 에 영문 이름으로 넣는다 (앞/뒤/오/왼 → front/back/right/left, 오걷/왼걷 → walk_right/walk_left)
2. `python reference.py --suggest-roles` 로 해당 견종 초안을 뽑아 `breeds.json` 에 합친다
3. `python reference.py --roles-sheet` 로 검수 — 빨강=main, 파랑=sub 가 맞게 칠해졌는지, 눈·외곽선이 원본인지
4. `python test_reference.py` — 에셋 색이 역할표에 빠짐없이 있는지 검사한다

에셋만 바뀌어도 4번이 실패한다. 새 색만 역할표에 추가하면 된다.

## 튜닝 포인트

| 상수 | 영향 |
|---|---|
| `SWATCHES` | 사용자가 고르는 털색. 사진 색은 가장 가까운 스와치로 붙는다 |
| `SUB_RATIO` (0.2) | 두 번째 색이 이 비율 이상이면 sub. 낮추면 눈·혀가 sub 로 잡힌다 |
| `CHROMA_KEEP` (0.3) | 명암 단계의 색조 편차를 얼마나 남길지. 높이면 원본 느낌, 낮추면 단색에 가깝다 |
| `MIN_FUR_L` (15) | 털 밝기 하한. 검은 털이 외곽선과 붙지 않게 한다. 음영은 잘라내지 않고 비율로 압축한다 |

## 검증 상태

| 항목 | 상태 |
|---|---|
| 역할표 커버리지 (5견종 전 에셋) | ✅ 테스트 |
| 재색칠 명암 순서·음영 단계 유지·밝기 하한 | ✅ 테스트 |
| 스와치 시트 눈 검수 | 커밋 시점 기록 참고 |
| **실제 반려동물 사진 털색 추출** | ❌ **미검증** — 합성 이미지로만 확인 (`samples/testdog.png` 도 합성 도형) |
| ML Kit 마스크와의 차이 | ❌ 미검증 |

### 알려진 한계

- 흰 털이 그림자 때문에 gray 로 잡힐 수 있다. 실사진으로 스와치 값을 조정하라.
- 원본 털색과 목표색이 멀면(검은 닥스 → 흰색) 명암이 어색할 수 있다. 스와치 시트로 확인하라.
- 외곽선과 눈이 같은 hex 를 쓰는 에셋이 있어, 외곽선만 따로 바꾸는 처리는 할 수 없다.

## 이식 시 주의

- 앱에서 옮길 것은 `extract_colors`(털색), `color_map`(Lab 변환 포함), `recolor_image`(픽셀 치환) 셋이다. SVG 를 직접 그린다면 `recolor_svg`
- `extract_colors` 는 양자화 없이 픽셀별 최근접 스와치라 Kotlin 에서도 같은 값이 나온다. `test_reference.py` 의 합성 사례(`test_extract_*`, `test_near_colors_snap_to_swatch`)를 FE 테스트로 그대로 옮겨 결과를 맞춰라
- 역할표·스와치는 `breeds.json` 을 그대로 앱 에셋으로 넣는다. 코드에 옮겨 적지 마라
- 치환표는 견종·색 조합당 한 번 계산해 캐시하면 된다. 프레임마다 다시 만들 필요가 없다
- rembg(U2-Net)와 ML Kit 마스크는 다르다. 최종 확인은 실기기에서 하라
````

- [ ] **Step 4: 루트 `README.md`**

아키텍처 그림에서

```
 │                → 픽셀화                     색은 원본 사진에서 그대로
```

를

```
 │                → 털색 추출 + 견종 템플릿 재색칠   견종은 사용자 선택, 색은 사진에서
```

로, 구성표에서

```
| `pixelart/` | 반려동물 사진 → 픽셀 캐릭터 변환 | FE (Kotlin 이식) |
```

를

```
| `pet_template/` | 반려동물 사진 → 견종 템플릿 재색칠 | FE (Kotlin 이식) |
```

로, 현재 상태 표에서

```
| 픽셀화 파이프라인 | 미검증 |
```

를

```
| 템플릿 재색칠 (실사진 털색 추출) | 미검증 |
```

로 바꾼다.

- [ ] **Step 5: `pet_validation/README.md`**

- `예   → 통과, 픽셀화로 진행` → `예   → 통과, 템플릿 재색칠로 진행`
- `애매하면 통과시키고, 픽셀화 결과가 이상하면` → `애매하면 통과시키고, 재색칠 결과가 이상하면`
- 「왜 분류기를 학습하지 않는가」의 두 항목

```
- 캐릭터 색은 **사진에서 직접 나온다** — `../pixelart/` 가 원본 색을 그대로 픽셀화하므로
  털색을 따로 판별할 이유가 없다
- 품종은 캐릭터 생성에 쓰이지 않는다
```

을

```
- 캐릭터 색은 **사진에서 규칙으로 뽑는다** — `../pet_template/` 이 털색을 스와치에 붙여
  견종 템플릿을 재색칠한다. 학습이 필요 없다
- 견종은 **사용자가 고른다** — 템플릿이 5종뿐이라 분류기를 둘 이유가 없고, 오답도 없다
```

로 바꾼다.

- [ ] **Step 6: `experiments/pet_analysis_vlm/README.md`**

- `픽셀 캐릭터 변환은 `../pixelart/` 담당이고,` → `캐릭터 생성은 `../../pet_template/` 담당이고,`
- `- 털색은 `../pixelart/` 의 팔레트 양자화 결과를 재활용하면 된다` → `- 털색은 `../../pet_template/` 의 털색 추출(`extract_colors`)을 재활용하면 된다`

- [ ] **Step 7: `LICENSING.md`**

제품 경로 표 마지막 행(`반려동물 분류 학습 데이터`) 아래에 추가:

```
| 견종 템플릿 에셋 | 팀 제작 (디자인) | ✅ | 2026-09-24 | `pet_template/assets/` — 드라이브 `peTox_픽셀` |
```

제품 경로 밖 표에서

```
| rembg / U2-Net | MIT / Apache 2.0 | `pixelart/` 프로토타입 |
```

를

```
| rembg / U2-Net | MIT / Apache 2.0 | `pet_template/` 파라미터 튜닝 |
```

로 바꾼다.

- [ ] **Step 8: `.gitignore`**

pixelart 블록 네 줄을 지운다:

```
# 픽셀화 생성물 (입력 테스트 이미지는 커밋한다)
pixelart/samples/*_pixel.png
pixelart/samples/*_preview.png
pixelart/samples/dog_32px_8c*.png
```

- [ ] **Step 9: 확인**

Run: `git grep -n pixelart -- ':!docs/superpowers'`
Expected: 출력 없음

Run: `cd pet_template && python test_reference.py`
Expected: `OK`

- [ ] **Step 10: 커밋**

```bash
git add -A pixelart pet_template README.md pet_validation/README.md experiments/pet_analysis_vlm/README.md LICENSING.md .gitignore
git commit -m "refactor: pixelart 를 pet_template 으로 대체 — 문서 정리"
```
