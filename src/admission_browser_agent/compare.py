"""Offline comparison report generation for MVP export artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class ComparisonRow:
    """One flattened MVP export row used for cross-program comparison."""

    university: str
    program_code: str
    program_name: str
    deadline: str
    tuition: str
    language_requirement: str
    background_requirement: str
    mentions_statistics_foundation: bool
    mentions_programming_foundation: bool
    mentions_math_foundation: bool


def load_latest_mvp_exports(export_dir: Path) -> list[ComparisonRow]:
    """Load the latest JSON export row per program code from an export directory."""

    if not export_dir.is_dir():
        raise FileNotFoundError(f"MVP export directory not found: {export_dir}")

    latest_by_program: dict[str, tuple[str, ComparisonRow]] = {}
    for file_path in sorted(export_dir.glob("*.json")):
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        program_code = str(payload.get("program_code", "")).strip()
        if not program_code:
            continue
        row = _to_comparison_row(payload)
        artifact_key = file_path.stem
        existing = latest_by_program.get(program_code)
        if existing is None or artifact_key > existing[0]:
            latest_by_program[program_code] = (artifact_key, row)

    if not latest_by_program:
        raise ValueError(f"No MVP JSON export files were found in: {export_dir}")
    return [item[1] for item in sorted(latest_by_program.values(), key=lambda entry: entry[1].program_code)]


def build_comparison_markdown(rows: list[ComparisonRow]) -> str:
    """Build a compact markdown comparison report."""

    headers = [
        "program_code",
        "program_name",
        "deadline",
        "tuition",
        "stats_foundation",
        "programming_foundation",
        "math_foundation",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.program_code,
                    row.program_name,
                    row.deadline or "",
                    row.tuition or "",
                    str(row.mentions_statistics_foundation),
                    str(row.mentions_programming_foundation),
                    str(row.mentions_math_foundation),
                ]
            )
            + " |"
        )

    earliest = _earliest_deadline(rows)
    stats_programs = [row.program_code for row in rows if row.mentions_statistics_foundation]
    cs_leaning_programs = [
        row.program_code
        for row in rows
        if row.mentions_programming_foundation and not row.mentions_math_foundation
    ]
    math_friendly_programs = [row.program_code for row in rows if row.mentions_math_foundation]

    lines.append("")
    lines.append("## Derived Signals")
    lines.append(
        f"- Earliest parsed deadline: {earliest if earliest is not None else 'not available'}"
    )
    lines.append(
        f"- Programs mentioning statistics foundation: {', '.join(stats_programs) if stats_programs else 'none'}"
    )
    lines.append(
        f"- Programs leaning CS/programming (heuristic): {', '.join(cs_leaning_programs) if cs_leaning_programs else 'none'}"
    )
    lines.append(
        f"- Programs mentioning mathematics foundation: {', '.join(math_friendly_programs) if math_friendly_programs else 'none'}"
    )
    return "\n".join(lines) + "\n"


def write_comparison_report(*, report_markdown: str, output_dir: Path) -> Path:
    """Write a markdown comparison report artifact and return its path."""

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"{timestamp}-mvp-comparison.md"
    output_path.write_text(report_markdown, encoding="utf-8")
    return output_path


def answer_simple_question(rows: list[ComparisonRow], question: str) -> str:
    """Return a deterministic rule-based answer from comparison rows."""

    normalized = question.strip().lower()
    if not normalized:
        return "Question is empty."

    if any(token in normalized for token in ("statistics", "统计")):
        matches = [row.program_code for row in rows if row.mentions_statistics_foundation]
        return (
            "Programs mentioning statistics foundation: "
            + (", ".join(matches) if matches else "none")
        )

    if any(token in normalized for token in ("programming", "cs", "计算机", "编程")):
        matches = [row.program_code for row in rows if row.mentions_programming_foundation]
        return (
            "Programs mentioning programming/CS foundation: "
            + (", ".join(matches) if matches else "none")
        )

    if any(token in normalized for token in ("math", "mathematics", "数学")):
        matches = [row.program_code for row in rows if row.mentions_math_foundation]
        return (
            "Programs mentioning mathematics foundation: "
            + (", ".join(matches) if matches else "none")
        )

    if any(
        token in normalized
        for token in ("earliest", "deadline", "截止", "最早")
    ):
        earliest = _earliest_deadline(rows)
        return f"Earliest parsed deadline: {earliest if earliest is not None else 'not available'}"

    return (
        "Supported questions currently include: statistics foundation, programming/CS foundation, "
        "mathematics foundation, and earliest deadline."
    )


def _to_comparison_row(payload: dict[str, object]) -> ComparisonRow:
    return ComparisonRow(
        university=str(payload.get("university", "")),
        program_code=str(payload.get("program_code", "")),
        program_name=str(payload.get("program_name", "")),
        deadline=str(payload.get("deadline", "")),
        tuition=str(payload.get("tuition", "")),
        language_requirement=str(payload.get("language_requirement", "")),
        background_requirement=str(payload.get("background_requirement", "")),
        mentions_statistics_foundation=_to_bool(payload.get("mentions_statistics_foundation")),
        mentions_programming_foundation=_to_bool(payload.get("mentions_programming_foundation")),
        mentions_math_foundation=_to_bool(payload.get("mentions_math_foundation")),
    )


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def _earliest_deadline(rows: list[ComparisonRow]) -> str | None:
    parsed: list[tuple[datetime, str]] = []
    for row in rows:
        dt = _parse_deadline(row.deadline)
        if dt is None:
            continue
        parsed.append((dt, row.program_code))
    if not parsed:
        return None
    parsed.sort(key=lambda item: item[0])
    return f"{parsed[0][0].date().isoformat()} ({parsed[0][1]})"


def _parse_deadline(text: str) -> datetime | None:
    normalized = re.sub(r"\s+", " ", text.replace(",", " ")).strip()
    if not normalized:
        return None
    for fmt in (
        "%Y-%m-%d",
        "%d %b %Y",
        "%d %B %Y",
        "%B %d %Y",
        "%b %d %Y",
    ):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None
