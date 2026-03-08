"""Gold-label loading and deterministic evaluation for official-seed runs."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .models import ExtractedProgramInfo, OfficialTargetDefinition

SCALAR_FIELDS: tuple[str, ...] = (
    "program_name",
    "deadline",
    "tuition",
    "english_requirement",
    "academic_requirement",
)
EVALUATED_FIELDS: tuple[str, ...] = SCALAR_FIELDS + ("prerequisite_keywords",)
_NORMALIZATION_REPLACEMENTS = str.maketrans(
    {
        "\u00a0": " ",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
    }
)
_MONTH_NAME_PATTERN = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_CURRENCY_VALUE_PATTERN = re.compile(
    r"\b(?:hk\$|us\$|usd|eur|gbp|\$)\s*(\d[\d,]*(?:\.\d{2})?)\b",
    flags=re.IGNORECASE,
)
READY_GOLD_LABEL_STATUSES: frozenset[str] = frozenset(
    {
        "manually_curated",
        "manually_curated_example",
        "benchmark_ready",
        "completed",
        "ready",
    }
)


@dataclass(slots=True)
class GoldLabelRecord:
    """A manually curated gold label for one benchmarked program."""

    program_code: str
    university: str
    mode: str
    label_status: str
    fields: dict[str, str | list[str] | None] = field(default_factory=dict)
    coverage_expectations: dict[str, bool] = field(default_factory=dict)
    notes: str | None = None
    gold_label_path: str | None = None


@dataclass(slots=True)
class FieldEvaluationResult:
    """Comparison outcome for one extracted field against the gold label."""

    field_name: str
    comparison_kind: str
    extracted_value: str | list[str] | None
    gold_value: str | list[str] | None
    normalized_extracted: str | list[str] | None
    normalized_gold: str | list[str] | None
    score: float
    exact_match: bool
    status: str
    coverage_expected: bool
    reason: str
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None


@dataclass(slots=True)
class EvaluationSummary:
    """High-level benchmark summary across all evaluated fields."""

    required_field_count: int
    covered_required_field_count: int
    matched_required_field_count: int
    extracted_populated_field_count: int
    scored_field_count: int
    field_coverage_rate: float | None
    exact_match_rate: float | None
    overall_field_score: float | None
    score_not_meaningful: bool = False
    scored_fields: list[str] = field(default_factory=list)
    skipped_fields_due_to_missing_truth: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    status_counts: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class EvaluationReport:
    """Persisted benchmark artifact for one official-seed run."""

    mode: str
    program_code: str
    university: str
    label_status: str
    gold_label_path: str
    processed_output_path: str | None
    debug_output_path: str | None
    benchmark_status: str = "completed"
    benchmark_message: str | None = None
    field_results: dict[str, FieldEvaluationResult] = field(default_factory=dict)
    summary: EvaluationSummary | None = None


def default_gold_dir() -> Path:
    """Return the repository-local directory for official-seed gold labels."""

    return Path(__file__).resolve().parents[2] / "data" / "gold" / "official-seed"


def load_gold_label(
    *,
    program_code: str,
    gold_dir: Path | str | None = None,
) -> GoldLabelRecord:
    """Load one manually curated gold label by program code."""

    base_dir = Path(gold_dir) if gold_dir is not None else default_gold_dir()
    gold_path = base_dir / f"{program_code}.json"
    if not gold_path.is_file():
        raise FileNotFoundError(f"Gold label not found for program code {program_code}: {gold_path}")

    payload = json.loads(gold_path.read_text(encoding="utf-8"))
    fields_payload = payload.get("fields")
    if not isinstance(fields_payload, dict):
        raise ValueError(f"Gold label must contain a 'fields' object: {gold_path}")

    fields: dict[str, str | list[str] | None] = {}
    for field_name in SCALAR_FIELDS:
        value = fields_payload.get(field_name)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"Gold label field '{field_name}' must be a string or null: {gold_path}")
        fields[field_name] = value

    keyword_payload = fields_payload.get("prerequisite_keywords", [])
    if keyword_payload is None:
        keyword_payload = []
    if not isinstance(keyword_payload, list):
        raise ValueError(f"Gold label field 'prerequisite_keywords' must be a list: {gold_path}")
    fields["prerequisite_keywords"] = [str(item) for item in keyword_payload]

    coverage_expectations_payload = payload.get("coverage_expectations", {})
    if not isinstance(coverage_expectations_payload, dict):
        raise ValueError(f"Gold label 'coverage_expectations' must be an object: {gold_path}")

    coverage_expectations = {
        field_name: bool(coverage_expectations_payload[field_name])
        for field_name in EVALUATED_FIELDS
        if field_name in coverage_expectations_payload
    }

    return GoldLabelRecord(
        program_code=str(payload["program_code"]),
        university=str(payload["university"]),
        mode=str(payload.get("mode", "official_seed")),
        label_status=str(payload.get("label_status", "manual")),
        fields=fields,
        coverage_expectations=coverage_expectations,
        notes=str(payload["notes"]) if payload.get("notes") is not None else None,
        gold_label_path=str(gold_path),
    )


def evaluate_official_seed_result(
    *,
    target: OfficialTargetDefinition,
    extracted_result: ExtractedProgramInfo,
    gold_label: GoldLabelRecord,
    processed_output_path: Path | None = None,
    debug_output_path: Path | None = None,
) -> EvaluationReport:
    """Compare one official-seed extraction result against a curated gold label."""

    field_results: dict[str, FieldEvaluationResult] = {}
    gold_label_ready = is_ready_gold_label_status(gold_label.label_status)
    coverage_defaults = _default_coverage_expectations(target)
    coverage_expectations = {**coverage_defaults, **gold_label.coverage_expectations}

    for field_name in SCALAR_FIELDS:
        field_results[field_name] = compare_scalar_field(
            field_name=field_name,
            extracted_value=getattr(extracted_result, field_name),
            gold_value=gold_label.fields.get(field_name),
            coverage_expected=coverage_expectations[field_name],
            gold_truth_complete=gold_label_ready,
        )

    field_results["prerequisite_keywords"] = compare_keyword_field(
        field_name="prerequisite_keywords",
        extracted_keywords=extracted_result.prerequisite_keywords,
        gold_keywords=gold_label.fields.get("prerequisite_keywords", []),
        coverage_expected=coverage_expectations["prerequisite_keywords"],
        gold_truth_complete=gold_label_ready,
    )

    benchmark_status, benchmark_message = determine_benchmark_status(
        label_status=gold_label.label_status,
        required_field_count=count_required_fields(field_results),
    )
    summary = build_evaluation_summary(
        field_results,
        score_meaningful=benchmark_status == "completed",
    )
    return EvaluationReport(
        mode=gold_label.mode,
        program_code=target.program_code,
        university=target.university,
        label_status=gold_label.label_status,
        gold_label_path=gold_label.gold_label_path or "",
        processed_output_path=str(processed_output_path) if processed_output_path is not None else None,
        debug_output_path=str(debug_output_path) if debug_output_path is not None else None,
        benchmark_status=benchmark_status,
        benchmark_message=benchmark_message,
        field_results=field_results,
        summary=summary,
    )


def compare_scalar_field(
    *,
    field_name: str,
    extracted_value: str | None,
    gold_value: str | None,
    coverage_expected: bool,
    gold_truth_complete: bool = True,
) -> FieldEvaluationResult:
    """Compare one scalar field with normalized exact matching."""

    normalized_extracted = normalize_field_value(field_name, extracted_value)
    normalized_gold = normalize_field_value(field_name, gold_value)
    extracted_has_value = bool(normalized_extracted)
    gold_has_value = bool(normalized_gold)

    if not gold_has_value:
        if not gold_truth_complete:
            return FieldEvaluationResult(
                field_name=field_name,
                comparison_kind="scalar",
                extracted_value=extracted_value,
                gold_value=gold_value,
                normalized_extracted=normalized_extracted,
                normalized_gold=normalized_gold,
                score=0.0,
                exact_match=False,
                status="skipped_due_to_missing_gold_truth",
                coverage_expected=coverage_expected,
                reason="Gold label is not yet complete for this field, so comparison is skipped.",
            )
        if not extracted_has_value:
            return FieldEvaluationResult(
                field_name=field_name,
                comparison_kind="scalar",
                extracted_value=extracted_value,
                gold_value=gold_value,
                normalized_extracted=normalized_extracted,
                normalized_gold=normalized_gold,
                score=1.0,
                exact_match=True,
                status="expected_null",
                coverage_expected=coverage_expected,
                reason="Gold label is intentionally empty for this field.",
            )
        return FieldEvaluationResult(
            field_name=field_name,
            comparison_kind="scalar",
            extracted_value=extracted_value,
            gold_value=gold_value,
            normalized_extracted=normalized_extracted,
            normalized_gold=normalized_gold,
            score=0.0,
            exact_match=False,
            status="extraction_error",
            coverage_expected=coverage_expected,
            reason="Extractor populated a field that is empty in the gold label.",
        )

    if not extracted_has_value:
        status = "field_left_null" if coverage_expected else "missing_source_coverage"
        reason = (
            "Gold label has a value and the current curated sources are expected to cover it."
            if coverage_expected
            else "Gold label has a value, but the current curated seed pages do not claim coverage for this field."
        )
        return FieldEvaluationResult(
            field_name=field_name,
            comparison_kind="scalar",
            extracted_value=extracted_value,
            gold_value=gold_value,
            normalized_extracted=normalized_extracted,
            normalized_gold=normalized_gold,
            score=0.0,
            exact_match=False,
            status=status,
            coverage_expected=coverage_expected,
            reason=reason,
        )

    if normalized_extracted == normalized_gold:
        return FieldEvaluationResult(
            field_name=field_name,
            comparison_kind="scalar",
            extracted_value=extracted_value,
            gold_value=gold_value,
            normalized_extracted=normalized_extracted,
            normalized_gold=normalized_gold,
            score=1.0,
            exact_match=True,
            status="matched",
            coverage_expected=coverage_expected,
            reason="Normalized extracted value matches the gold label.",
        )

    if field_name == "tuition":
        extracted_amounts = _extract_currency_amounts(extracted_value)
        gold_amounts = _extract_currency_amounts(gold_value)
        if gold_amounts and extracted_amounts and gold_amounts.issubset(extracted_amounts):
            return FieldEvaluationResult(
                field_name=field_name,
                comparison_kind="scalar",
                extracted_value=extracted_value,
                gold_value=gold_value,
                normalized_extracted=normalized_extracted,
                normalized_gold=normalized_gold,
                score=1.0,
                exact_match=True,
                status="matched",
                coverage_expected=coverage_expected,
                reason="Extracted tuition contains all gold tuition amount(s).",
            )

    return FieldEvaluationResult(
        field_name=field_name,
        comparison_kind="scalar",
        extracted_value=extracted_value,
        gold_value=gold_value,
        normalized_extracted=normalized_extracted,
        normalized_gold=normalized_gold,
        score=0.0,
        exact_match=False,
        status="extraction_error",
        coverage_expected=coverage_expected,
        reason="Normalized extracted value does not match the gold label.",
    )


def compare_keyword_field(
    *,
    field_name: str,
    extracted_keywords: list[str],
    gold_keywords: list[str] | None,
    coverage_expected: bool,
    gold_truth_complete: bool = True,
) -> FieldEvaluationResult:
    """Compare prerequisite keywords with normalized set overlap metrics."""

    normalized_extracted = normalize_keyword_values(extracted_keywords)
    normalized_gold = normalize_keyword_values(gold_keywords or [])
    extracted_set = set(normalized_extracted)
    gold_set = set(normalized_gold)
    extracted_has_value = bool(extracted_set)
    gold_has_value = bool(gold_set)

    if not gold_has_value:
        if not gold_truth_complete:
            return FieldEvaluationResult(
                field_name=field_name,
                comparison_kind="set_overlap",
                extracted_value=normalized_extracted,
                gold_value=normalized_gold,
                normalized_extracted=normalized_extracted,
                normalized_gold=normalized_gold,
                score=0.0,
                exact_match=False,
                status="skipped_due_to_missing_gold_truth",
                coverage_expected=coverage_expected,
                reason="Gold label is not yet complete for this field, so comparison is skipped.",
                precision=None,
                recall=None,
                f1=None,
            )
        if not extracted_has_value:
            return FieldEvaluationResult(
                field_name=field_name,
                comparison_kind="set_overlap",
                extracted_value=normalized_extracted,
                gold_value=normalized_gold,
                normalized_extracted=normalized_extracted,
                normalized_gold=normalized_gold,
                score=1.0,
                exact_match=True,
                status="expected_null",
                coverage_expected=coverage_expected,
                reason="Gold label is intentionally empty for this field.",
                precision=1.0,
                recall=1.0,
                f1=1.0,
            )
        return FieldEvaluationResult(
            field_name=field_name,
            comparison_kind="set_overlap",
            extracted_value=normalized_extracted,
            gold_value=normalized_gold,
            normalized_extracted=normalized_extracted,
            normalized_gold=normalized_gold,
            score=0.0,
            exact_match=False,
            status="extraction_error",
            coverage_expected=coverage_expected,
            reason="Extractor populated prerequisite keywords that are empty in the gold label.",
            precision=0.0,
            recall=0.0,
            f1=0.0,
        )

    if not extracted_has_value:
        status = "field_left_null" if coverage_expected else "missing_source_coverage"
        reason = (
            "Gold label has prerequisite keywords and the current curated sources are expected to cover them."
            if coverage_expected
            else "Gold label has prerequisite keywords, but the current curated seed pages do not claim coverage for this field."
        )
        return FieldEvaluationResult(
            field_name=field_name,
            comparison_kind="set_overlap",
            extracted_value=normalized_extracted,
            gold_value=normalized_gold,
            normalized_extracted=normalized_extracted,
            normalized_gold=normalized_gold,
            score=0.0,
            exact_match=False,
            status=status,
            coverage_expected=coverage_expected,
            reason=reason,
            precision=0.0,
            recall=0.0,
            f1=0.0,
        )

    overlap_count = len(extracted_set & gold_set)
    precision = overlap_count / len(extracted_set) if extracted_set else 0.0
    recall = overlap_count / len(gold_set) if gold_set else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    exact_match = extracted_set == gold_set
    status = "matched" if exact_match else "extraction_error"
    reason = (
        "Normalized prerequisite keyword set matches the gold label exactly."
        if exact_match
        else "Prerequisite keyword overlap is partial or mismatched."
    )
    return FieldEvaluationResult(
        field_name=field_name,
        comparison_kind="set_overlap",
        extracted_value=normalized_extracted,
        gold_value=normalized_gold,
        normalized_extracted=normalized_extracted,
        normalized_gold=normalized_gold,
        score=f1,
        exact_match=exact_match,
        status=status,
        coverage_expected=coverage_expected,
        reason=reason,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def build_evaluation_summary(
    field_results: dict[str, FieldEvaluationResult],
    *,
    score_meaningful: bool,
) -> EvaluationSummary:
    """Compute overall benchmark summary metrics from per-field results."""

    scored_field_names = [
        field_name
        for field_name, result in field_results.items()
        if _has_gold_value(result.gold_value)
    ]
    required_field_count = len(scored_field_names)
    covered_required_field_count = sum(
        1
        for field_name in scored_field_names
        if _has_extracted_value(field_results[field_name].extracted_value)
    )
    matched_required_field_count = sum(
        1
        for field_name in scored_field_names
        if field_results[field_name].exact_match
    )
    extracted_populated_field_count = sum(
        1
        for result in field_results.values()
        if _has_extracted_value(result.extracted_value)
    )
    score_not_meaningful = not (score_meaningful and required_field_count > 0)
    if score_not_meaningful:
        overall_field_score = None
        field_coverage_rate = None
        exact_match_rate = None
    else:
        overall_field_score = (
            sum(field_results[field_name].score for field_name in scored_field_names)
            / required_field_count
        )
        field_coverage_rate = covered_required_field_count / required_field_count
        exact_match_rate = matched_required_field_count / required_field_count
    status_counts: dict[str, int] = {}
    for result in field_results.values():
        status_counts[result.status] = status_counts.get(result.status, 0) + 1

    skipped_fields_due_to_missing_truth = [
        field_name
        for field_name, result in field_results.items()
        if result.status == "skipped_due_to_missing_gold_truth"
    ]
    missing_fields = [
        field_name
        for field_name, result in field_results.items()
        if result.status in {"field_left_null", "missing_source_coverage"}
    ]
    return EvaluationSummary(
        required_field_count=required_field_count,
        covered_required_field_count=covered_required_field_count,
        matched_required_field_count=matched_required_field_count,
        extracted_populated_field_count=extracted_populated_field_count,
        scored_field_count=required_field_count,
        field_coverage_rate=field_coverage_rate,
        exact_match_rate=exact_match_rate,
        overall_field_score=overall_field_score,
        score_not_meaningful=score_not_meaningful,
        scored_fields=scored_field_names,
        skipped_fields_due_to_missing_truth=skipped_fields_due_to_missing_truth,
        missing_fields=missing_fields,
        status_counts=status_counts,
    )


def resolve_eval_output_dir(
    *,
    processed_data_dir: Path,
    mode_subdir: str | None = None,
) -> Path:
    """Return the evaluation artifact directory below the processed output root."""

    output_dir = processed_data_dir / "eval"
    if mode_subdir:
        output_dir = output_dir / mode_subdir
    return output_dir


def write_evaluation_report(
    report: EvaluationReport,
    *,
    output_dir: Path,
    artifact_name: str,
) -> Path:
    """Persist one benchmark artifact as JSON."""

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / artifact_name
    output_path.write_text(
        json.dumps(asdict(report), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


def normalize_scalar_value(value: str | None) -> str | None:
    """Normalize one scalar value for deterministic exact matching."""

    if value is None:
        return None
    normalized = value.translate(_NORMALIZATION_REPLACEMENTS)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = re.sub(r"\s+([,.;:])", r"\1", normalized)
    normalized = re.sub(r"[ \t]+$", "", normalized)
    if not normalized:
        return None
    return normalized.casefold()


def normalize_field_value(field_name: str, value: str | None) -> str | None:
    """Normalize one scalar field with small field-specific canonical rules."""

    if value is None:
        return None

    normalized_source = value.translate(_NORMALIZATION_REPLACEMENTS)
    normalized_source = re.sub(r"\s+", " ", normalized_source).strip()
    normalized_source = re.sub(r"\s+([,.;:])", r"\1", normalized_source)

    if field_name == "program_name":
        normalized_source = re.sub(
            r"\s*\(([A-Z][A-Z0-9&/\-]{1,15})\)\s*$",
            "",
            normalized_source,
        )
        return normalize_scalar_value(normalized_source)
    if field_name == "deadline":
        normalized_source = _normalize_deadline_format(normalized_source)

    normalized = normalize_scalar_value(normalized_source)
    if normalized is None:
        return None

    if field_name == "english_requirement":
        canonical = _canonicalize_english_requirement(normalized)
        if canonical is not None:
            return canonical
    if field_name == "academic_requirement":
        canonical = _canonicalize_academic_requirement(normalized)
        if canonical is not None:
            return canonical

    return normalized


def normalize_keyword_values(values: list[str]) -> list[str]:
    """Normalize prerequisite keyword values into a sorted unique list."""

    normalized_values: set[str] = set()
    for value in values:
        normalized = normalize_scalar_value(value)
        if normalized:
            normalized_values.add(normalized)
    return sorted(normalized_values)


def _canonicalize_english_requirement(normalized: str) -> str | None:
    if (
        "english language requirement" in normalized
        and ("higher degree" in normalized or "higher degrees" in normalized)
        and any(
            keyword in normalized
            for keyword in (
                "satisfy",
                "applicable to higher degrees",
                "admission requirements",
                "admissions requirements",
            )
        )
    ):
        return "university higher degree english language requirement"
    return None


def _canonicalize_academic_requirement(normalized: str) -> str | None:
    has_course_background_pattern = all(
        keyword in normalized
        for keyword in ("calculus", "algebra", "programming", "statistics")
    ) and any(
        phrase in normalized
        for phrase in ("at least one", "should have completed", "shall have taken", "should have taken")
    )
    if has_course_background_pattern:
        return "course_background_calculus_algebra_programming_statistics"
    return None


def _normalize_deadline_format(value: str) -> str:
    normalized = value
    normalized = re.sub(
        rf"\b({_MONTH_NAME_PATTERN})\s+0([1-9])(?=,\s*\d{{4}}\b)",
        r"\1 \2",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        rf"\b0([1-9])\s+({_MONTH_NAME_PATTERN})(?=\s+\d{{4}}\b)",
        r"\1 \2",
        normalized,
        flags=re.IGNORECASE,
    )
    return normalized


def _extract_currency_amounts(value: str | None) -> set[int]:
    if not value:
        return set()
    amounts: set[int] = set()
    for match in _CURRENCY_VALUE_PATTERN.findall(value):
        amount = int(float(match.replace(",", "")))
        amounts.add(amount)
    return amounts


def is_ready_gold_label_status(label_status: str) -> bool:
    """Return whether a gold label is in a completed, scoreable state."""

    return label_status in READY_GOLD_LABEL_STATUSES


def count_required_fields(field_results: dict[str, FieldEvaluationResult]) -> int:
    """Count fields that have real gold truth and can be scored."""

    return sum(1 for result in field_results.values() if _has_gold_value(result.gold_value))


def determine_benchmark_status(
    *,
    label_status: str,
    required_field_count: int,
) -> tuple[str, str | None]:
    """Return the benchmark-level status and explanatory message."""

    if not is_ready_gold_label_status(label_status):
        if required_field_count == 0:
            return (
                "skipped_due_to_incomplete_gold_label",
                "Gold label is still marked as incomplete/template and contains no scored fields.",
            )
        return (
            "incomplete_gold_label",
            "Gold label is not yet in a completed state; field-level comparisons are partial and aggregate scores are not meaningful.",
        )
    if required_field_count == 0:
        return (
            "score_not_meaningful",
            "Gold label contains no scored fields, so aggregate benchmark scores are not meaningful.",
        )
    return "completed", None


def _default_coverage_expectations(target: OfficialTargetDefinition) -> dict[str, bool]:
    coverage = {field_name: False for field_name in EVALUATED_FIELDS}
    for seed_page in target.seed_pages:
        for field_name in seed_page.intended_fields:
            if field_name in coverage:
                coverage[field_name] = True
    return coverage


def _has_gold_value(value: str | list[str] | None) -> bool:
    if isinstance(value, list):
        return bool(value)
    return normalize_scalar_value(value) is not None


def _has_extracted_value(value: str | list[str] | None) -> bool:
    if isinstance(value, list):
        return bool(value)
    return normalize_scalar_value(value) is not None
