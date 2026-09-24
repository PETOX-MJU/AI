# 견종 템플릿 재색칠

반려동물 사진에서 털색을 뽑아, 사용자가 고른 견종 픽셀 템플릿을 그 색으로 다시 칠한다.
사진을 그대로 픽셀화하던 이전 모듈을 대체했다.

## 이 디렉터리의 목적

`reference.py` 는 **Kotlin 이식용 기준 구현**이다. 파라미터를 여기서 튜닝해 확정한 뒤
같은 알고리즘을 앱의 `Bitmap` 연산으로 옮긴다.

## 파이프라인

```
사진 → 배경 제거 (앱: ML Kit Subject Segmentation / 여기: rembg)
     → 픽셀마다 가까운 스와치로 → 면적 순   main·sub 털색 (스와치 이름)
견종(사용자 선택) + main·sub → 색 치환표 {원본 hex: 새 hex}
     → 에셋 프레임 픽셀 치환              캐릭터
```

**생성형 모델은 쓰지 않는다.** 전부 결정론적 연산이라 온디바이스에서 즉시 돌고 같은 입력에 같은 결과가 나온다.
견종 분류기도 없다. 견종은 사용자가 고르므로 오답이 없다.

**사진이 없거나 배경 제거·털색 추출이 실패하면** `color_map(breed, None, None)` 이 빈 표를 돌려주고
견종 템플릿 원본색이 그대로 나온다. 가입 흐름을 막지 않는다.

## 에셋과 역할표

- `assets/<견종>/` — 디자인 드라이브 `peTox_픽셀` 의 파일. 앞·뒤·오·왼 SVG + 견종에 따라 걷기·짖기 GIF.
- `breeds.json` — 스와치, 견종별 에셋 목록, **역할표**(hex → `main`/`sub`/`keep`).
  - `main` 주 털색 계열, `sub` 보조 털색 계열(흰 배·크림 얼굴 등), `keep` 외곽선·눈·코·귀 안쪽·혀
  - 역할의 기준색은 그 역할에서 픽셀 수가 가장 많은 색이다
  - 단색 견종(golden 등)은 `sub` 가 없다 — 밝은 크림 음영도 `main` 하이라이트로 묶인다

## 사용

```
python reference.py samples/testdog.png --breed golden   # 사진 → 캐릭터 (8배 확대 PNG)
python reference.py --sheet                              # 견종 × 스와치 확인 시트
python reference.py --roles-sheet                        # 역할표 검수 시트
python reference.py --suggest-roles                      # breeds.json 초안 출력
python test_reference.py
```

## 견종 추가·에셋 교체 절차

1. 드라이브 파일을 `assets/<견종>/` 에 영문 이름으로 넣는다 (앞/뒤/오/왼 → front/back/right/left, 오걷/왼걷 → walk_right/walk_left)
2. `python reference.py --suggest-roles` 로 해당 견종 초안을 뽑아 `breeds.json` 에 합친다
3. `python reference.py --roles-sheet` 로 검수 — 빨강=main, 파랑=sub 가 맞게 칠해졌는지, 눈·외곽선이 원본인지
4. `python test_reference.py` — 에셋 색이 역할표에 빠짐없이 있는지 검사한다

에셋만 바뀌어도 4번이 실패한다. 새 색만 역할표에 추가하면 된다.

## 튜닝 포인트

| 상수 | 영향 |
|---|---|
| `SWATCHES` | 사용자가 고르는 털색. 사진 색은 가장 가까운 스와치로 붙는다 |
| `SUB_RATIO` (0.2) | 두 번째 색이 이 비율 이상이면 sub. 낮추면 눈·혀가 sub 로 잡힌다 |
| `CHROMA_KEEP` (0.3) | 명암 단계의 색조 편차를 얼마나 남길지. 높이면 원본 느낌, 낮추면 단색에 가깝다. 목표색 채도가 낮을수록(무채색에 가까울수록) 비례해서 덜 적용된다 |
| `MIN_FUR_L` (15) | 털 밝기 하한. 목표색 L 도 이 값 이상으로 올려서(순검정도 L 15 로) 검은 털이 외곽선과 붙지 않게 한다. 음영은 잘라내지 않고 비율로 압축한다 |

## 검증 상태

| 항목 | 상태 |
|---|---|
| 역할표 커버리지 (5견종 전 에셋) | ✅ 테스트 |
| 재색칠 명암 순서·음영 단계 유지·밝기 하한 | ✅ 테스트 |
| 스와치 시트 눈 검수 | 커밋 시점 기록 참고 |
| **실제 반려동물 사진 털색 추출** | ❌ **미검증** — 합성 이미지로만 확인 (`samples/testdog.png` 도 합성 도형) |
| ML Kit 마스크와의 차이 | ❌ 미검증 |

### 알려진 한계

- 흰 털이 그림자 때문에 gray 로 잡힐 수 있다. 실사진으로 스와치 값을 조정하라.
- 원본 털색과 목표색이 멀면(검은 닥스 → 흰색) 명암이 어색할 수 있다. 스와치 시트로 확인하라.
- 외곽선과 눈이 같은 hex 를 쓰는 에셋이 있어, 외곽선만 따로 바꾸는 처리는 할 수 없다.

## 이식 시 주의

- 앱에서 옮길 것은 `extract_colors`(털색), `color_map`(Lab 변환 포함), `recolor_image`(픽셀 치환) 셋이다. SVG 를 직접 그린다면 `recolor_svg`
- `extract_colors` 는 양자화 없이 픽셀별 최근접 스와치라 Kotlin 에서도 같은 값이 나온다. `test_reference.py` 의 합성 사례(`test_extract_*`, `test_near_colors_snap_to_swatch`)를 FE 테스트로 그대로 옮겨 결과를 맞춰라
- 역할표·스와치는 `breeds.json` 을 그대로 앱 에셋으로 넣는다. 코드에 옮겨 적지 마라
- 치환표는 견종·색 조합당 한 번 계산해 캐시하면 된다. 프레임마다 다시 만들 필요가 없다
- rembg(U2-Net)와 ML Kit 마스크는 다르다. 최종 확인은 실기기에서 하라
