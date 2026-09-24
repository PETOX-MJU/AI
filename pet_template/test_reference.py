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
