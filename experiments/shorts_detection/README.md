# 숏츠 화면 판별 정확도 실험

펫톡스의 핵심 리스크 검증용. `UsageStatsManager`는 "유튜브 실행"까지만 알려주고
"숏츠 시청 중"인지는 모른다. VARCO-VISION이 스크린샷으로 이걸 판별할 수 있는지 측정한다.

## 1. 스크린샷 수집 (30~40장 권장)

| 폴더 | 넣을 것 |
|---|---|
| `data/shorts/` | 유튜브 Shorts, 인스타 Reels, 틱톡 피드 재생 화면 |
| `data/not_shorts/` | 유튜브 홈/검색/가로영상/댓글, 인스타 피드/스토리/DM, 카톡, 브라우저 |

**오답이 나올 만한 화면을 일부러 섞으세요.** 인스타 스토리(세로 전체화면이지만 숏폼 아님),
유튜브 홈의 Shorts 썸네일 줄, 세로로 찍은 일반 영상 — 여기서 틀리면 실제 앱에서도 틀립니다.

## 2. 실행

```
pip install -r requirements.txt
python run.py
```

vLLM 서버에 붙일 때:

```
vllm serve NCSOFT/VARCO-VISION-2.0-1.7B --port 8000
python run.py --backend vllm
```

## 3. 판정 기준

- **재현율 90% 이상 + 정밀도 85% 이상** → 이 방식으로 간다
- **정확도 70% 미만** → 앱 단위 감지로 후퇴 (유튜브/인스타/틱톡 실행 자체를 트리거)
- 지연이 2초를 넘으면 `--max-side 768`로 해상도를 낮춰 재측정

오탐(정밀도)이 재현율보다 중요합니다. 숏츠를 몇 번 놓치는 건 괜찮지만,
카톡 하는데 캐릭터가 튀어나오면 사용자는 앱을 지웁니다.

## 4. 프롬프트 튜닝

`prompts/v1.txt`(상세)와 `prompts/v2.txt`(간결)를 비교해 보세요.

```
python run.py --prompt prompts/v2.txt
```

정확도가 애매하면 오답 목록을 보고 v3를 만들어 반복합니다.
확정된 프롬프트는 그대로 FastAPI 서버로 옮깁니다.

## 주의

- `data/`는 개인 화면이 담기므로 git에 커밋되지 않습니다 (`.gitignore` 처리됨)
- transformers 클래스/버전 요구사항은 모델 카드를 확인하세요:
  https://huggingface.co/NCSOFT/VARCO-VISION-2.0-1.7B
- VARCO-VISION 2.0은 CC-BY-NC-4.0 (비상업) 라이선스입니다

## 상용 배포 시

**이 디렉터리의 VARCO는 평가·비교 용도 전용이다. 제품에 탑재하지 않는다.**
CC-BY-NC-4.0(비상업)이라 상용 배포 경로에 들어가면 안 된다.

실제 판별은 `../../shorts_classifier/` 의 온디바이스 CNN 이 담당하고,
반려동물 사진 분석은 `../../pet_analysis/` 의 Kanana(Apache 2.0)를 쓴다.
