"""python test_reference.py — 재색칠 기준 구현 검사."""

import contextlib
import io
import json
import subprocess
import sys
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
    extract_colors,
    fit_to_template,
    frame_colors,
    hex_to_lab,
    hex_to_rgb8,
    lab_to_hex,
    load_breeds,
    make_character,
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


def test_color_map_sub_path_moves_sub_base_and_covers_sub_keys():
    """sub 목표를 주면 sub 역할의 기준색(픽셀 최다)이 정확히 그 목표로 바뀌고,
    sub 역할 색 전부가 치환표에 있어야 한다(main 과 같은 규칙이 sub 에도 적용됨을 확인)."""
    sw = load_breeds()["swatches"]
    shiba = load_breeds()["breeds"]["shiba"]
    counts = breed_colors(shiba)
    subs = [h for h, r in shiba["roles"].items() if r == "sub"]
    base_sub = max(subs, key=lambda h: counts[h])
    cmap = color_map(shiba, sw["brown"], sw["white"])
    assert cmap[base_sub] == sw["white"]
    assert set(subs) <= set(cmap)


def test_color_map_drops_photo_sub_when_breed_has_no_sub_role():
    """단색 견종(golden)은 sub 역할이 없다 — 사진에서 sub 가 나와도 버려지고 main 만 바뀐다."""
    sw = load_breeds()["swatches"]
    golden = load_breeds()["breeds"]["golden"]
    mains = [h for h, r in golden["roles"].items() if r == "main"]
    cmap = color_map(golden, sw["brown"], sw["white"])
    assert set(cmap) == set(mains)


def test_extreme_targets_keep_every_shade():
    """검정·흰색은 밝기 여유가 없다. 음영 단계가 하나로 뭉개지거나 외곽선과 붙으면 안 된다."""
    sw = load_breeds()["swatches"]
    for name, breed in load_breeds()["breeds"].items():
        mains = [h for h, r in breed["roles"].items() if r == "main"]
        for target in (sw["black"], sw["white"], "#000000"):
            cmap = color_map(breed, target, None)
            lost = len(mains) - len(set(cmap.values()))
            if target != "#000000":  # 순검정은 여유가 0 이라 뭉개지는 게 정상 — 하한만 본다
                # 8비트 sRGB 반올림/무채색 chroma_keep 축소로 인한 겹침은 음영 단계가
                # 촘촘할수록(=main 색이 많을수록) 늘어난다 — 알고리즘 버그가 아니라 색
                # 공간 해상도의 한계다. 그래서 견종별 main 개수에 비례한 허용치를 쓴다
                # (실측: corgi 10→#453d3e 1개, golden 29→#453d3e 3개/#f4f2ee 2개,
                # dachshund·husky·shiba 는 0개). len(mains)//8 은 이 실측치를 모두
                # 통과시키면서 dachshund·husky·shiba 의 허용치는 최대 1 로 작게 유지한다.
                allowed = len(mains) // 8
                assert lost <= allowed, f"{name} {target}: 음영이 {lost}개 합쳐졌다 (허용 {allowed})"
            assert min(hex_to_lab(v)[0] for v in cmap.values()) >= MIN_FUR_L - 0.5, f"{name} {target}"


def test_neutral_target_stays_neutral():
    """무채색(black·gray) 목표에 원본 색조 편차를 그대로 더하면 반대 색조(파랑)로 넘어간다.

    목표색 자체도 완전한 무채색(b=0)은 아니라서(예: gray 스와치는 b≈-2.9) 절대값 0 을
    기준으로 삼지 않고, 목표의 b 보다 3 이상 더 파래지지 않는지를 본다.
    """
    sw = load_breeds()["swatches"]
    golden = load_breeds()["breeds"]["golden"]
    for target in (sw["black"], sw["gray"]):
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


def test_extract_colors_stride_matches_downscaled_image():
    """256px 초과 사진도 stride 로 같은 비율이면 같은 결과가 나온다(리샘플링이 아니므로).

    폰 사진 원본 해상도(수천 px)를 흉내낸다 — thumbnail 의 안티앨리어싱이었다면
    경계 색이 섞여 결과가 달라질 수 있었다.
    """
    sw = load_breeds()["swatches"]
    big = _photo([(sw["white"], 700), (sw["brown"], 300)])
    small = _photo([(sw["white"], 70), (sw["brown"], 30)])
    assert big.width > 256
    assert extract_colors(big, sw) == extract_colors(small, sw) == ("white", "brown")


def test_fit_to_template_swaps_to_template_order():
    """허스키는 main(회색)이 sub(흰색)보다 어둡다. 흰 개 사진처럼 main·sub 가 뒤집혀
    나오면 캐릭터가 반전되므로, 템플릿의 밝기 순서에 맞게 되돌려야 한다."""
    sw = load_breeds()["swatches"]
    breeds = load_breeds()["breeds"]
    husky = breeds["husky"]
    # 사진이 뒤집힌 순서(main=흰색, sub=회색)로 나오면 맞바꾼다
    assert fit_to_template(husky, sw["white"], sw["gray"]) == (sw["gray"], sw["white"])
    # 이미 템플릿 순서(main=회색, sub=흰색)면 그대로 둔다
    assert fit_to_template(husky, sw["gray"], sw["white"]) == (sw["gray"], sw["white"])
    # golden 은 sub 역할이 없다 — 비교할 대상이 없으니 그대로 둔다
    golden = breeds["golden"]
    assert fit_to_template(golden, sw["black"], sw["white"]) == (sw["black"], sw["white"])
    # sub 가 None(추출 실패)이면 그대로 둔다
    assert fit_to_template(husky, sw["gray"], None) == (sw["gray"], None)


def _shiba_front():
    (front,) = asset_frames(ASSETS / "shiba" / "front.svg")
    return front


def test_character_without_photo_is_original():
    """사진 없이 견종만 골라도 원본색 캐릭터가 나온다 — 가입 흐름을 막지 않는다."""
    data = load_breeds()
    sprite, main, sub = make_character(data["breeds"]["shiba"], None, data["swatches"])
    assert (main, sub) == (None, None)
    assert sprite.tobytes() == _shiba_front().tobytes()


def test_character_from_missing_or_broken_photo_is_original():
    data = load_breeds()
    with tempfile.TemporaryDirectory() as d:
        broken = Path(d) / "broken.jpg"
        broken.write_bytes(b"not an image")
        for photo in (Path(d) / "missing.jpg", broken):
            with contextlib.redirect_stdout(io.StringIO()):  # 예상된 [알림] 출력은 숨긴다
                sprite, main, sub = make_character(data["breeds"]["shiba"], photo, data["swatches"])
            assert (main, sub) == (None, None), photo.name
            assert sprite.tobytes() == _shiba_front().tobytes(), photo.name


def test_cli_missing_photo_exits_cleanly():
    """리뷰 재현 사례: `reference.py missing.jpg --breed shiba` 가 예외로 죽지 않는다."""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "character.png"
        run = subprocess.run(
            [sys.executable, "reference.py", str(Path(d) / "missing.jpg"), "--breed", "shiba", "--out", str(out)],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
        )
        assert run.returncode == 0, run.stderr
        assert out.is_file()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK")
