"""반려동물 사진 → 픽셀 캐릭터 변환 기준 구현.

이 파일은 **Kotlin 이식용 기준**이다. 파라미터를 여기서 튜닝해 확정한 뒤
같은 알고리즘을 앱의 Bitmap 연산으로 옮긴다. 이식이 목적이므로
파이썬다운 축약보다 단계가 드러나는 쪽을 택했다.

앱에서의 대응:
    remove_background  → ML Kit Subject Segmentation (여기서는 rembg 로 근사)
    이하 전 단계        → android.graphics.Bitmap 연산

    python reference.py samples/dog.jpg --pixel-size 48 --colors 16
"""

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


@dataclass
class Params:
    pixel_size: int = 48      # 긴 변 기준 픽셀 격자 해상도
    colors: int = 16          # 팔레트 색 수
    outline: bool = True      # 캐릭터 외곽선
    outline_dark: tuple = (30, 30, 40)    # 밝은 피사체용
    outline_light: tuple = (235, 232, 228)  # 어두운 피사체용
    preview_scale: int = 8    # 미리보기 확대 배율


def load_upright(path: Path) -> Image.Image:
    """폰 사진은 EXIF 회전 정보를 갖는다. 적용하지 않으면 캐릭터가 옆으로 눕는다."""
    return ImageOps.exif_transpose(Image.open(path)).convert("RGBA")


def remove_background(image: Image.Image) -> Image.Image:
    """배경을 지우고 RGBA 로 돌려준다. 앱에서는 ML Kit 이 담당한다."""
    try:
        from rembg import remove
    except ImportError:
        print("[알림] rembg 미설치 — 배경 제거를 건너뜁니다 (pip install rembg)")
        return image.convert("RGBA")
    return remove(image).convert("RGBA")


def crop_to_subject(image: Image.Image, padding: int = 4) -> Image.Image:
    """투명 영역을 잘라내 피사체를 격자에 꽉 채운다. 이걸 빼면 캐릭터가 작게 나온다."""
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return image
    left, top, right, bottom = bbox
    return image.crop(
        (
            max(0, left - padding),
            max(0, top - padding),
            min(image.width, right + padding),
            min(image.height, bottom + padding),
        )
    )


def downsample(image: Image.Image, pixel_size: int) -> Image.Image:
    """긴 변을 pixel_size 로 맞춘다. NEAREST 여야 픽셀 경계가 뭉개지지 않는다."""
    scale = pixel_size / max(image.size)
    target = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(target, Image.NEAREST)


def quantize_palette(image: Image.Image, colors: int) -> Image.Image:
    """색 수를 줄여 픽셀아트 느낌을 만든다. 알파는 양자화에서 제외하고 나중에 되돌린다."""
    alpha = image.getchannel("A")
    rgb = image.convert("RGB")
    # MEDIANCUT 은 Kotlin 이식이 어렵지 않다. 결과가 아쉬우면 k-means 로 교체.
    quantized = rgb.quantize(colors=colors, method=Image.MEDIANCUT).convert("RGB")
    result = quantized.convert("RGBA")
    result.putalpha(alpha)
    return result


def pick_outline(image: Image.Image, params: "Params") -> tuple:
    """어두운 동물에 어두운 테두리를 두르면 실루엣으로 뭉개진다.

    검은 고양이·장모 흑견에서 실제로 재현되는 실패라 피사체 밝기로 테두리 색을 뒤집는다.
    """
    arr = np.array(image)
    opaque = arr[:, :, 3] > 128
    if not opaque.any():
        return params.outline_dark

    rgb = arr[:, :, :3][opaque].astype(np.float32)
    luminance = (0.299 * rgb[:, 0] + 0.587 * rgb[:, 1] + 0.114 * rgb[:, 2]).mean()
    return params.outline_light if luminance < 90 else params.outline_dark


def add_outline(image: Image.Image, rgb: tuple) -> Image.Image:
    """불투명 픽셀의 바깥 경계에 1px 테두리를 두른다. 캐릭터가 배경에서 떠 보이게 한다."""
    arr = np.array(image)
    opaque = arr[:, :, 3] > 128

    neighbors = np.zeros_like(opaque)
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        neighbors |= np.roll(np.roll(opaque, dy, axis=0), dx, axis=1)
    border = neighbors & ~opaque

    arr[border] = [*rgb, 255]
    return Image.fromarray(arr)


def convert(path: Path, params: Params) -> Image.Image:
    image = load_upright(path)
    image = remove_background(image)
    image = crop_to_subject(image)
    image = downsample(image, params.pixel_size)
    image = quantize_palette(image, params.colors)
    if params.outline:
        image = add_outline(image, pick_outline(image, params))
    return image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--pixel-size", type=int, default=Params.pixel_size)
    parser.add_argument("--colors", type=int, default=Params.colors)
    parser.add_argument("--no-outline", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    params = Params(pixel_size=args.pixel_size, colors=args.colors, outline=not args.no_outline)
    sprite = convert(args.image, params)

    out = args.out or args.image.with_name(f"{args.image.stem}_pixel.png")
    sprite.save(out)

    preview = sprite.resize(
        (sprite.width * params.preview_scale, sprite.height * params.preview_scale), Image.NEAREST
    )
    preview_path = out.with_name(f"{out.stem}_preview.png")
    preview.save(preview_path)

    print(f"스프라이트 {out} ({sprite.width}x{sprite.height})")
    print(f"미리보기   {preview_path}")


if __name__ == "__main__":
    main()
