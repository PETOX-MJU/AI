"""털색·종·털길이로 한국어 이름을 추천한다.

VLM 없이 처리하는 부분이다. 모델을 부르지 않으므로 오프라인에서 즉시 동작하고
결과가 일정하다. 앱에서는 이 표를 Kotlin 으로 옮긴다.
"""

BY_COLOR = {
    "검정": ["까미", "깜지", "흑곰", "먹물"],
    "흰색": ["구름", "뽀삐", "설이", "하양"],
    "회색": ["재구", "먼지", "안개", "회오리"],
    "갈색": ["초코", "밤톨", "누렁", "곰돌"],
    "황금색": ["보리", "황금", "단추", "노랑"],
    "크림색": ["크림", "우유", "콩고물", "모카"],
    "주황색": ["당근", "귤이", "노을", "홍시"],
}

BY_SPECIES = {
    "개": ["멍구", "댕댕", "복실"],
    "고양이": ["나비", "냥이", "쫀득"],
    "기타": ["몽이", "동글", "포롱"],
}

BY_COAT = {
    "장모": ["뭉치", "솜사탕", "털뭉치"],
    "곱슬": ["뽀글", "라면", "꼬불"],
    "단모": [],
}


def suggest(species: str | None, main_color: str | None, coat: str | None, limit: int = 3) -> list[str]:
    """색 → 종 → 털길이 순으로 채운다. 색에서 나온 이름이 가장 잘 맞는다."""
    pool: list[str] = []
    for source in (BY_COLOR.get(main_color or "", []), BY_SPECIES.get(species or "", []), BY_COAT.get(coat or "", [])):
        for name in source:
            if name not in pool:
                pool.append(name)

    if not pool:  # 분석이 전부 실패해도 빈 목록을 주지 않는다
        pool = BY_SPECIES["기타"]

    return pool[:limit]


if __name__ == "__main__":
    for args in (("개", "황금색", "단모"), ("고양이", "검정", "장모"), (None, None, None)):
        print(f"{str(args):<32} -> {suggest(*args)}")
