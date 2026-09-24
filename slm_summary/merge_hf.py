"""원본 HF 체크포인트(base/)에 LoRA 로 바뀐 선형 가중치만 갈아 끼워 ft-hf/ 를 만든다.
mlx fuse 결과는 이름·배치가 mlx 방식이고 정규화 가중치 값도 달라(오프셋을 더해 저장) llama.cpp 변환기에 그대로 넣지 않는다.

    python -m mlx_lm fuse --model base --adapter-path adapters-v2 --save-path fused
    python merge_hf.py adapters-v2
"""
import glob, json, shutil, sys
from pathlib import Path
import mlx.core as mx
from safetensors import safe_open

base, fused, out = Path("base"), Path("fused"), Path("ft-hf")
adapter = sys.argv[1] if len(sys.argv) > 1 else "adapters"
with safe_open(f"{adapter}/adapters.safetensors", "mlx") as s:
    targets = sorted({k.rsplit(".", 1)[0] for k in s.keys()})  # language_model.model.layers.N.xxx

def load_all(d):
    t = {}
    for f in glob.glob(f"{d}/*.safetensors"):
        t.update(mx.load(f))
    return t

B, F = load_all(base), load_all(fused)
to_hf = lambda k: k.replace("language_model.model.", "model.language_model.", 1)

# 이름 대응 확인: LoRA 대상이 아닌 가중치는 원본과 같아야 한다
for k in ["language_model.model.embed_tokens.weight", "language_model.model.layers.3.self_attn.q_norm.weight"]:
    if k in F and to_hf(k) in B:
        same = mx.allclose(F[k].astype(mx.float32), B[to_hf(k)].astype(mx.float32)).item()
        print("대상 아님, 원본과 같음:", k, same)

changed = 0
for m in targets:
    fk, hk = f"{m}.weight", to_hf(f"{m}.weight")
    assert hk in B, hk
    assert F[fk].shape == B[hk].shape, (hk, F[fk].shape, B[hk].shape)
    delta = mx.abs(F[fk].astype(mx.float32) - B[hk].astype(mx.float32)).max().item()
    assert delta > 0, f"LoRA 대상인데 값이 같다: {hk}"
    B[hk] = F[fk].astype(B[hk].dtype)
    changed += 1
print("갈아 끼운 가중치", changed)

shutil.rmtree(out, ignore_errors=True)
shutil.copytree(base, out, ignore=shutil.ignore_patterns("*.safetensors", "*.safetensors.index.json"))
mx.save_safetensors(str(out / "model.safetensors"), B, metadata={"format": "pt"})
print("저장", out)
