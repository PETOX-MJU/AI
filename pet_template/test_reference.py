"""python test_reference.py — 재색칠 기준 구현 검사."""

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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK")
