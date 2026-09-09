"""데모 CLI (계획서 Task 6). 별도 프로세스에서 실행해 결정성을 확인한다."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "contracts" / "examples" / "complete-week.input.json"


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "screentime", *args],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )


def test_cli_writes_output_and_exits_zero(tmp_path):
    out = tmp_path / "result.json"
    proc = run(["--input", str(EXAMPLE), "--output", str(out)])
    assert proc.returncode == 0, proc.stderr
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["week_status"] == "ready"
    assert {p["kind"]: p["target_ms"] for p in result["proposals"]} == {
        "daily": 108 * 60_000,
        "night": 27 * 60_000,
    }


def test_cli_is_deterministic_across_processes(tmp_path):
    """같은 입력은 별도 프로세스에서도 같은 결과를 낸다. 실제 현재 시각을 쓰지 않는다."""
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    assert run(["--input", str(EXAMPLE), "--output", str(first)]).returncode == 0
    assert run(["--input", str(EXAMPLE), "--output", str(second)]).returncode == 0
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")


def test_cli_rejects_invalid_input_with_exit_two(tmp_path):
    bad = tmp_path / "bad.json"
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["week_start"] = "2026-09-08"  # 화요일
    bad.write_text(json.dumps(payload), encoding="utf-8")

    out = tmp_path / "never.json"
    proc = run(["--input", str(bad), "--output", str(out)])
    assert proc.returncode == 2
    assert not out.exists()
    assert "입력 검증 실패" in proc.stderr


def test_cli_error_does_not_leak_user_values(tmp_path):
    """실패 메시지는 필드 위치와 오류 유형만 담는다."""
    bad = tmp_path / "bad.json"
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    secret = "com.private.verysecretapp"
    payload["profile"]["target_packages"] = [secret, secret]
    bad.write_text(json.dumps(payload), encoding="utf-8")

    proc = run(["--input", str(bad), "--output", str(tmp_path / "never.json")])
    assert proc.returncode == 2
    assert secret not in proc.stderr
    assert secret not in proc.stdout
    assert "profile" in proc.stderr  # 위치는 알려준다


def test_cli_reports_malformed_json_without_echoing_it(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"as_of_ms": 1, "secret": "do-not-echo"', encoding="utf-8")
    proc = run(["--input", str(bad), "--output", str(tmp_path / "never.json")])
    assert proc.returncode == 2
    assert "do-not-echo" not in proc.stderr
    assert "JSON 구문 오류" in proc.stderr


def test_cli_missing_file(tmp_path):
    proc = run(["--input", str(tmp_path / "nope.json"), "--output", str(tmp_path / "out.json")])
    assert proc.returncode == 2
