"""FE 앱(Kotlin) 이식용 데이터와 대조 사례. reference.py 가 정본이다.

    python export_palette.py     # build/pet_palette.json, build/pet_cases.json

- pet_palette.json → FE android/app/src/main/assets/ 에 복사. 앱이 런타임에 읽는 전부다.
  역할별 기준색(픽셀 수 최다)은 AI 에셋 전체로 세야 해서 여기서 미리 계산해 넘긴다.
  FE PNG 는 에셋 일부라 앱에서 다시 세면 기준색이 달라질 수 있다.
- pet_cases.json → FE android/app/src/test/resources/ 에 복사. Kotlin 이 Python 과 같은 값을 내는지 본다.
"""

import base64
import json
import random
import zlib
from pathlib import Path

from PIL import Image, ImageDraw

import reference as R

HERE = Path(__file__).resolve().parent
OUT = HERE / "build"


def palette(data: dict) -> dict:
    breeds = {}
    for name, breed in data["breeds"].items():
        counts = R.breed_colors(breed)
        roles = {h.lower(): r for h, r in breed["roles"].items()}
        base = {}
        for role in ("main", "sub"):
            colors = [h for h, r in breed["roles"].items() if r == role]
            base[role] = max(colors, key=lambda h: counts[h]).lower() if colors else None
        breeds[name] = {"roles": roles, "base": base}
    return {
        "swatches": {k: v.lower() for k, v in data["swatches"].items()},
        "subRatio": R.SUB_RATIO,
        "chromaKeep": R.CHROMA_KEEP,
        "minFurL": R.MIN_FUR_L,
        "breeds": breeds,
    }


def synthetic(rng: random.Random, w: int, h: int, swatches: dict) -> Image.Image:
    """투명 배경 위 털색 덩어리 몇 개 + 반투명 가장자리. 실제 사진 대신 쓰는 결정적 입력."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    hexes = list(swatches.values())
    for _ in range(rng.randint(2, 5)):
        x0, y0 = rng.randrange(w), rng.randrange(h)
        x1, y1 = rng.randint(x0, w), rng.randint(y0, h)
        r, g, b = R.hex_to_rgb8(rng.choice(hexes))
        jitter = lambda v: max(0, min(255, v + rng.randint(-40, 40)))  # 조명 차이
        draw.ellipse((x0, y0, x1, y1), fill=(jitter(r), jitter(g), jitter(b), rng.choice([255, 255, 200, 90])))
    return img


def rgba_b64(img: Image.Image) -> dict:
    """RGBA 원시 바이트를 zlib 으로 압축해 base64. 안드로이드 단위 테스트는 javax.imageio(PNG)를 못 쓴다."""
    return {"w": img.width, "h": img.height, "rgba": base64.b64encode(zlib.compress(img.convert("RGBA").tobytes(), 9)).decode()}


def cases(data: dict) -> dict:
    sw = data["swatches"]
    rng = random.Random(20260929)
    labs = [{"hex": h, "lab": R.hex_to_lab(h).tolist()} for h in ["#000000", "#ffffff", "#808080", *sw.values()]]
    roundtrip = [{"lab": lab, "hex": R.lab_to_hex(lab)} for lab in
                 ([rng.uniform(0, 100), rng.uniform(-80, 80), rng.uniform(-80, 80)] for _ in range(300))]

    maps = []
    options = [None, *sw]
    for name, breed in data["breeds"].items():
        for main in options:
            for sub in options:
                fm, fs = R.fit_to_template(breed, sw.get(main), sw.get(sub))
                maps.append({"breed": name, "main": sw.get(main), "sub": sw.get(sub),
                             "fitMain": fm, "fitSub": fs, "map": R.color_map(breed, fm, fs)})

    extract = []
    for w, h in [(30, 40), (64, 48), (257, 180), (600, 300), (1030, 770)]:
        for _ in range(4):
            img = synthetic(rng, w, h, sw)
            main, sub = R.extract_colors(img, sw)
            extract.append({**rgba_b64(img), "main": main, "sub": sub})
    extract.append({**rgba_b64(Image.new("RGBA", (20, 20), (0, 0, 0, 0))), "main": None, "sub": None})
    return {"labs": labs, "roundtrip": roundtrip, "maps": maps, "extract": extract}


def main() -> None:
    data = R.load_breeds()
    OUT.mkdir(exist_ok=True)
    (OUT / "pet_palette.json").write_text(json.dumps(palette(data), ensure_ascii=False, indent=1))
    c = cases(data)
    (OUT / "pet_cases.json").write_text(json.dumps(c, ensure_ascii=False))
    subs = sum(e["sub"] is not None for e in c["extract"])
    print(f"palette {len(data['breeds'])} breeds; cases: maps {len(c['maps'])}, extract {len(c['extract'])} (sub 있음 {subs})")
    assert 0 < subs < len(c["extract"]) - 1, "sub 가 있는 사례와 없는 사례가 둘 다 있어야 대조가 의미 있다"


if __name__ == "__main__":
    main()
