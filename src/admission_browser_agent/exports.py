"""Structured export helpers for MVP admissions output formats."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import ExtractedProgramInfo, OfficialTargetDefinition

SUPPORTED_EXPORT_FORMATS: tuple[str, ...] = ("json", "csv", "markdown")


def parse_export_formats(raw_value: str) -> list[str]:
    """Parse a comma-separated export format list with deterministic ordering."""

    requested = [item.strip().lower() for item in raw_value.split(",") if item.strip()]
    if not requested:
        raise ValueError("At least one export format must be provided.")

    invalid = [item for item in requested if item not in SUPPORTED_EXPORT_FORMATS]
    if invalid:
        raise ValueError(
            f"Unsupported export format(s): {', '.join(invalid)}. "
            f"Supported values: {', '.join(SUPPORTED_EXPORT_FORMATS)}."
        )

    deduped: list[str] = []
    for format_name in requested:
        if format_name not in deduped:
            deduped.append(format_name)
    return deduped


def export_program_result(
    *,
    target: OfficialTargetDefinition,
    result: ExtractedProgramInfo,
    output_dir: Path,
    artifact_stem: str,
    formats: list[str],
) -> dict[str, Path]:
    """Write one structured result to the requested export formats."""

    output_dir.mkdir(parents=True, exist_ok=True)
    row = build_export_row(target=target, result=result)
    output_paths: dict[str, Path] = {}

    for format_name in formats:
        if format_name == "json":
            output_path = output_dir / f"{artifact_stem}.json"
            output_path.write_text(
                json.dumps(row, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            output_paths[format_name] = output_path
            continue

        if format_name == "csv":
            output_path = output_dir / f"{artifact_stem}.csv"
            with output_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
                writer.writeheader()
                writer.writerow(row)
            output_paths[format_name] = output_path
            continue

        if format_name == "markdown":
            output_path = output_dir / f"{artifact_stem}.md"
            output_path.write_text(_to_markdown_table(row), encoding="utf-8")
            output_paths[format_name] = output_path
            continue

        raise ValueError(f"Unsupported export format: {format_name}")

    return output_paths


def build_export_row(
    *,
    target: OfficialTargetDefinition,
    result: ExtractedProgramInfo,
) -> dict[str, str]:
    """Build a flat row for JSON/CSV/Markdown exports."""

    return {
        "university": target.university,
        "program_code": target.program_code,
        "program_name": result.program_name or target.program_name,
        "department": result.department or "",
        "duration": result.duration or "",
        "tuition": result.tuition or "",
        "deadline": result.deadline or "",
        "language_requirement": result.english_requirement or "",
        "background_requirement": result.academic_requirement or "",
        "mentions_statistics_foundation": str(bool(result.foundation_mentions.get("statistics", False))),
        "mentions_programming_foundation": str(bool(result.foundation_mentions.get("programming", False))),
        "mentions_math_foundation": str(bool(result.foundation_mentions.get("mathematics", False))),
        "prerequisite_keywords": "; ".join(result.prerequisite_keywords),
        "source_url": result.source_url,
        "page_title": result.page_title,
    }


def _to_markdown_table(row: dict[str, str]) -> str:
    headers = list(row.keys())
    separator = ["---"] * len(headers)
    values = [row[header].replace("\n", " ") for header in headers]
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(separator) + " |"
    value_line = "| " + " | ".join(values) + " |"
    return "\n".join((header_line, separator_line, value_line)) + "\n"
