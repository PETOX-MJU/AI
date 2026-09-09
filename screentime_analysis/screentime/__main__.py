"""합성 입력 JSON을 받아 분석 결과 JSON을 쓰는 데모 CLI.

    python -m screentime --input INPUT_JSON --output OUTPUT_JSON

명시된 파일만 읽고 쓴다. DB·네트워크·서버·API 키를 사용하지 않는다.
검증 실패 시 **필드 위치와 오류 유형만** stderr에 표시하고 원본 사용자 데이터는 출력하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from .models import AnalysisInput
from .pipeline import analyze

EXIT_OK = 0
EXIT_INVALID_INPUT = 2


def _describe(error: ValidationError) -> str:
    """오류 위치와 유형만 남긴다. 사용자 값은 절대 넣지 않는다."""
    lines = [f"입력 검증 실패: {error.error_count()}건"]
    for item in error.errors(include_url=False):
        location = ".".join(str(part) for part in item["loc"]) or "(root)"
        lines.append(f"  - {location}: {item['type']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="screentime", description="스크린타임 분석 데모")
    parser.add_argument("--input", required=True, type=Path, help="AnalysisInput JSON 경로")
    parser.add_argument("--output", required=True, type=Path, help="AnalysisOutput JSON을 쓸 경로")
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"입력 파일을 읽을 수 없습니다: {exc.strerror}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    except json.JSONDecodeError as exc:
        # 위치만 알린다. 문제가 된 원문 조각은 출력하지 않는다.
        print(f"JSON 구문 오류: line {exc.lineno} column {exc.colno}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    try:
        request = AnalysisInput.model_validate(payload)
    except ValidationError as exc:
        print(_describe(exc), file=sys.stderr)
        return EXIT_INVALID_INPUT

    result = analyze(request)
    args.output.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
