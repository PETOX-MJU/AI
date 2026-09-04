"""반려동물 사진 분석 클라이언트 — 모델 교체 가능한 구조.

vLLM 의 OpenAI 호환 엔드포인트에 붙는다. 모델을 바꿔도 이 파일과 앱 코드는
그대로다. 바뀌는 것은 환경변수와 서버에 띄우는 모델뿐이다.

    export PET_VLM_MODEL=kakaocorp/kanana-1.5-v-3b-instruct
    export PET_VLM_BASE_URL=http://localhost:8000/v1
    python client.py samples/dog.jpg
"""

import argparse
import base64
import io
import json
import os
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

PROMPT_PATH = Path(__file__).parent / "prompts" / "pet_analysis.txt"
DEFAULT_MODEL = "kakaocorp/kanana-1.5-v-3b-instruct"  # Apache 2.0
DEFAULT_BASE_URL = "http://localhost:8000/v1"
MAX_SIDE = 896  # 이보다 크게 보내도 분석 품질이 오르지 않는다. 지연만 늘어난다.

# 앱이 의존하는 계약. 모델이 바뀌어도 이 스키마는 고정이다.
REQUIRED_KEYS = ("species", "breed", "main_color", "sub_color", "coat", "pose", "face_visible", "suggested_names")


@dataclass
class PetAnalysis:
    species: str | None
    breed: str
    main_color: str
    sub_color: str | None
    coat: str
    pose: str
    face_visible: bool
    suggested_names: list[str]

    @property
    def is_pet(self) -> bool:
        return self.species is not None


def encode(image_path: Path) -> str:
    image = Image.open(image_path).convert("RGB")
    if max(image.size) > MAX_SIDE:
        scale = MAX_SIDE / max(image.size)
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def parse_response(text: str) -> PetAnalysis:
    """모델이 JSON 앞뒤에 설명을 붙이는 경우가 있어 중괄호 범위만 잘라낸다."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"JSON 을 찾지 못했습니다: {text[:200]!r}")

    data = json.loads(text[start : end + 1])

    if data.get("species") is None:
        return PetAnalysis(None, "", "", None, "", "", False, [])

    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        raise ValueError(f"필드 누락 {missing} — 프롬프트를 이 모델에 맞게 조정하세요")

    return PetAnalysis(**{k: data[k] for k in REQUIRED_KEYS})


def analyze(image_path: Path, model: str | None = None, base_url: str | None = None) -> PetAnalysis:
    from openai import OpenAI

    model = model or os.environ.get("PET_VLM_MODEL", DEFAULT_MODEL)
    base_url = base_url or os.environ.get("PET_VLM_BASE_URL", DEFAULT_BASE_URL)
    client = OpenAI(base_url=base_url, api_key=os.environ.get("PET_VLM_API_KEY", "EMPTY"))

    response = client.chat.completions.create(
        model=model,
        max_tokens=512,
        temperature=0,  # 같은 사진에 같은 캐릭터가 나와야 한다
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": encode(image_path)}},
                    {"type": "text", "text": PROMPT_PATH.read_text(encoding="utf-8")},
                ],
            }
        ],
    )
    return parse_response(response.choices[0].message.content or "")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    args = parser.parse_args()

    result = analyze(args.image, args.model, args.base_url)
    if not result.is_pet:
        print("반려동물을 찾지 못했습니다. 앱에서는 기본 캐릭터로 폴백하세요.")
        return

    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
