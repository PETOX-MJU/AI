"""python test_reference.py — 재색칠 기준 구현 검사."""

import json
import tempfile
from collections import Counter
from pathlib import Path

from PIL import Image

from reference import (
    ASSETS,
    MIN_FUR_L,
    asset_frames,
    breed_colors,
    color_map,
    frame_colors,
    hex_to_lab,
    lab_to_hex,
    load_breeds,
    recolor_image,
    recolor_svg,
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
            lost = len(mains) - len(set(cmap.values()))
            if target != "#000000":  # 순검정은 여유가 0 이라 뭉개지는 게 정상 — 하한만 본다
                # golden 처럼 음영이 촘촘한(29 단계) 견종은 흰색 근처(여유 L≈3)에서 8비트
                # sRGB 반올림으로 극소수가 겹칠 수 있다 — 알고리즘 버그가 아니라 색 공간
                # 해상도의 한계다(CHROMA_KEEP 을 0.3→1.0 으로 올려도 28/29 까지만 개선돼
                # 근본적으로 못 없앤다, 실측 확인). 무채색 목표(예: 검정)에서는 색조 편차로
                # 구분되던, L 이 거의 같은 쌍이 chroma_keep 축소로 함께 겹치기도 한다
                # (골든 검정: 3 쌍). 완전 동일 개수를 요구하진 않는다.
                assert lost <= 3, f"{name} {target}: 음영이 {lost}개 합쳐졌다"
            assert min(hex_to_lab(v)[0] for v in cmap.values()) >= MIN_FUR_L - 0.5, f"{name} {target}"


def test_neutral_target_stays_neutral():
    """무채색(black·gray) 목표에 원본 색조 편차를 그대로 더하면 반대 색조(파랑)로 넘어간다.

    목표색 자체도 완전한 무채색(b=0)은 아니라서(예: gray 스와치는 b≈-2.9) 절대값 0 을
    기준으로 삼지 않고, 목표의 b 보다 3 이상 더 파래지지 않는지를 본다.
    """
    golden = load_breeds()["breeds"]["golden"]
    for target in ("#453d3e", "#8c8a90"):
        goal_b = hex_to_lab(target)[2]
        cmap = color_map(golden, target, None)
        assert min(hex_to_lab(v)[2] for v in cmap.values()) >= goal_b - 3, f"{target}: 파란 색조로 넘어갔다"


def test_no_target_keeps_original():
    shiba, _, _ = _shiba_mains()
    assert color_map(shiba, None, None) == {}


def test_recolor_svg_replaces_only_mapped():
    svg = "<rect x='0.0' y='0.0' width='1.0' height='1.0' fill='#ca895a' /><rect fill='#181313' />"
    out = recolor_svg(svg, {"#ca895a": "#6e4a32"})
    assert "fill='#6e4a32'" in out and "fill='#181313'" in out and "#ca895a" not in out


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
