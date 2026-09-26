"""파인튜닝 모델 평가. 세트 A = 학습 전 비교에 쓴 사실 97개, B = 학습에 없던 극단값 200개.

    python eval_ft.py mlx adapters-v2                 # 어댑터를 붙인 mlx 모델 (빠른 확인)
    python eval_ft.py gguf models/ft-v2-q4.gguf        # 폰 배포 형태 (llama-server)
    python eval_ft.py gguf models/ft-v2-q4.gguf --temp=0.5   # 요청마다 시드를 바꿔 다양성까지 본다
"""

import json
import random
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import bench
from data import APP, SYSTEM, fill, marker_errors, user_text

HERE = Path(__file__).resolve().parent
TEMP = float(next((a.split("=")[1] for a in sys.argv if a.startswith("--temp=")), 0))
SHOW_APPS = ["유튜브", "인스타그램", "틱톡", "치지직", "아프리카TV", "네이버 웹툰"]  # 채운 문장을 읽어 보기 위한 이름


def cases() -> dict[str, list[tuple[str, str]]]:
    """(모델에 넣을 사실, 보여 줄 앱 이름)."""
    rng = random.Random(7)
    a = []
    for fact in (f for _ in range(40) for f in bench.scenario(rng)):
        name = next((n for n in bench.APPS if f" {n}이고" in fact), SHOW_APPS[len(a) % len(SHOW_APPS)])
        a.append((fact.replace(f" {name}이고", f" {APP}이고"), name))
    b = [json.loads(line)["messages"][1]["content"].removeprefix("사실: ") for line in open(HERE / "data" / "test_b.jsonl")]
    return {"A": a, "B": [(f, SHOW_APPS[i % len(SHOW_APPS)]) for i, f in enumerate(b)]}


def mlx_generator(adapter: str):
    from mlx_lm import generate, load
    from mlx_lm.sample_utils import make_sampler

    model, tok = load(str(HERE / "base"), adapter_path=str(HERE / adapter))

    def gen(fact: str, seed: int) -> str:
        import mlx.core as mx
        mx.random.seed(seed)
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_text(fact)}]
        prompt = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False, enable_thinking=False)
        return generate(model, tok, prompt=prompt, max_tokens=80, sampler=make_sampler(temp=TEMP))
    return gen, None


def gguf_generator(path: str):
    server = subprocess.Popen(
        ["llama-server", "-m", path, "--port", str(bench.PORT), "-c", "1024", "-ngl", "0", "-t", "4", "--jinja"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(120):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{bench.PORT}/health", timeout=1)
            break
        except Exception:
            time.sleep(0.5)

    def gen(fact: str, seed: int) -> str:
        res = bench.post({
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_text(fact)}],
            "temperature": TEMP, "seed": seed, "max_tokens": 80, "chat_template_kwargs": {"enable_thinking": False},
        })
        gen.speed.append(res.get("timings", {}).get("predicted_per_second") or 0)
        return res["choices"][0]["message"]["content"]
    gen.speed = []
    return gen, server


def main() -> None:
    backend, target = sys.argv[1], sys.argv[2]
    gen, server = mlx_generator(target) if backend == "mlx" else gguf_generator(target)
    tag = Path(target).stem + (f"_t{TEMP}" if TEMP else "")
    try:
        for name, items in cases().items():
            rows = []
            for i, (fact, app) in enumerate(items):
                out = gen(fact, seed=i).strip()
                fail = ([k for k, v in bench.check([fact], out).items() if v] + bench.meaning_errors([fact], out)
                        + marker_errors(fact, out))
                rows.append({"fact": fact, "out": out, "shown": fill(out, app), "fail": fail})
            (HERE / "results" / f"{tag}_{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
            ok = sum(not r["fail"] for r in rows)
            kinds = {}
            for r in rows:
                for f in r["fail"]:
                    kinds[f] = kinds.get(f, 0) + 1
            shapes = len({re.sub(r"[0-9.]+", "N", r["out"]) for r in rows})
            speed = f"  {sum(gen.speed) / len(gen.speed):.0f} tok/s" if getattr(gen, "speed", None) else ""
            print(f"{tag} 세트 {name}: 자동 검사 통과 {ok}/{len(rows)}  서로 다른 문장 틀 {shapes}개  {kinds}{speed}", flush=True)
    finally:
        if server:
            server.terminate()
            server.wait()


if __name__ == "__main__":
    main()
