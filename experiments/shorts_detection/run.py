"""숏츠 화면 판별 정확도 실험.

data/shorts/ 와 data/not_shorts/ 에 스크린샷을 넣고 실행하면
VARCO-VISION 의 판별 정확도와 이미지당 지연 시간을 측정한다.

사용:
    python run.py                                  # transformers 로 로컬 실행
    python run.py --backend vllm                   # vLLM 서버에 요청
    python run.py --prompt prompts/v2.txt          # 프롬프트 비교
    python run.py --max-side 768                   # 입력 해상도 축소 후 속도 비교
"""

import argparse
import base64
import io
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

DATA_DIR = Path(__file__).parent / "data"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_MODEL = "NCSOFT/VARCO-VISION-2.0-1.7B"


@dataclass
class Sample:
    path: Path
    is_shorts: bool


@dataclass
class Result:
    sample: Sample
    predicted: bool | None  # None = 응답을 예/아니오로 해석하지 못함
    raw: str
    latency_s: float


def load_samples() -> list[Sample]:
    samples = []
    for label, is_shorts in (("shorts", True), ("not_shorts", False)):
        for path in sorted((DATA_DIR / label).iterdir()):
            if path.suffix.lower() in IMAGE_SUFFIXES:
                samples.append(Sample(path=path, is_shorts=is_shorts))
    return samples


def load_image(path: Path, max_side: int | None) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if max_side and max(image.size) > max_side:
        scale = max_side / max(image.size)
        new_size = (round(image.width * scale), round(image.height * scale))
        image = image.resize(new_size, Image.LANCZOS)
    return image


def parse_answer(text: str) -> bool | None:
    """모델 응답에서 예/아니오를 뽑아낸다. 부정형이 긍정형을 포함하므로 순서가 중요하다."""
    head = text.strip().lower()[:20]
    for token in ("아니오", "아니요", "아님", "no"):
        if token in head:
            return False
    for token in ("예", "네", "맞", "yes"):
        if token in head:
            return True
    return None


class TransformersBackend:
    def __init__(self, model_id: str):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        self.torch = torch
        self.processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        self.model = AutoModelForImageTextToText.from_pretrained(
            model_id,
            dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )
        self.model.eval()

    def ask(self, image: Image.Image, prompt: str) -> str:
        conversation = [
            {
                "role": "user",
                "content": [{"type": "image"}, {"type": "text", "text": prompt}],
            }
        ]
        text = self.processor.apply_chat_template(conversation, add_generation_prompt=True)
        inputs = self.processor(images=image, text=text, return_tensors="pt").to(self.model.device)
        with self.torch.inference_mode():
            output = self.model.generate(**inputs, max_new_tokens=8, do_sample=False)
        generated = output[0][inputs["input_ids"].shape[-1] :]
        return self.processor.decode(generated, skip_special_tokens=True)


class VLLMBackend:
    def __init__(self, model_id: str, base_url: str):
        from openai import OpenAI

        self.model_id = model_id
        self.client = OpenAI(base_url=base_url, api_key="EMPTY")

    def ask(self, image: Image.Image, prompt: str) -> str:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=90)
        data_url = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()
        response = self.client.chat.completions.create(
            model=self.model_id,
            max_tokens=8,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        return response.choices[0].message.content or ""


def report(results: list[Result]) -> None:
    tp = sum(r.predicted is True and r.sample.is_shorts for r in results)
    fp = sum(r.predicted is True and not r.sample.is_shorts for r in results)
    fn = sum(r.predicted is False and r.sample.is_shorts for r in results)
    tn = sum(r.predicted is False and not r.sample.is_shorts for r in results)
    unparsed = [r for r in results if r.predicted is None]

    total = len(results)
    correct = tp + tn
    latencies = sorted(r.latency_s for r in results)

    print("\n" + "=" * 52)
    print(f"샘플 {total}장 | 정확도 {correct / total:.1%} ({correct}/{total})")
    print("-" * 52)
    print("                 예측:숏츠   예측:아님")
    print(f"  실제 숏츠        {tp:>6}      {fn:>6}")
    print(f"  실제 아님        {fp:>6}      {tn:>6}")
    print("-" * 52)

    if tp + fn:
        print(f"재현율(숏츠를 놓치지 않는가) : {tp / (tp + fn):.1%}")
    if tp + fp:
        print(f"정밀도(오탐이 적은가)        : {tp / (tp + fp):.1%}")
    print(f"지연 중앙값 {latencies[len(latencies) // 2]:.2f}s | 최대 {latencies[-1]:.2f}s")

    if unparsed:
        print(f"\n[경고] 예/아니오로 해석 실패 {len(unparsed)}건 — 프롬프트를 더 강하게 제약하세요")
        for r in unparsed[:3]:
            print(f"  {r.sample.path.name}: {r.raw!r}")

    wrong = [r for r in results if r.predicted is not None and r.predicted != r.sample.is_shorts]
    if wrong:
        print(f"\n오답 {len(wrong)}건:")
        for r in wrong:
            expected = "숏츠" if r.sample.is_shorts else "아님"
            print(f"  {r.sample.path.parent.name}/{r.sample.path.name} (정답:{expected}) -> {r.raw.strip()!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["transformers", "vllm"], default="transformers")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default="http://localhost:8000/v1", help="vLLM 서버 주소")
    parser.add_argument("--prompt", type=Path, default=Path(__file__).parent / "prompts" / "v1.txt")
    parser.add_argument("--max-side", type=int, default=1024, help="긴 변 기준 리사이즈 (0이면 원본)")
    args = parser.parse_args()

    samples = load_samples()
    if not samples:
        raise SystemExit(
            f"스크린샷이 없습니다. {DATA_DIR}/shorts 와 {DATA_DIR}/not_shorts 에 이미지를 넣어주세요."
        )

    prompt = args.prompt.read_text(encoding="utf-8").strip()
    print(f"모델 {args.model} | 백엔드 {args.backend} | 프롬프트 {args.prompt.name} | 샘플 {len(samples)}장")

    if args.backend == "transformers":
        backend = TransformersBackend(args.model)
    else:
        backend = VLLMBackend(args.model, args.base_url)

    results = []
    for i, sample in enumerate(samples, 1):
        image = load_image(sample.path, args.max_side or None)
        started = time.perf_counter()
        raw = backend.ask(image, prompt)
        latency = time.perf_counter() - started
        predicted = parse_answer(raw)
        results.append(Result(sample=sample, predicted=predicted, raw=raw, latency_s=latency))

        mark = "?" if predicted is None else ("O" if predicted == sample.is_shorts else "X")
        print(f"[{i:>3}/{len(samples)}] {mark} {sample.path.name} ({latency:.2f}s)")

    report(results)


if __name__ == "__main__":
    main()
