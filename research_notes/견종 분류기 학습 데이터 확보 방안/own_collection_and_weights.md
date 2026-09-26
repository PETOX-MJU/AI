# 직접 수집(사용자·팀원 사진)과 사전학습 가중치의 법적 상태 — 견종 템플릿 분류기

조사일: 2026-09-29. 관할: 대한민국. 법률 자문이 아니라 1차 자료 조사 노트다. 출시 전에는 변호사 검토를 받는다.

## (A1) PIPA상 반려동물 사진은 개인정보인가, 사용자 사진으로 학습하려면 어떤 법적 근거·동의가 필요한가

### Takeaway
개 사진만 있으면 개인정보가 아니다. 개인정보가 되는 건 사람이 (얼굴 등으로) 식별 가능하게 찍혔을 때, EXIF GPS가 집 주소를 드러낼 때, 계정 ID와 연결돼 저장될 때다. PIPC 2025.8 생성형 AI 안내서는 이용자 데이터의 학습 이용을 세 경우로 나눈다. 원래 목적 안이면 원래의 법적 근거를 쓰고, 관련된 목적이면 제15조 제3항 추가적 이용을 검토할 수 있고, 무관한 목적이면 가명·익명처리나 새 법적 근거(예: 별도 동의)가 필요하다. "견종 인식"용으로 받은 사진을 "모델 재학습"에 쓰는 건 경계선에 있다. 소규모 무료 앱이라면 가장 깔끔한 방법은 별도 옵트인 동의에 더해, 서버로 보내기 전에 기기에서 EXIF 제거와 얼굴 흐림을 하는 것이다.

### Cited Findings
- PIPA 제2조 제1호의 개인정보 정의는 세 가지다. 가목 "성명, 주민등록번호 및 영상 등을 통하여 개인을 알아볼 수 있는 정보", 나목 다른 정보와 "쉽게 결합하여 알아볼 수 있는 정보", 다목 가명정보. 법문 사이트에 표시된 현행 시행일은 2026.9.11(법률 제21445호, 2026.3.10. 일부개정)이다. 이 시행일은 law.go.kr에서 교차확인하지 못했다. — [casenote.kr 개인정보 보호법](https://casenote.kr/법령/개인정보_보호법)
- 제15조 제3항: "당초 수집 목적과 합리적으로 관련된 범위에서" 정보주체에게 불이익이 없고 안전성 확보 조치를 한 경우에는 동의 없이 이용할 수 있다. — [casenote.kr](https://casenote.kr/법령/개인정보_보호법)
- 제22조 제1항: 동의를 받을 때는 "각각의 동의 사항을 구분하여" 정보주체가 명확히 인지하도록 받아야 한다. 이 조항이 "학습 기여 동의"를 필수 동의와 분리해야 하는 근거다. — [casenote.kr](https://casenote.kr/법령/개인정보_보호법)
- 제28조의2 제1항: "통계작성, 과학적 연구, 공익적 기록보존 등"을 위해서는 정보주체 동의 없이 가명정보를 처리할 수 있다. — [casenote.kr](https://casenote.kr/법령/개인정보_보호법)
- PIPC 「생성형 AI 개발·활용을 위한 개인정보 처리 안내서」(2025.8)가 제시하는 이용자 데이터 학습의 적법근거 3단계:
  - 원래 목적 안: "당초 이용자 개인정보 수집의 적법 근거가 된 동의, 계약, 정당한 이익 등에 근거함"
  - 관련된 목적: "추가적 이용 조항(법 제15조 제3항)을 적법근거로 검토할 수 있음"
  - 무관한 목적: "개인정보를 가명·익명처리하거나 새로운 적법근거 마련이 필요함"
  - 출처: [김·장 법률사무소 해설](https://www.kimchang.com/ko/insights/detail.kc?sch_section=4&idx=32696), 원문 [PIPC](https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS074&mCode=C020010000&nttId=11410), [KISA](https://www.kisa.or.kr/2060301/form?postSeq=41&lang_type=KO&page=1)
- 이 안내서는 생성형 AI 수명주기를 목적 설정, 전략 수립, 학습·개발, 시스템 적용·관리의 4단계로 나누고 단계별 고려사항을 정리한다. — [KISA 게시](https://www.kisa.or.kr/2060301/form?postSeq=41&lang_type=KO&page=1)
- 「AI 개발·서비스를 위한 공개된 개인정보 처리 안내서」(2024.7.17)는 웹, 블로그, 커먼크롤 같은 "누구나 합법적으로 접근 가능한" 공개 데이터를 대상으로 하며, 정당한 이익을 근거로 한 학습과 안전조치를 안내한다. 앱에 업로드된 사진은 공개 데이터가 아니므로 이 안내서의 직접 대상이 아니다. — [김·장](https://www.kimchang.com/ko/insights/detail.kc?sch_section=4&idx=30017), [정책브리핑](https://www.korea.kr/briefing/policyBriefingView.do?newsId=156641502)
- 「가명정보 처리 가이드라인」 2024.2 개정판에는 이미지·영상·음성·텍스트 같은 비정형데이터의 가명처리 기준이 새로 들어갔다. 이미지 처리 기법으로는 이미지 필터링(블러·모자이크), 이미지 암호화, 얼굴 합성, 인페인팅을 예시한다. — [법률신문](https://www.lawtimes.co.kr/LawFirm-NewsLetter/195772), [PIPC 비정형데이터 가명처리 기준](https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS074&mCode=C020010000&nttId=9899), [가이드라인 PDF](https://data.gangwon.kr/images/pdf/%EA%B0%80%EB%AA%85%EC%A0%95%EB%B3%B4_%EC%B2%98%EB%A6%AC_%EA%B0%80%EC%9D%B4%EB%93%9C%EB%9D%BC%EC%9D%B8(2024_2_%EA%B0%9C%EC%A0%95).pdf)
- EXIF에는 촬영일시, 기종, GPS 위도·경도가 들어간다. 집에서 찍은 사진의 GPS는 사실상 자택 주소라서 개인정보에 해당할 수 있다. PIPC는 사진을 공유하기 전에 EXIF를 지우라고 홍보한다. — [PIPC 홍보물(혁신24)](https://www.innovation.go.kr/ucms/bbs/B0000060/view.do?nttId=17555&menuNo=300240&searchType=4&pageIndex=1)
- 반려동물 사진 자체가 개인정보인지 PIPC가 직접 판단한 자료는 찾지 못했다. — (동일 검색)

### Inferences
- 개인정보로 바뀌는 경우는 다섯 가지다.
  1. 보호자나 가족의 얼굴이 식별 가능하게 찍힌 경우(제2조 가목의 "영상")
  2. GPS EXIF가 남은 경우
  3. 집 내부, 창밖 풍경, 택배 송장, 이름표처럼 결합하면 개인을 알아볼 수 있는 단서가 있는 경우(나목)
  4. 사진이 계정 ID나 기기 ID와 연결돼 서버에 저장되는 경우
  5. 반려동물 이름표나 등록번호가 찍힌 경우(동물등록번호는 소유자 정보와 연결된다)
- 개 사진만 있고, EXIF가 제거됐고, 계정과 연결되지 않은 파일이라면 개인정보성이 매우 낮다. 따라서 기기에서 전처리한 뒤 익명 업로드하는 설계가 법적 부담을 가장 크게 줄인다.
- 제15조 제3항 추가적 이용은 권장하지 않는다. "앱 기능 제공"과 "모델 개선 학습"이 "합리적으로 관련"되는지는 해석이 갈리고, 이 조항은 시행령상 요건(관련성, 예측가능성, 불이익 여부, 안전조치)을 스스로 판단하고 공개하는 부담이 있다. 무료 앱은 옵트인 동의 쪽이 더 단순하고 안전하다.
- 제28조의2 가명처리 경로는 "과학적 연구"에 상업 제품 개선이 포함되는지 다툼 여지가 있다. 게다가 얼굴 흐림과 EXIF 제거만으로 개 사진은 사실상 익명정보가 될 가능성이 높다. 그러면 가명정보 절차(결합, 반출 심사, 기록 보관)를 거칠 필요 자체가 없어진다. 가명정보 체계로 들어가기보다는 익명화 후 학습하는 편이 간단하다.
- 동의서에 담을 항목: 목적("견종 분류 모델 학습 및 개선"), 항목(반려동물 사진, 사용자가 고른 견종 라벨), 보유기간(예: 동의 철회 시 또는 수집 후 N년, 학습에 이미 쓰인 모델 가중치는 삭제 대상에서 제외한다는 고지), 거부 권리와 거부해도 불이익이 없다는 점. 이 항목 구성은 PIPA 제15조 제2항의 일반 고지 항목에 근거한 추론이며, 제15조 제2항 원문은 인용하지 못했다.

### Gaps
- law.go.kr 원문을 직접 불러오지 못해 casenote 요약을 사용했다. 조문 요약은 원문 문장을 부분 인용한 것이고, 2026.3.10 개정 내용(법률 제21445호)이 무엇인지는 확인하지 못했다.
- 2023.9.15 시행 개정(정보통신서비스 특례 일원화, 동의 제도 정비)의 세부 내용은 이번에 1차 자료로 확인하지 못했다.
- 생성형 AI 안내서 원문(PDF)의 해당 페이지 문구와 "민감정보·식별자" 관련 문장은 김·장 요약으로만 확인했다.
- 2025~2026년에 PIPC가 이미지 분류용(비생성형) 학습 데이터만 따로 다룬 안내가 있는지는 찾지 못했다.

## (A2) 저작권: 사용자 사진을 학습에 쓰기 위한 이용허락, 국내 약관 사례

### Takeaway
사진 저작권은 촬영한 사용자에게 있다. 학습에 쓰려면 약관이나 동의 화면에서 "모델 학습 목적의 복제·이용" 이용허락을 명시적으로 받아야 한다. 공정위는 2025년 네이버 사례에서 약관에 조항이 있어도 이용자가 충분히 인지할 수 없으면 실질적 동의로 볼 수 없다는 입장을 보였다. 그래서 약관 한 줄로는 부족하고, 업로드 시점의 별도 체크박스로 받는 것이 안전하다.

### Cited Findings
- 공정위는 생성형 AI 개발용 데이터를 수집하면서 저작권자 동의를 받지 않는 행위가 소비자 이익을 해칠 수 있다고 봤다. 또 약관에 데이터 수집 조항이 있어도 이용자가 충분히 인지할 수 없다면 실질적 동의로 볼 수 없다고 했다(네이버 약관, 2025.1). — [뉴스W](https://www.newsw.co.kr/news/articleView.html?idxno=6069)
- 카카오는 2025.12에 약관을 개정해 2026.2.4부터 이용기록과 패턴을 분석·활용할 수 있다고 명시했다. AI 결과물은 AI 기본법에 따라 고지한다는 내용도 넣었다. — [아시아경제](https://www.asiae.co.kr/article/2025122109492128396)
- 2025년 지상파 3사가 뉴스 데이터를 무단으로 AI 학습에 썼다며 네이버를 상대로 저작권 소송을 냈다. 국내에서도 학습 데이터의 저작권 분쟁이 현실화됐다. — [삼성SDS 인사이트](https://www.samsungsds.com/kr/insights/the-laws-businesses-need-to-know-in-the-ai-era.html)

### Inferences
- 문구 예시(초안, 법률 검토 필요): "회원이 '학습에 기여하기'를 켜고 올린 반려동물 사진과 선택한 견종 정보를, 회사가 견종 분류 모델을 학습·평가·개선하는 목적으로 무상·비독점적으로 복제·저장·가공(크롭, 흐림 처리 등)하는 것을 허락합니다. 사진 자체를 외부에 공개하거나 판매하지 않으며, 설정에서 언제든 철회할 수 있습니다. 철회 시 원본 사진은 삭제되나, 이미 학습된 모델에는 개별 사진이 복원 가능한 형태로 남지 않습니다."
- 학습된 가중치에서 개별 사진을 제거할 수 없다는 점은 동의 화면에 미리 밝혀야 한다. 공정위가 말한 "충분한 인지" 기준을 충족하기 위해서다.
- 팀원이나 지인에게 사진을 받을 때는 서면(또는 구글폼) 동의서 한 장에 저작권 이용허락과 개인정보 동의를 함께 받는다. 동의서에는 본인이 찍은 사진이라는 확인과 타인 얼굴이 없다는 확인을 넣는다.

### Gaps
- 국내 반려동물 앱(펫닥, 포인핸드 등)이 사진 학습 이용허락을 실제로 어떻게 문구화했는지 원문을 확인하지 못했다.
- 저작권법상 TDM(텍스트·데이터 마이닝) 면책 조항은 2026.9 기준 국회 통과 여부를 확인하지 못했다.

## (A3) 만 14세 미만 사용자

### Takeaway
PIPA 제22조의2에 따라 만 14세 미만 아동의 개인정보를 처리하려면 법정대리인 동의와 확인 절차가 필요하다. 소규모 앱은 학습 기여 기능을 만 14세 이상에게만 여는 것이 가장 단순하다.

### Cited Findings
- 제22조의2 제1항: "만 14세 미만 아동의 개인정보를 처리하려면 법정대리인의 동의를 받아야" 하고 동의 확인 절차를 거쳐야 한다. — [casenote.kr](https://casenote.kr/법령/개인정보_보호법)

### Inferences
- "학습에 기여하기"를 켤 때 "만 14세 이상입니다" 확인을 받고, 미만이면 기능을 막는다. 아동 사진이 섞이는 것도 얼굴 흐림으로 이중 방어한다.

### Gaps
- 연령 확인 수준(자기 신고로 충분한지)에 대한 PIPC 기준 문구는 확인하지 못했다.

## (A4) 실무 수집 설계(앱 내 옵트인, 기기 내 전처리, 라벨 노이즈, 팀·지인 크라우드소싱, 필요 수량)

### Takeaway
권장 구조: 기본값 OFF인 "학습에 기여하기" 토글 → 기기에서 EXIF 제거·얼굴 흐림·개 영역 크롭 → 계정과 연결되지 않은 익명 ID로 업로드 → 사용자가 고른 견종 라벨과 현재 모델의 예측이 다르면 검수 대기열로 보낸다. 가명정보 가이드라인이 인정하는 필터링·인페인팅 기법을 기기에서 적용하면 서버에는 개인정보성이 낮은 데이터만 도착한다.

### Cited Findings
- 이미지 가명처리 기법(필터링, 암호화, 얼굴 합성, 인페인팅)은 PIPC 가이드라인에 예시로 나와 있다. — [PIPC 비정형데이터 가명처리 기준](https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS074&mCode=C020010000&nttId=9899)
- Meta는 DINOv2 학습 데이터를 만들면서 "blurring identifiable faces"(식별 가능한 얼굴 흐림)를 후처리로 적용했다. 대형 연구소도 이미지 학습 데이터에 얼굴 흐림을 표준 전처리로 쓴다는 사례다. — [DINOv2 논문](https://arxiv.org/html/2304.07193)
- EXIF의 GPS를 지우면 자택 위치 노출이 막힌다. — [PIPC 홍보물](https://www.innovation.go.kr/ucms/bbs/B0000060/view.do?nttId=17555&menuNo=300240&searchType=4&pageIndex=1)

### Inferences
- 기기 내 구현(최소):
  1. 원본 파일은 올리지 않는다. 디코딩한 픽셀을 다시 JPEG로 인코딩하면 EXIF가 통째로 빠진다. Android에서는 `Bitmap.compress`를 쓴다.
  2. 사람 얼굴은 ML Kit Face Detection이나 MediaPipe Face Detector로 찾아 흐린다.
  3. 개 검출 박스로 크롭하면 배경(집 내부)이 대부분 잘려 나간다.
- 라벨 노이즈: 사용자는 믹스견을 순종으로 고르거나 비슷한 견종을 혼동한다. 다음 두 가지로 줄인다.
  - "모름/믹스" 선택지를 꼭 둔다.
  - 모델 예측과 사용자 라벨이 모두 확신 높게 일치하는 샘플만 자동 채택하고, 불일치 샘플은 팀이 검수한다.
- 팀·지인 수집: 구글폼 동의서(이름, 본인 촬영 확인, 이용 목적, 보유기간, 철회 방법)와 업로드 폴더를 함께 쓰면 비용이 거의 들지 않는다. 다만 견종이 흔한 몇 종(말티즈, 푸들, 포메라니안 등 국내 인기견)에 치우친다.
- 필요 수량(추정이며 출처 없음): 사전학습 백본을 동결하고 헤드만 학습하는 경우 클래스당 약 50~200장이면 쓸 만한 수준이 나오는 것이 흔한 경험칙이다. 템플릿 수가 10~20종이면 1,000~4,000장 규모다. 실제 필요량은 검증셋 곡선으로 판단한다.

### Gaps
- 국내 앱의 옵트인 학습 기여율(몇 % 사용자가 켜는지)에 대한 공개 통계는 찾지 못했다.
- 클래스당 필요 샘플 수는 신뢰할 만한 출처를 인용하지 못했다(위 수치는 추정).

## (B1) ImageNet 사전학습 가중치를 상업용 앱에 쓰는 것의 법적 상태

### Takeaway
ImageNet 이용약관은 "non-commercial research and educational purposes"로 제한된다. 하지만 이 약관은 데이터셋에 접근하는 연구자를 구속하는 계약이고, 학습된 가중치가 그 제한을 상속하는지에 대한 판례나 권위 있는 결론은 없다. torchvision은 명시적으로 이 판단을 사용자에게 넘긴다. 업계에서는 ImageNet 사전학습 백본(MobileNet, EfficientNet 등)이 상업 제품에 널리 쓰이고 있다. 구글 MediaPipe의 공식 분류 모델도 ImageNet으로 학습됐다. 실무 위험은 낮지만 0은 아니다.

### Cited Findings
- ImageNet Terms of Access: "Researcher shall use the Database only for non-commercial research and educational purposes." — [image-net.org](https://www.image-net.org/download.php)
- torchvision 공식 문서: "The pre-trained models provided in this library may have their own licenses or terms and conditions derived from the dataset used for training. It is your responsibility to determine whether you have permission to use the models for your use case." — [PyTorch docs](https://docs.pytorch.org/vision/main/models.html)
- torchvision 코드 자체는 BSD 라이선스다. 가중치의 상업 이용 문의는 GitHub 이슈로 반복 제기됐다. — [pytorch/vision #2597](https://github.com/pytorch/vision/issues/2597), [PyTorch Forums](https://discuss.pytorch.org/t/pre-trained-models-license/38647)
- Keras 가중치는 MIT 라이선스이지만 ImageNet에서 파생됐다는 점이 이슈로 제기됐다. 확인 가능한 범위에서 메인테이너의 명시적 답변은 없고 이슈는 닫혀 있다. — [keras-team/keras #13362](https://github.com/keras-team/keras/issues/13362)
- 학술 논문의 평가: 모델이 학습 데이터의 2차적저작물인지에 대한 논의는 "yet unresolved"이며, 입법과 판례가 불명확하다. — [arXiv 2204.04950](https://arxiv.org/pdf/2204.04950)
- timm은 일부 가중치(Instagram 사전학습, semi-supervised ImageNet)가 CC BY-NC 4.0이라 상업 이용이 안 된다고 모델별로 표기한다. 즉 라이선스는 가중치마다 확인해야 한다. — [timm PyPI](https://pypi.org/project/timm/0.9.1/)
- 구글 MediaPipe Image Classifier의 공식 모델 EfficientNet-Lite0/Lite2는 "trained using ImageNet"이며 int8 Lite0 기준 Pixel 6 CPU에서 10.08ms다. 문서 코드는 Apache 2.0, 콘텐츠는 CC BY 4.0이다. — [MediaPipe Image Classifier](https://developers.google.com/edge/mediapipe/solutions/vision/image_classifier)

### Inferences
- 구글, 파이토치 같은 대형 사업자가 ImageNet 학습 가중치를 상업용 SDK의 기본 모델로 배포하고 있고, 이를 문제 삼은 소송 사례도 찾지 못했다. 따라서 무료 상업 앱에서 ImageNet 백본을 파인튜닝해 쓰는 것은 업계 통상 관행 범위에 있다고 보인다. 위험도는 낮음으로 판단한다.
- 남는 위험은 두 가지다. ImageNet 약관 위반은 계약상 이론적 위험인데, 앱 개발팀은 약관 당사자가 아니다. 그리고 ImageNet 이미지 원저작자의 저작권 주장인데, 가중치에서 개별 이미지를 복원할 수 없어 실현 가능성이 낮다.
- 한국에서 이 쟁점을 다룬 판례나 PIPC·문체부 해석은 찾지 못했다.
- 가장 깔끔하게 가려면 가중치 라이선스가 명시적으로 Apache 2.0이고, 데이터 약관 문제를 제공자가 정리한 모델을 쓴다(B2 참고).

### Gaps
- 이 쟁점만을 다룬 법원 판결은 찾지 못했다(미국 Getty v. Stability, NYT v. OpenAI 등은 생성형·저작권 쟁점이고 가중치 라이선스 상속 문제가 아니며, 이번에 직접 확인하지 않았다).
- Keras 이슈의 최종 메인테이너 답변 원문은 페이지에서 보이지 않았다.

## (B2) 상업적으로 더 깔끔한 백본과 모바일 적합성

### Takeaway
- DINOv2 ViT-S/14(21M 파라미터)는 가중치가 Apache 2.0으로 명시돼 있고 모바일에서 실행 가능한 크기다. 다만 학습 데이터 LVD-142M은 ImageNet-22k/1k를 검색 시드로 써서 웹 이미지를 모았으므로 "ImageNet과 완전 무관"하지는 않다.
- SigLIP 2는 체크포인트가 Apache 2.0(소프트웨어)과 CC-BY 4.0(기타 자료)이다. 가장 작은 B/16·B/32(86M)도 모바일에는 무거운 편이다.
- Apple MobileCLIP/MobileCLIP2는 모바일에 최적화돼 있지만 가중치 라이선스가 연구 전용이라 상업용으로 쓸 수 없다.

### Cited Findings
- DINOv2: "DINOv2 code and model weights are released under the Apache License 2.0." ViT-S/14 distilled는 21M 파라미터다. Cell-DINO와 XRay-DINO는 비상업 라이선스라 제외해야 한다. — [facebookresearch/dinov2](https://github.com/facebookresearch/dinov2)
- LVD-142M 구성: 큐레이션 소스로 "ImageNet-22k, the train split of ImageNet-1k, Google Landmarks and several fine-grained datasets"를 썼고, 공개 웹 크롤 이미지 1.2B장에서 이들과 유사한 이미지를 검색해 142M장을 만들었다. 이 과정에서 얼굴 흐림, NSFW 필터링, 중복 제거를 거쳤다. — [DINOv2 논문](https://arxiv.org/html/2304.07193)
  - 요약 모델은 큐레이션 데이터셋이 직접 포함되지 않고 시드로만 쓰였다고 정리했다. 그러나 논문 Table 15에는 ImageNet-22k가 "as is"로 포함된 것으로 기억한다(확인 필요).
- SigLIP 2 모델 크기: ViT-B 86M(B/16, B/32), L 303M, So400m 400M, g 1B. 라이선스: "All software is licensed under the Apache License, Version 2.0" / "All other materials are licensed under the Creative Commons Attribution 4.0 International License (CC-BY)". — [big_vision SigLIP2 README](https://github.com/google-research/big_vision/blob/main/big_vision/configs/proj/image_text/README_siglip2.md)
- SigLIP2 base 체크포인트 파일은 약 354.8MB(fp32)다. — [검색 요약, Tenzro 모델 페이지](https://www.tenzro.com/models/siglip2-base-224)(2차 출처)
- Apple MobileCLIP LICENSE_MODELS: "Research Purposes ... does not include any commercial exploitation, product development or use in any commercial product or service." 파생 모델에도 같은 제한이 붙는다. — [apple/ml-mobileclip LICENSE_MODELS](https://github.com/apple/ml-mobileclip/blob/main/LICENSE_MODELS)
- MobileCLIP2의 학습 데이터 DFNDR-2B는 DataComp(CC-BY-4.0 메타데이터)의 부분집합이다. 데이터 메타데이터 라이선스와 별개로 가중치는 Apple 연구 전용 라이선스다. — [HF apple/DFNDR-2B](https://huggingface.co/datasets/apple/DFNDR-2B)
- timm에는 모델별 라이선스가 표기되며 비상업(CC BY-NC) 가중치가 섞여 있다. — [timm PyPI](https://pypi.org/project/timm/0.9.1/)

### Inferences
- 모바일 적합성 순위(추론):
  1. MediaPipe EfficientNet-Lite0: int8 약 5MB급, 10ms. 단 ImageNet 학습.
  2. DINOv2 ViT-S/14: 21M, int8 기준 약 22MB, 중급 폰에서 수십~100ms대로 추정.
  3. SigLIP2 B/16: 86M 비전 인코더, int8 기준 약 90MB. 템플릿 앱 용량으로는 부담.
- "깔끔함" 순위(추론): SigLIP2 ≈ DINOv2(가중치에 명시적 Apache 2.0, 대형 제공자) > torchvision·Keras ImageNet 가중치(라이선스 판단을 사용자에게 넘김) > MobileCLIP(상업 불가).
  - DINOv2와 SigLIP의 학습 데이터도 웹 크롤 기반이라 원저작권 이슈가 이론적으로는 남는다. 그래도 가중치 자체에 상업 이용 가능 라이선스가 명시돼 있다는 점이 ImageNet 가중치와의 핵심 차이다.
- 추천: DINOv2 ViT-S/14(Apache 2.0) 백본을 동결하고, 자체 수집 사진으로 선형 헤드나 k-NN만 학습한다. 적은 데이터로도 잘 동작하고 라이선스 설명도 쉽다.
- 배포할 때는 LICENSE와 NOTICE를 앱 오픈소스 고지 화면에 포함한다(Apache 2.0 요건).

### Gaps
- OpenCLIP(LAION 학습) 가중치의 라이선스 표기(대체로 MIT 코드, 가중치 표기는 모델 카드마다 다름)는 이번에 직접 확인하지 못했다. LAION 데이터 자체는 URL 목록이라 원저작권 문제가 따로 있다.
- MobileNetV4나 기타 구글 모델 중 ImageNet 외 데이터로 학습되고 Apache 2.0인 모바일 백본이 있는지 확인하지 못했다.
- DINOv2 Table 15의 "as is" 포함 여부는 직접 확인이 필요하다.

## (B3) 제로샷 대안(CLIP·SigLIP류로 학습 데이터 없이 견종 분류)

### Takeaway
SigLIP 2는 Apache 2.0이라 상업적으로 쓸 수 있고, "a photo of a {견종}" 텍스트 임베딩을 미리 계산해 두면 앱에는 이미지 인코더만 넣으면 된다. 가장 작은 모델도 비전 인코더가 약 86M 파라미터(fp32 기준 수백 MB)라서, 수 MB 단위인 MobileNet 계열보다 훨씬 무겁다. 현실적인 절충안은 두 가지다.
- SigLIP2로 초기 데이터를 자동 라벨링하는 데 서버나 개발 PC에서만 쓰고, 경량 모델로 증류한다.
- DINOv2-S에 소수 샘플로 k-NN을 붙인다.

### Cited Findings
- SigLIP 2의 소프트웨어는 Apache 2.0, 기타 자료는 CC-BY 4.0이다. 가장 작은 모델은 ViT-B 86M이다. — [big_vision README](https://github.com/google-research/big_vision/blob/main/big_vision/configs/proj/image_text/README_siglip2.md)
- SigLIP2 base 체크포인트는 약 354.8MB다. — [Tenzro](https://www.tenzro.com/models/siglip2-base-224)(2차 출처)
- MobileCLIP2는 모바일용으로 설계됐지만 가중치가 연구 전용이라 상업용으로 쓸 수 없다. — [LICENSE_MODELS](https://github.com/apple/ml-mobileclip/blob/main/LICENSE_MODELS)

### Inferences
- 견종 템플릿 수가 적고(대략 10~30종) 정확도 요구가 "비슷한 템플릿 고르기" 수준이면, SigLIP2 제로샷으로도 쓸 만할 가능성이 높다.
- 앱 용량 제약을 고려하면 다음 순서가 가장 효율적이다.
  1. SigLIP2를 오프라인 라벨러로 쓴다. 사용자 사진에 가짜 라벨을 달고, 사용자 선택 라벨과 교차검증한다.
  2. 그 결과를 DINOv2-S나 경량 CNN 헤드로 증류해 온디바이스에 배포한다.
- 증류해 만든 모델이 교사 모델 라이선스의 영향을 받을 수 있다. Apache 2.0은 파생물에도 허용적이라 문제는 없다. MobileCLIP 같은 연구 전용 모델을 교사로 쓰면 증류 모델도 오염될 수 있다(Apple 라이선스는 파생 모델까지 제한한다).

### Gaps
- SigLIP2 B/16의 스탠퍼드 도그스(120견종) 제로샷 정확도 수치는 찾지 못했다.
- 모바일(int8 TFLite/LiteRT)에서 SigLIP2 B/16의 실측 지연시간 자료는 찾지 못했다.
