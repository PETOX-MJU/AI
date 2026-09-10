"""순수 함수들을 묶는 ``analyze`` 진입점 (계획서 6.3).

호출자가 입력을 전달하며 함수가 DB나 시스템 현재 시각을 직접 읽지 않는다.
같은 입력과 같은 ``rules_version``은 항상 같은 출력을 반환한다.
"""

from __future__ import annotations

from .analytics import analyze_week, get_week_status, mission_results
from .missions import propose_targets
from .models import RULES_VERSION, AnalysisInput, AnalysisOutput
from .narratives import render_insights


def analyze(request: AnalysisInput) -> AnalysisOutput:
    """주간 분석 → 미션 판정 → 다음 목표 제안 → 근거 설명 순서로 조립한다.

    데이터 부족은 예외가 아니라 정상 결과다. ``week_status``와 ``insights``가 이유를 알린다.
    """
    metrics = analyze_week(request)
    return AnalysisOutput(
        week_status=get_week_status(request),
        metrics=metrics,
        mission_results=mission_results(request),
        proposals=propose_targets(request, metrics),
        insights=render_insights(
            metrics,
            request.profile,
            current_daily_target_ms=request.current_daily_target_ms,
            current_night_target_ms=request.current_night_target_ms,
            basis_week=request.week_start,
        ),
        rules_version=RULES_VERSION,
    )
