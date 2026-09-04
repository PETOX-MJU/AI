# 반려동물 사진 분석

사용자가 올린 사진에서 종·품종·털색·자세를 뽑아낸다.
캐릭터 템플릿 매칭, 이름 추천, 캐릭터 소개 문구에 쓴다.

## 모델

**기본: `Qwen/Qwen2.5-VL-7B-Instruct` (Apache 2.0)**

모델 카드에서 `License: apache-2.0` 을 직접 확인했다. 상업 이용에 조건이 없다.

| 모델 | 크기 | 라이선스 | 상용 |
|---|---|---|---|
| **Qwen2.5-VL-7B-Instruct** | 7B | **Apache 2.0** | ✅ 조건 없음 |
| Kanana 1.5-v-3b (카카오) | 3.6B | `kanana` 자체 라이선스 | ⚠️ **조건 불명 — 문의 필요** |
| HyperCLOVA X SEED Vision (네이버) | 3B | 자체 라이선스 | ⚠️ 상업 허용, 조건 확인 필요 |
| VARCO-VISION 2.0 (NC AI) | 1.7B/14B | CC-BY-NC-4.0 | ❌ 비상업 전용 |

### 라이선스 확인 시 주의

**보도자료를 믿지 말고 모델 카드를 직접 열어라.** 실제로 겪은 사례:

- 카카오 보도자료에는 "Kanana에 Apache 2.0 적용"이라고 나오지만, 그건 **텍스트 LLM 기준**이다.
  VLM 변형인 `kanana-1.5-v-3b-instruct` 의 모델 카드에는 `License: kanana` 라고 적혀 있고
  상업 이용 조건이 명시되어 있지 않다. 쓰려면 카카오에 직접 문의해야 한다 (kanana-mllm@kakaocorp.com).
- Kanana-2 는 4종 모두 **텍스트 전용**이다. 비전 변형이 없다.
- Qwen 은 2026년 8월까지 오픈웨이트 전부 Apache 2.0 이었으나 지금은 모델별로 갈린다.

**같은 제품군 안에서도 변형마다 라이선스가 다르다. 배포 직전에 쓰려는 그 모델의 카드를 확인하라.**

## 한국어 처리

열거값(species, color, coat, pose)은 **영어로 받고 `client.py` 에서 한국어로 옮긴다.**
모델의 한국어 능력에 의존하지 않으므로 라이선스가 깨끗한 모델을 폭넓게 쓸 수 있다.

한국어가 필요한 건 `suggested_names` 뿐이고, 품질이 부족하면 텍스트 LLM 이나
털색·품종 기반 이름 테이블로 대체하면 된다.

## 모델 교체 방법

`client.py` 는 vLLM 의 OpenAI 호환 엔드포인트에 붙는다. 교체는 환경변수 두 개다.

```
export PET_VLM_MODEL=Qwen/Qwen2.5-VL-7B-Instruct
export PET_VLM_BASE_URL=http://localhost:8000/v1
```

앱과 BE 는 `PetAnalysis` 스키마에만 의존한다. 모델이 바뀌어도 그쪽 코드는 손대지 않는다.

## 사용

```
vllm serve Qwen/Qwen2.5-VL-7B-Instruct --port 8000
python client.py samples/dog.jpg
```

## 출력 계약

```json
{
  "species": "개",
  "breed": "Welsh Corgi",
  "main_color": "황금색",
  "sub_color": "흰색",
  "coat": "단모",
  "pose": "앉음",
  "face_visible": true,
  "suggested_names": ["코코", "누렁이", "몽이"]
}
```

`species` 가 `null` 이면 반려동물을 찾지 못한 것이다. **앱은 기본 캐릭터로 폴백하라.**
사진 분석 실패가 가입 흐름을 막으면 안 된다.

## 역할 범위

**이 모델은 텍스트만 출력한다. 이미지를 생성하지 않는다.**
픽셀 캐릭터 변환은 `../pixelart/` 담당이고, 여기는 메타데이터만 뽑는다.

**화면 캡처 판별에는 쓰지 않는다.** 사용자 화면을 서버로 보내는 구조는 개인정보 문제가
커서 `../shorts_classifier/` 의 온디바이스 CNN 으로 대체했다. 반려동물 사진은 사용자가
직접 올리는 경로라 동의 구조가 명확해 서버 전송이 정당화된다.

## VLM 이 꼭 필요한가

품종 판별은 지도학습으로 이미 잘 풀린 문제다. 상용 정확도가 아쉬우면 전용 분류기가 낫다.

- **Oxford-IIIT Pet** (37종), **Stanford Dogs** (120종) — 공개 데이터셋
- 털색은 `../pixelart/` 의 팔레트 양자화 결과를 재활용하면 된다
- 이름 추천은 비전이 필요 없는 텍스트 작업

`shorts_classifier` 와 같은 구조다 — 작은 전용 모델이 범용 대형 모델보다 정확하고,
가볍고, 라이선스가 깨끗하다. 지금은 VLM 하나로 처리하되 정확도가 부족하면 이쪽으로 옮겨라.

## 배포

서빙 코드는 이 저장소가 아니라 **BE** 에 있다. 여기는 클라이언트·프롬프트·평가만 관리한다.
