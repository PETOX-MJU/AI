# 반려동물 사진 → 캐릭터 템플릿 매칭 설계

2026-09-23 · 상태: 검토 대기

## 목표

사진을 픽셀화하던 `pixelart/` 를 **대체**한다. 디자이너가 만든 완성 스프라이트 N종 중
사진에 가장 맞는 하나를 고른다.

```
템플릿 = templates[group][color]
  group  사용자가 카드에서 선택 (체형 그룹)
  color  사진에서 자동 추출 → 사용자가 바꿀 수 있음
```

## 범위

| 포함 | 제외 (필요해지면 추가) |
|---|---|
| 사진 → 주색·보조색 추출 | 종 그룹 자동 분류기 |
| (group, main, sub) → 템플릿 매칭 | 학습 데이터셋 |
| 템플릿·팔레트 데이터 파일 | 이름 추천 |
| `pixelart/` 삭제, 문서 정리 | |

종 그룹을 사용자가 고르므로 학습, 데이터, 라이선스 쟁점이 없고 분류 오답도 없다.
분류기는 나중에 "추천 기본값"으로 붙인다.

## 구성

```
pet_template/
  reference.py        색 추출 + 매칭 (Kotlin 이식용 기준 구현)
  templates.json      팔레트 + 템플릿 목록
  test_reference.py
  README.md
  samples/testdog.png pixelart/samples 에서 이동
```

`pixelart/` 는 통째로 삭제한다. 재사용할 함수(`load_upright`, `remove_background`)는
`pet_template/reference.py` 로 옮긴다. 크롭·다운샘플·양자화·외곽선은 쓰지 않는다.

## 데이터 파일

색 목록과 투톤 여부가 아직 정해지지 않았다. 그래서 코드가 아니라 데이터로 받는다.
디자인이 확정되면 이 파일만 고친다.

```json
{
  "palette": {"white": [240,238,232], "cream": [225,200,160], "golden": [200,150,80],
              "brown": [120,80,50], "black": [30,28,28], "gray": [140,140,140]},
  "templates": [
    {"id": "retriever_golden", "group": "retriever", "main": "golden", "sub": null},
    {"id": "corgi_golden_white", "group": "corgi", "main": "golden", "sub": "white"}
  ]
}
```

- 그룹마다 템플릿이 최소 1개 있어야 한다. 그룹의 첫 템플릿을 그 그룹의 기본값으로 쓴다.
- 로드 시 검사: `main`·`sub` 가 팔레트에 있어야 하고, `id` 가 중복되면 안 되며, 그룹이 비면 안 된다. 어기면 즉시 예외.

## 흐름

1. `load_upright` → `remove_background` (앱: ML Kit Subject Segmentation)
2. 알파 > 128 픽셀만 모은다. 0개면 추출 실패 → 5번 기본값.
3. 모은 픽셀을 `quantize(3, MEDIANCUT)` 으로 3색으로 줄인다. pixelart 와 같은 연산이라 이식 부담이 늘지 않는다.
4. 각 색을 **Lab 거리**로 가장 가까운 팔레트 이름에 붙이고, 이름이 같은 색끼리 면적을 합친다.
   - 가장 넓은 색 = `main`
   - 두 번째 색 비율 ≥ `SUB_RATIO`(0.2, 튜닝값) → `sub`, 아니면 `null`
5. 선택한 `group` 안에서 아래 순서로 첫 일치를 찾는다.
   1. `(main, sub)` 일치
   2. `(main, null)` 일치
   3. `main` 만 일치
   4. 그룹 기본값

   이 순서면 템플릿이 단색만 있든 투톤까지 있든 코드를 바꾸지 않고 동작한다.

출력: `{"template_id", "main", "sub"}`. 앱은 `main`·`sub` 를 기본 선택으로 보여주고,
사용자가 색을 바꾸면 5단계만 다시 돌린다.

## 오류 처리

- 사진 없음, 유효성 실패(`pet_validation`), 추출 실패 → 그룹 기본 템플릿. **가입 흐름은 막지 않는다.**
- `templates.json` 이 잘못됐으면 로드 시 예외. 배포 전 테스트가 잡는다.

## 알려진 위험

- **흰 털이 그림자 때문에 gray 로 잡힐 수 있다.** 팔레트 기준 RGB 와 `SUB_RATIO` 는 실제 사진으로 조정한다.
- 눈·코·혀는 면적이 작아서 `SUB_RATIO` 에 걸러질 것으로 본다. 실사진으로 확인해야 한다.
- 배경 제거가 덜 되면 배경색이 섞인다. rembg 와 ML Kit 마스크는 다르므로 최종 확인은 실기기에서 한다.

## 테스트

`test_reference.py` 에서 합성 RGBA 이미지로 배경 제거를 건너뛰고 확인한다.

| 입력 | 기대 |
|---|---|
| 갈색 단색 | main=brown, sub=null |
| 흰 70% + 갈 30% | main=white, sub=brown |
| 흰 90% + 갈 10% | main=white, sub=null |
| 완전 투명 | 그룹 기본값 |
| 매칭 폴백 4단계 | 각 단계가 순서대로 선택됨 |
| 잘못된 templates.json | 예외 |

## 문서 정리

- `README.md`: 아키텍처 그림의 "픽셀화" 경로, 구성표, 검증 상태 표
- `pet_validation/README.md`: "픽셀화로 진행"과 "품종은 캐릭터 생성에 쓰이지 않는다" 문단
- `experiments/pet_analysis_vlm/README.md`: `../pixelart/` 참조
- `LICENSING.md`: rembg 행의 사용처를 `pet_template/` 으로
- `.gitignore`: pixelart 생성물 줄 삭제
