"""펫톡스 스크린타임 분석 라이브러리.

BE 진입점::

    from screentime import AnalysisInput, AnalysisOutput, analyze

    result = analyze(AnalysisInput.model_validate(payload))
    return result.model_dump(mode="json")

무상태 순수 계산이다. DB·네트워크·시스템 현재 시각을 읽지 않으며 입력을 저장하지 않는다.
"""

from .models import AnalysisInput, AnalysisOutput

__all__ = ["AnalysisInput", "AnalysisOutput", "analyze"]
__version__ = "0.1.0"


def __getattr__(name: str):  # pragma: no cover - 순환 임포트 회피용 지연 로딩
    if name == "analyze":
        from .pipeline import analyze

        return analyze
    raise AttributeError(name)
