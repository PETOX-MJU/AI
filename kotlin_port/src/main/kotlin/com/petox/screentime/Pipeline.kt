package com.petox.screentime

/**
 * Python `screentime/pipeline.py` 이식 — 순수 함수들을 묶는 `analyze` 진입점 (계획서 6.3).
 *
 * 호출자가 입력을 전달하며 함수가 DB나 시스템 현재 시각을 직접 읽지 않는다.
 * 같은 입력과 같은 [RULES_VERSION]은 항상 같은 출력을 반환한다.
 */

/**
 * 주간 분석 → 미션 판정 → 다음 목표 제안 → 근거 설명 순서로 조립한다.
 *
 * 데이터 부족은 예외가 아니라 정상 결과다. [WeekStatus]와 `insights`가 이유를 알린다.
 */
fun analyze(request: AnalysisInput): AnalysisOutput {
    val metrics = analyzeWeek(request, defaultMissionEvaluator)
    return AnalysisOutput(
        weekStatus = getWeekStatus(request),
        metrics = metrics,
        missionResults = missionResults(request, defaultMissionEvaluator),
        proposals = proposeTargets(request, metrics),
        insights = renderInsights(
            metrics,
            request.profile,
            currentDailyTargetMs = request.currentDailyTargetMs,
            currentNightTargetMs = request.currentNightTargetMs,
            basisWeek = request.weekStart,
        ),
        rulesVersion = RULES_VERSION,
    )
}
