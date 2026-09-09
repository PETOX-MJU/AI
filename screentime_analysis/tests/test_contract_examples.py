"""스키마·예제와 구현의 일치 (계획서 Task 5).

예제 출력은 손으로 쓰지 않는다. 실제 analyze 실행값과 다르면 실패한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from screentime import AnalysisInput, AnalysisOutput, analyze

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
EXAMPLES = CONTRACTS / "examples"


def load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["complete-week", "insufficient-data"])
def test_example_output_matches_implementation(name):
    payload = load(f"{name}.input.json")
    expected = load(f"{name}.output.json")
    actual = analyze(AnalysisInput.model_validate(payload)).model_dump(mode="json")
    assert actual == expected


def test_complete_week_example():
    """계획서 Task 5가 지정한 계약 테스트."""
    payload = load("complete-week.input.json")
    expected = load("complete-week.output.json")
    actual = analyze(AnalysisInput.model_validate(payload)).model_dump(mode="json")
    assert actual == expected


def test_complete_week_expected_values():
    """F01의 기대값이 문서와 같은지 못 박는다."""
    result = load("complete-week.output.json")
    assert result["week_status"] == "ready"
    assert result["metrics"]["selected_daily_mean_ms"] == 120 * 60_000
    assert result["metrics"]["selected_night_mean_ms"] == 30 * 60_000
    targets = {p["kind"]: p["target_ms"] for p in result["proposals"]}
    assert targets == {"daily": 108 * 60_000, "night": 27 * 60_000}


def test_insufficient_example_makes_no_targets():
    """F04: 기준선이 없으면 목표를 만들지 않는다."""
    result = load("insufficient-data.output.json")
    assert result["week_status"] == "insufficient_data"
    assert result["proposals"] == []
    assert result["metrics"]["selected_total_ms"] is None


@pytest.mark.parametrize(
    ("filename", "model"),
    [("input.schema.json", AnalysisInput), ("output.schema.json", AnalysisOutput)],
)
def test_schema_matches_model(filename, model):
    stored = json.loads((CONTRACTS / filename).read_text(encoding="utf-8"))
    assert stored == model.model_json_schema()


def test_fixtures_match_implementation():
    """FE 대조용 fixture가 실제 구현과 같은 값을 담고 있는지 확인한다."""
    import datetime as dt

    from screentime.missions import reduce_target
    from screentime.windows import daily_window, night_windows

    fixtures = json.loads((CONTRACTS / "fixtures.json").read_text(encoding="utf-8"))
    profile = AnalysisInput.model_validate(load("complete-week.input.json")).profile

    for case in fixtures["night_windows"]:
        pre, post = night_windows(dt.date.fromisoformat(case["anchor_date"]), profile)
        assert pre.start_ms == case["expected_pre_bed"]["start_ms"]
        assert post.end_ms == case["expected_after_bed"]["end_ms"]

    ny = profile.model_copy(update={"timezone": "America/New_York"})
    for case in fixtures["daily_window_dst"]:
        window = daily_window(dt.date.fromisoformat(case["date"]), ny)
        assert window.duration_ms == case["expected_duration_ms"]

    for case in fixtures["reduce_target"]:
        assert reduce_target(case["reference_ms"], case["final_goal_ms"]) == case["expected_ms"]
