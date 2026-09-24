# 한줄 요약 SLM (온디바이스)

대시보드 한줄 요약을 템플릿 대신 폰에서 도는 작은 언어 모델(SLM)로 만드는 실험.
**Qwen3.5 0.8B 를 LoRA 로 파인튜닝해 4비트 GGUF(약 540MB)로 배포**하는 것이 현재 후보다.

> 아직 앱에 붙이지 않았다. 붙일 때는 `kotlin_port/contracts/output.schema.json` 의 `insight.source`(지금은
> `"template"` 고정)와 대시보드 명세의 "생성형 AI 배지 금지" 규칙을 먼저 고쳐야 한다.

## 설계

- **모델에게는 사실 하나만 준다.** 분석기 템플릿 문장(`Narratives.kt`) 하나를 펫 말투 한 문장으로 바꾸는 일만 한다.
  사실 2~4개를 한 번에 주면 2B 모델도 숫자를 엉뚱한 사실에 붙였다(아래 「모델 선택」).
- **앱 이름은 모델에 넣지 않는다.** 사실에는 `{앱}`, 출력에는 `{앱:을}` 같은 자리표시를 쓰고
  `data.fill()` 이 실제 이름과 받침에 맞는 조사로 바꾼다. 처음 보는 이름이 깨지는 일이 없다.
- **숫자·계산은 여전히 분석기가 한다.** 모델은 사실의 숫자를 옮기기만 한다.
- **출력은 검사하고, 실패하면 템플릿 문장을 그대로 쓴다.** 앱에 넣을 검사:
  - 숫자: 출력의 모든 숫자(단위 포함)가 사실에 있다 (`bench.meaning_errors`)
  - 방향: 줄어든 값을 "늘었다"로 쓰지 않는다
  - 형식: 한 문장, 90자 이하, 한자·가나·사실에 없는 로마자 없음, 금지어 없음 (`bench.check`)
  - 자리표시: `{앱}` 이 사실에 있으면 정확히 한 번 (`data.marker_errors`)

## 파일

| 파일 | 하는 일 |
|---|---|
| `bench.py` | 학습 전 모델 4종 비교(사실 여러 개 / 하나씩). 자동 검사 함수 `check`, `meaning_errors` |
| `data.py` | 학습 데이터 생성. 사실은 분석기와 같은 문구, 정답은 펫 말투 틀에 숫자를 코드로 넣는다. `fill` 도 여기 있다 |
| `merge_hf.py` | LoRA 로 바뀐 선형 가중치만 원본 HF 체크포인트에 갈아 끼운다 (GGUF 변환용) |
| `eval_ft.py` | 파인튜닝 모델 평가. 세트 A(학습 전 비교에 쓴 사실 97개), B(학습에 없던 극단값 200개) |

모델·데이터·결과 파일은 커밋하지 않는다(`.gitignore`). 아래 절차로 다시 만든다.

## 재현

```bash
# 학습용 (Apple Silicon). anaconda 파이썬은 MPICH 때문에 mlx 학습이 죽는다 — Homebrew 파이썬을 쓴다
/opt/homebrew/bin/python3.14 -m venv .venv && .venv/bin/pip install mlx-lm==0.31.3
hf download Qwen/Qwen3.5-0.8B --local-dir base
brew install llama.cpp

python data.py                                     # data/train.jsonl 3000, valid 150, test_b 200
.venv/bin/python -m mlx_lm lora --model base --train --data data --mask-prompt --num-layers -1 \
  --batch-size 4 --iters 1500 --learning-rate 1e-4 --max-seq-length 256 --grad-checkpoint \
  --adapter-path adapters-v2 --seed 0             # M3 Pro 약 1시간 40분. 메모리가 빠듯하면 스왑으로 멈춘다

# GGUF 변환 (llama.cpp 저장소의 변환기. torch·gguf 가 든 별도 venv)
.venv/bin/python -m mlx_lm fuse --model base --adapter-path adapters-v2 --save-path fused
.venv/bin/python merge_hf.py adapters-v2           # fused/ 를 통째로 쓰지 않는 이유는 파일 머리말 참고
git clone --depth 1 https://github.com/ggml-org/llama.cpp llama.cpp-src
.conv/bin/python llama.cpp-src/convert_hf_to_gguf.py ft-hf --outfile models/ft-v2-f16.gguf --outtype f16
llama-quantize models/ft-v2-f16.gguf models/ft-v2-q4.gguf Q4_K_M

python eval_ft.py gguf models/ft-v2-q4.gguf                # 온도 0
python eval_ft.py gguf models/ft-v2-q4.gguf --temp=0.5     # 요청마다 시드를 바꿔 다양성까지
```

## 모델 선택 (학습 전, 2026-09-24)

같은 지시문·예시 1개, 온도 0, CPU 4스레드(폰 CPU 추론에 가깝게). 뜻 오류는 사람이 읽고 채점했다.

**사실 2~4개를 한 번에:** 전 모델 부적합. 0.5B·0.8B 는 입력을 거의 그대로 옮겼고,
1.5B·2B 도 "6일 중 7개 달성", "59.2% 증가"(실제 감소)처럼 숫자를 뒤섞었다.

**사실 하나씩 (50건 채점):**

| 모델 | 좋음 | 뜻 틀림 | 형식 실패 | 4비트 크기 | 속도(맥 CPU) |
|---|---|---|---|---|---|
| HyperCLOVA X SEED 0.5B | 약 7 | 다수 | 대부분 | 368MB | 113 tok/s |
| Qwen3.5 0.8B | 24 | 10 | 11 | 580MB | 80 tok/s |
| HyperCLOVA X SEED 1.5B | 22 (+전보식 20) | 4 | 4 | 1.0GB | 56 tok/s |
| Qwen3.5 2B | 39 | 7 | 4 | 1.4GB | 42 tok/s |

1B 미만은 그대로는 약하다. 실패가 "입력 복사", "줄었다 → 늘었다" 같은 패턴에 몰려 있어 파인튜닝으로 고치기로 했다.

## 파인튜닝 결과

### v1 (2026-09-24) — 앱 이름을 그대로 넣음, 숫자 420분까지

| | 학습 전 0.8B | 학습 전 2B | v1 0.8B (4비트) |
|---|---|---|---|
| 세트 A 뜻 틀림 (사람 채점) | 20% | 14% | 0% (온도 0) / 1% (온도 0.7) |
| 세트 A 형식 실패 | 22% | 8% | 0% |
| 세트 B 자동 검사 통과 | — | — | 197/200 |

남은 문제: 네 자리 숫자를 잘라 옮김(1848 → 184), 처음 보는 앱 이름이 깨짐(치지직 → 치지icks),
온도 0.7 에서 두 문장 틀이 섞임("유튜브가 23.1%가 유튜브였어요").

### v2 (2026-09-25) — 앱 이름 자리표시, 숫자 1~5000분, 문장 틀 확대

학습 3000개·1500스텝(검증 손실 0.118). 4비트 541MB, 맥 CPU 4스레드 91~93 tok/s.

| | 온도 0 | 온도 0.5 (요청마다 시드 변경) |
|---|---|---|
| 세트 A 자동 검사 통과 | 97/97 | 97/97 |
| 세트 A 뜻 틀림 (사람 채점) | — | **1/97** |
| 세트 A 서로 다른 문장 틀 | 20 | 44 |
| 세트 B 자동 검사 통과 (1~9999분 극단값 포함) | **200/200** | 199/200 |

앱에서는 **온도 0.5** 를 쓴다. 온도 0 은 사실 종류마다 거의 같은 문장만 낸다.

v1 문제 해결: 네 자리 숫자는 세트 B 온도 0 에서 전부 맞게 옮겼고, 앱 이름은 모델이 보지 않으니 깨질 일이 없다.

남은 문제 (v3 에서 고친다):
- 온도 0.5 에서 틀이 섞이는 경우가 가끔 있다. 세트 A "'학습'용 92.8%를 틱톡이 차지했어요"(사용 목적과 비중을 섞음),
  세트 B "밤 사용의 4282분이었어요"(숫자 오류라 검사에 걸림).
- `data.py` 의 틀 "밤 시간의 {s}를 {앱:이} 차지했어요" 는 뜻이 부정확하다. 이 비중은 밤 시간 전체가 아니라
  **관리 앱 야간 사용** 중 비중이다. "밤 사용의" 로 고쳐야 한다(v2 는 이 틀로 학습했으므로 재현을 위해 그대로 둔다).
- 미션이 둘 다 0개일 때 한 절로 묶는 틀이 있는데도 "다음엔 해낼 수 있어요"를 두 번 쓰는 경우가 있다.

## 알려진 한계

- 정답 문장 틀은 사람이 쓴 것이라, 다양성은 학습한 틀 수를 넘지 않는다. 더 다양하게 하려면 틀을 늘린다.
- 속도는 맥 CPU 기준이다. 실제 폰에서는 몇 배 느리다. 한 줄(수십 토큰)이라 주 1회 생성에는 문제없을 것으로 보지만 실측이 필요하다.
- 입력은 분석기 문장뿐이라 앱 이름·화면 내용 같은 개인정보가 모델에 들어가지 않는다.
