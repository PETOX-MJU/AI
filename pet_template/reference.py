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
from PIL import Image, ImageDraw, ImageOps

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


# ── 사진 → 털색 ────────────────────────────────────────
SUB_RATIO = 0.2  # 두 번째 색이 이 비율 이상이어야 sub 로 인정. 눈·코·혀가 sub 가 되지 않게 한다


def load_upright(path: Path) -> Image.Image | None:
    """폰 사진은 EXIF 회전 정보를 갖는다. 적용하지 않으면 마스크가 어긋난다.

    파일이 없거나 이미지가 아니면 None — 원본색으로 진행한다. 가입 흐름을 막지 않는다.
    """
    try:
        return ImageOps.exif_transpose(Image.open(path)).convert("RGBA")
    except OSError as e:  # FileNotFoundError, 손상 파일(UnidentifiedImageError) 모두 OSError
        print(f"[알림] 사진을 읽지 못함({e}) — 원본색으로 진행합니다")
        return None


def remove_background(image: Image.Image | None) -> Image.Image | None:
    """배경을 지우고 RGBA 로 돌려준다. 앱에서는 ML Kit 이 담당한다.

    못 지우면 None. 배경 섞인 사진으로 색을 뽑으면 벽지 색 강아지가 나온다 — 원본색이 낫다.
    사진을 못 읽었으면(None) 그대로 None.
    """
    if image is None:
        return None
    try:
        from rembg import remove
    except ImportError:
        print("[알림] rembg 미설치 — 배경 제거 불가, 원본색으로 진행합니다 (pip install rembg)")
        return None
    try:
        return remove(image).convert("RGBA")
    except Exception as e:  # 모델 로드 실패 등 rembg 내부 오류도 원본색으로 진행한다
        print(f"[알림] 배경 제거 실패({e}) — 원본색으로 진행합니다")
        return None


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
    # 축소 대신 일정 간격으로 픽셀을 건너뛴다(stride). 리샘플링이 없어 원본 픽셀 값
    # 그대로 쓰므로 경계 색이 섞이지 않고, Kotlin 에서도 같은 결과를 내기 쉽다
    s = max(1, max(img.size) // 256)
    arr = np.array(img)[::s, ::s]
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


def fit_to_template(breed: dict, main: str | None, sub: str | None) -> tuple:
    """사진에서 뽑은 (main hex, sub hex) 를 견종 템플릿의 밝기 순서에 맞춘다.

    예: 허스키는 main(회색)이 sub(흰색)보다 어둡다. 그런데 흰 개 사진은 몸의 대부분이
    흰색이라 main(면적 최다) 이 오히려 더 밝게 나온다 — 그대로 color_map 에 넘기면
    캐릭터가 명암 반전된다. 역할의 기준색(픽셀 수 최다, color_map 과 같은 규칙) 끼리의
    밝기(L) 순서와 사진 두 색의 밝기 순서를 비교해, 서로 다르면 맞바꾼다.
    sub 가 없거나(단색 견종) 사진에 main·sub 중 하나가 없으면 그대로 둔다 — 순서를 셋 중
    하나만 있을 때 비교할 대상이 없다. 사용자가 스와치를 직접 고른 경우에는 쓰지 않는다
    (color_map 안에 넣지 않는 이유) — 사용자 선택을 뒤집으면 안 된다.
    """
    if main is None or sub is None:
        return main, sub
    role_colors = {r: [h for h, rr in breed["roles"].items() if rr == r] for r in ("main", "sub")}
    if not role_colors["main"] or not role_colors["sub"]:
        return main, sub
    counts = breed_colors(breed)
    base_main_l = hex_to_lab(max(role_colors["main"], key=lambda h: counts[h]))[0]
    base_sub_l = hex_to_lab(max(role_colors["sub"], key=lambda h: counts[h]))[0]
    photo_main_l, photo_sub_l = hex_to_lab(main)[0], hex_to_lab(sub)[0]
    if (base_main_l - base_sub_l) * (photo_main_l - photo_sub_l) < 0:
        return sub, main
    return main, sub


# ── 재색칠 ─────────────────────────────────────────────
CHROMA_KEEP = 0.3  # 색조 차를 얼마나 남길지. 1 이면 원본 색조 편차 그대로, 0 이면 단색
MIN_FUR_L = 15  # 털 밝기 하한. 외곽선(L≈3~8)과 붙지 않게 한다
SVG_FILL = re.compile(r"fill='(#[0-9a-fA-F]{6})'")


def color_map(breed: dict, main: str | None, sub: str | None) -> dict:
    """역할표 + 목표색(hex) → {원본 hex: 새 hex}.

    역할의 기준색(픽셀 수 최다)이 목표색이 되도록 역할 전체를 Lab 에서 옮긴다.
    색조 차는 CHROMA_KEEP 배, 그리고 목표가 기준색보다 덜 선명하면 그 비율만큼 더 줄여서
    남긴다(무채색 목표에 원본 색조 편차를 그대로 더하면 반대 색조(파랑)로 넘어간다).
    밝기 차(명암)는 유지하되 [MIN_FUR_L, 100] 에 들어가도록 어두운 쪽·밝은 쪽을 각각
    비율로 줄인다. 잘라내면(클램프) 음영이 한 색으로 뭉개진다.
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
        goal[0] = max(goal[0], MIN_FUR_L)  # 목표색이 하한보다 어두워도 결과 L 은 [MIN_FUR_L, 100] 에 든다
        base_chroma = float(np.hypot(base[1], base[2]))
        goal_chroma = float(np.hypot(goal[1], goal[2]))
        chroma_keep = CHROMA_KEEP if base_chroma == 0 else CHROMA_KEEP * min(1.0, goal_chroma / base_chroma)
        deltas = {h: hex_to_lab(h) - base for h in colors}
        darkest = min(d[0] for d in deltas.values())  # ≤ 0 (기준색 자신이 0)
        brightest = max(d[0] for d in deltas.values())  # ≥ 0
        squeeze_dark = min(1.0, max(0.0, goal[0] - MIN_FUR_L) / -darkest) if darkest < 0 else 1.0
        squeeze_bright = min(1.0, max(0.0, 100 - goal[0]) / brightest) if brightest > 0 else 1.0
        for h, d in deltas.items():
            dl = d[0] * (squeeze_dark if d[0] < 0 else squeeze_bright)
            out[h] = lab_to_hex(goal + np.array([dl, d[1] * chroma_keep, d[2] * chroma_keep]))
    return out


def recolor_svg(text: str, cmap: dict) -> str:
    """SVG 는 fill 문자열만 바꾸면 된다. 앱이 SVG 를 직접 그린다면 이쪽을 쓴다."""
    return SVG_FILL.sub(lambda m: f"fill='{cmap.get(m.group(1).lower(), m.group(1))}'", text)


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


def swatch_sheet(data: dict) -> Image.Image:
    """견종마다 한 줄: 원본 앞모습 + 스와치별 재색칠. 명암이 어색한 조합을 찾는 용도다."""
    rows = []
    for breed in data["breeds"].values():
        (front,) = asset_frames(ASSETS / breed["assets"]["front"])
        rows.append([front] + [recolor_image(front, color_map(breed, h, None)) for h in data["swatches"].values()])
    return contact_sheet(rows)


def draft_breeds() -> dict:
    """assets/ 를 훑어 breeds.json 초안을 만든다. 새 견종을 추가할 때 쓴다.

    스와치는 기존 breeds.json 이 있으면 그대로 가져온다 — 스와치는 breeds.json 이
    유일한 출처이고(코드 상수로 중복 관리하지 않는다), 초안에도 같은 스와치가 필요하다.
    """
    breeds_path = HERE / "breeds.json"
    swatches = json.loads(breeds_path.read_text())["swatches"] if breeds_path.is_file() else {}
    breeds = {}
    for folder in sorted(p for p in ASSETS.iterdir() if p.is_dir()):
        files = sorted(p for p in folder.iterdir() if p.suffix in (".svg", ".gif"))
        breed = {"assets": {p.stem: f"{folder.name}/{p.name}" for p in files}}
        breed["roles"] = suggest_roles(breed_colors(breed))
        breeds[folder.name] = breed
    return {"swatches": swatches, "breeds": breeds}


def make_character(breed: dict, photo: Path | None, swatches: dict) -> tuple:
    """사진(없어도 됨) → (앞모습 캐릭터, main 스와치 이름, sub 스와치 이름).

    사진이 없거나 읽기·배경 제거·추출 중 하나라도 실패하면 이름은 (None, None) 이고
    견종 템플릿 원본색이 나온다.
    """
    main_name, sub_name = (None, None)
    if photo is not None:
        main_name, sub_name = extract_colors(remove_background(load_upright(photo)), swatches)
    main_hex, sub_hex = fit_to_template(breed, swatches.get(main_name), swatches.get(sub_name))
    hex_to_name = {v: k for k, v in swatches.items()}
    (front,) = asset_frames(ASSETS / breed["assets"]["front"])
    sprite = recolor_image(front, color_map(breed, main_hex, sub_hex))
    return sprite, hex_to_name.get(main_hex), hex_to_name.get(sub_hex)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("photo", type=Path, nargs="?", help="반려동물 사진 (없으면 원본색)")
    parser.add_argument("--breed", help="견종 (breeds.json 의 키). 사진 없이 주면 원본색 캐릭터")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--suggest-roles", action="store_true", help="breeds.json 초안을 출력한다")
    parser.add_argument("--roles-sheet", action="store_true", help="역할표 검수 시트를 만든다")
    parser.add_argument("--sheet", action="store_true", help="견종 × 스와치 확인 시트를 만든다")
    args = parser.parse_args()

    if args.photo or args.breed:
        data = load_breeds()
        if args.breed not in data["breeds"]:
            parser.error(f"--breed 는 {', '.join(data['breeds'])} 중 하나")
        sprite, main_name, sub_name = make_character(data["breeds"][args.breed], args.photo, data["swatches"])
        default = args.photo.with_name(f"{args.photo.stem}_character.png") if args.photo else HERE / "samples" / f"{args.breed}_character.png"
        out = args.out or default
        sprite.resize((sprite.width * 8, sprite.height * 8), Image.NEAREST).save(out)
        print(f"털색 main={main_name} sub={sub_name}")
        print(f"캐릭터 {out}")
        return
    elif args.suggest_roles:
        print(json.dumps(draft_breeds(), ensure_ascii=False, indent=2))
    elif args.roles_sheet:
        out = HERE / "roles_sheet.png"
        roles_sheet(load_breeds()).save(out)
        print(f"역할 검수 시트 {out}")
    elif args.sheet:
        out = HERE / "swatch_sheet.png"
        swatch_sheet(load_breeds()).save(out)
        print(f"스와치 시트 {out}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
