"""입력·출력 Pydantic 모델과 검증 규칙 (계획서 6절).

설계 원칙:
- 모든 모델은 ``extra="forbid"``다. 오탈자를 조용히 삼키면 BE 연동에서 원인을 찾기 어렵다.
- 시간 단위는 정수 밀리초, 시각은 UTC epoch milliseconds다. 화면 표시용 분 변환은 하지 않는다.
- 데이터가 없다는 이유로 0을 만들지 않는다. 확인 불가는 ``None``이고 확인된 0은 빈 배열이다.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1"
# 규칙이 바뀌면 올린다. 같은 입력과 같은 rules_version은 항상 같은 출력을 낸다.
RULES_VERSION = "2026-09-10.1"
MINUTE_MS = 60_000
MAX_DURATION_MS = 2**53 - 1
# 시각 입력을 상식적인 범위로 묶는다. 초 단위 값을 밀리초로 잘못 보내는 실수를 잡아준다.
EPOCH_MIN_MS = 946_684_800_000  # 2000-01-01T00:00:00Z
EPOCH_MAX_MS = 4_102_444_800_000  # 2100-01-01T00:00:00Z
MAX_ANCHOR_DATES = 21
MAX_APPS_PER_WINDOW = 200

Quality = Literal["complete", "partial", "unavailable"]
WindowKind = Literal["daily", "pre_bed", "after_bed"]
MissionKind = Literal["daily", "night"]
MissionStatus = Literal["in_progress", "succeeded", "failed", "unknown", "not_applicable"]
WeekStatus = Literal["in_progress", "awaiting_data", "ready", "insufficient_data"]


def _reject_bool(value: Any) -> Any:
    """``bool``은 ``int``의 하위 타입이라 Pydantic이 그냥 통과시킨다. 명시적으로 막는다."""
    if isinstance(value, bool):
        raise ValueError("bool은 정수 필드에 사용할 수 없습니다")
    return value


DurationMs = Annotated[int, BeforeValidator(_reject_bool), Field(ge=0, le=MAX_DURATION_MS)]
EpochMs = Annotated[int, BeforeValidator(_reject_bool), Field(ge=EPOCH_MIN_MS, le=EPOCH_MAX_MS)]
Version = Annotated[int, BeforeValidator(_reject_bool), Field(ge=0)]
Count = Annotated[int, BeforeValidator(_reject_bool), Field(ge=0)]
ClockTime = Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]


class Strict(BaseModel):
    """모든 모델의 공통 설정."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Window(Strict):
    """``[start_ms, end_ms)`` 반열린 구간."""

    start_ms: EpochMs
    end_ms: EpochMs

    @model_validator(mode="after")
    def _ordered(self) -> Window:
        if self.start_ms >= self.end_ms:
            raise ValueError("start_ms는 end_ms보다 작아야 합니다")
        return self

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


class Profile(Strict):
    """사용자 설정 스냅샷. 목표 입력은 분 단위 정수다."""

    version: Version
    timezone: str = Field(min_length=1)
    target_packages: list[str] = Field(min_length=1)
    purposes: dict[str, str] = Field(default_factory=dict)
    weekday_bed: ClockTime
    weekday_wake: ClockTime
    weekend_bed: ClockTime
    weekend_wake: ClockTime
    temporary_daily_ms: DurationMs
    temporary_night_ms: DurationMs
    final_daily_ms: DurationMs
    final_night_ms: DurationMs
    effective_from: dt.date

    @model_validator(mode="after")
    def _check(self) -> Profile:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"알 수 없는 IANA 시간대입니다: {self.timezone}") from exc

        if len(set(self.target_packages)) != len(self.target_packages):
            raise ValueError("target_packages에 중복이 있습니다")
        if any(not p for p in self.target_packages):
            raise ValueError("target_packages에 빈 문자열이 있습니다")

        for name in ("temporary_daily_ms", "temporary_night_ms", "final_daily_ms", "final_night_ms"):
            if getattr(self, name) % MINUTE_MS:
                raise ValueError(f"{name}는 분 단위(60000ms의 배수)여야 합니다")

        # 임시 목표는 최종 목표보다 느슨하다. 반대면 온보딩 입력이 잘못된 것이다.
        if self.temporary_daily_ms < self.final_daily_ms:
            raise ValueError("temporary_daily_ms는 final_daily_ms 이상이어야 합니다")
        if self.temporary_night_ms < self.final_night_ms:
            raise ValueError("temporary_night_ms는 final_night_ms 이상이어야 합니다")
        return self

    def is_weekend_anchor(self, anchor_date: dt.date) -> bool:
        """야간 일정은 밤을 시작하는 저녁이 속한 날짜로 고른다. 토·일 저녁이 주말이다."""
        return anchor_date.weekday() >= 5

    def bed_wake_for(self, anchor_date: dt.date) -> tuple[str, str]:
        if self.is_weekend_anchor(anchor_date):
            return self.weekend_bed, self.weekend_wake
        return self.weekday_bed, self.weekday_wake


class AppDuration(Strict):
    package_name: str = Field(min_length=1)
    duration_ms: DurationMs


class WindowAggregate(Strict):
    """FE가 정규화한 한 구간의 앱별 집계."""

    anchor_date: dt.date
    kind: WindowKind
    start_ms: EpochMs
    end_ms: EpochMs
    observed_until_ms: EpochMs
    quality: Quality
    reason_codes: list[str] = Field(default_factory=list)
    profile_version: Version
    apps: list[AppDuration] | None
    measurement_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> WindowAggregate:
        if self.start_ms >= self.end_ms:
            raise ValueError("start_ms는 end_ms보다 작아야 합니다")
        if not (self.start_ms <= self.observed_until_ms <= self.end_ms):
            raise ValueError("observed_until_ms는 [start_ms, end_ms] 안에 있어야 합니다")

        if self.quality == "unavailable":
            if self.apps is not None:
                raise ValueError("unavailable 집계의 apps는 null이어야 합니다")
        elif self.apps is None:
            raise ValueError(f"{self.quality} 집계의 apps는 배열이어야 합니다 (빈 배열이 확인된 0)")

        if self.quality == "complete" and self.observed_until_ms != self.end_ms:
            raise ValueError("complete 집계는 observed_until_ms == end_ms 여야 합니다")

        if self.apps is not None:
            if len(self.apps) > MAX_APPS_PER_WINDOW:
                raise ValueError(f"한 구간의 앱은 {MAX_APPS_PER_WINDOW}개를 넘을 수 없습니다")
            names = [a.package_name for a in self.apps]
            if len(set(names)) != len(names):
                raise ValueError("같은 집계 안에 package_name 중복이 있습니다")
            span = self.end_ms - self.start_ms
            # 개별 앱은 구간 길이를 넘을 수 없다. 멀티윈도우 때문에 앱들의 합계는 넘을 수 있다.
            for app in self.apps:
                if app.duration_ms > span:
                    raise ValueError(f"{app.package_name}의 사용 시간이 구간 길이를 초과합니다")
        return self

    @property
    def key(self) -> tuple[dt.date, str, int, str]:
        return (self.anchor_date, self.kind, self.profile_version, self.measurement_version)

    def total_ms(self, packages: set[str] | None = None) -> int | None:
        """``packages``가 None이면 전체 앱 합계. 집계 불가면 None."""
        if self.apps is None:
            return None
        if packages is None:
            return sum(a.duration_ms for a in self.apps)
        return sum(a.duration_ms for a in self.apps if a.package_name in packages)


class Mission(Strict):
    """실제로 발급된 미션 스냅샷. 현재 설정으로 과거를 재평가하지 않는다."""

    id: str = Field(min_length=1)
    anchor_date: dt.date
    kind: MissionKind
    target_ms: DurationMs
    profile_version: Version
    accepted_at_ms: EpochMs
    window_start_ms: EpochMs
    window_end_ms: EpochMs

    @model_validator(mode="after")
    def _check(self) -> Mission:
        if self.window_start_ms >= self.window_end_ms:
            raise ValueError("window_start_ms는 window_end_ms보다 작아야 합니다")
        return self


class Proposal(Strict):
    """추천이며 활성 미션이 아니다. 수락·저장은 BE 책임이다."""

    kind: MissionKind
    target_ms: DurationMs | None
    reason_code: str
    basis_week: dt.date
    profile_version: Version
    rules_version: str


class MissionResult(Strict):
    mission_id: str
    status: MissionStatus
    observed_ms: DurationMs | None
    evaluated_at_ms: EpochMs


class DayMetrics(Strict):
    date: dt.date
    daily_quality: Quality | None
    pre_bed_quality: Quality | None
    after_bed_quality: Quality | None
    all_apps_ms: int | None
    selected_ms: int | None
    pre_bed_ms: int | None
    after_bed_ms: int | None


class AppMetrics(Strict):
    package_name: str
    is_target: bool
    total_ms: int | None
    share_pct: float | None
    night_total_ms: int | None
    night_share_pct: float | None
    delta_ms: int | None
    delta_pct: float | None


class Comparison(Strict):
    comparable: bool
    reason: str | None
    selected_delta_ms: int | None
    selected_delta_pct: float | None
    all_apps_delta_ms: int | None


class WeeklyMetrics(Strict):
    valid_days: Count
    valid_nights: Count
    all_apps_total_ms: int | None
    selected_total_ms: int | None
    selected_daily_mean_ms: float | None
    selected_night_mean_ms: float | None
    pre_bed_total_ms: int | None
    after_bed_total_ms: int | None
    daily_success_count: Count
    daily_evaluable_count: Count
    night_success_count: Count
    night_evaluable_count: Count
    per_day: list[DayMetrics]
    per_app: list[AppMetrics]
    comparison: Comparison


class Insight(Strict):
    code: str
    evidence: dict[str, int | float | str | None]
    text: str
    source: Literal["template"] = "template"


class AnalysisInput(Strict):
    schema_version: Literal["1"] = SCHEMA_VERSION
    as_of_ms: EpochMs
    last_collection_attempt_ms: EpochMs | None
    week_start: dt.date
    profile: Profile
    aggregates: list[WindowAggregate]
    missions: list[Mission]
    current_daily_target_ms: DurationMs | None
    current_night_target_ms: DurationMs | None

    @model_validator(mode="after")
    def _check(self) -> AnalysisInput:
        if self.week_start.weekday() != 0:
            raise ValueError("week_start는 월요일이어야 합니다")

        keys = [a.key for a in self.aggregates]
        if len(set(keys)) != len(keys):
            raise ValueError("aggregates에 (anchor_date, kind, profile_version, measurement_version) 중복이 있습니다")

        anchors = {a.anchor_date for a in self.aggregates} | {m.anchor_date for m in self.missions}
        if len(anchors) > MAX_ANCHOR_DATES:
            raise ValueError(f"anchor date는 최대 {MAX_ANCHOR_DATES}개까지 허용합니다")

        versions = {a.measurement_version for a in self.aggregates}
        if len(versions) > 1:
            raise ValueError("한 요청의 measurement_version은 하나여야 합니다")

        for agg in self.aggregates:
            if agg.profile_version != self.profile.version:
                raise ValueError(f"집계 profile_version({agg.profile_version})이 프로필과 다릅니다")
            # complete는 이미 끝난 구간에만 붙일 수 있다. 진행 중 구간의 complete를 막는다.
            if agg.quality == "complete" and agg.end_ms > self.as_of_ms:
                raise ValueError("아직 끝나지 않은 구간을 complete로 표시할 수 없습니다")

        mission_ids = [m.id for m in self.missions]
        if len(set(mission_ids)) != len(mission_ids):
            raise ValueError("mission.id 중복이 있습니다")
        mission_keys = [(m.anchor_date, m.kind) for m in self.missions]
        if len(set(mission_keys)) != len(mission_keys):
            raise ValueError("(anchor_date, kind)가 같은 미션이 둘 이상입니다")
        for mission in self.missions:
            if mission.profile_version != self.profile.version:
                raise ValueError(f"미션 profile_version({mission.profile_version})이 프로필과 다릅니다")

        return self

    @property
    def measurement_version(self) -> str:
        return next(iter({a.measurement_version for a in self.aggregates}), "unknown")

    @property
    def target_packages(self) -> set[str]:
        return set(self.profile.target_packages)


class AnalysisOutput(Strict):
    schema_version: Literal["1"] = SCHEMA_VERSION
    week_status: WeekStatus
    metrics: WeeklyMetrics
    mission_results: list[MissionResult]
    proposals: list[Proposal]
    insights: list[Insight]
    rules_version: str
