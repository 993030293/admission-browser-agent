"""Command-line entrypoint for one-hop admissions capture."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .config import BrowserConfig, RunConfig
from .evaluation import (
    evaluate_official_seed_result,
    load_gold_label,
    resolve_eval_output_dir,
    write_evaluation_report,
)
from .models import CrawlRequest
from .pipeline import AdmissionsPipeline
from .targets import load_official_seed_registry


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for generic exploration and curated-seed runs."""

    parser = argparse.ArgumentParser(
        prog="admission-browser-agent",
        description=(
            "Run either generic seed-URL exploration or curated official-seed-page "
            "capture for graduate admissions targets."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=("generic", "homepage", "official-seed"),
        default="generic",
        help=(
            "Execution mode. 'generic' explores from a user-provided seed URL. "
            "'official-seed' uses curated program pages. 'homepage' is a backward-compatible "
            "alias for 'generic'."
        ),
    )
    parser.add_argument(
        "--university",
        help="University label stored with generic exploration requests.",
    )
    parser.add_argument(
        "--seed-url",
        help="Single page URL to fetch in generic exploration mode.",
    )
    parser.add_argument(
        "--program-code",
        help="Curated program code to run in official-seed mode.",
    )
    parser.add_argument(
        "--all-programs",
        action="store_true",
        help="Run all curated target programs in official-seed mode.",
    )
    parser.add_argument(
        "--registry-path",
        help="Optional path to an official seed-page registry JSON file.",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Benchmark official-seed output against a manually curated gold label.",
    )
    parser.add_argument(
        "--gold-dir",
        help="Optional directory containing official-seed gold labels named <PROGRAM_CODE>.json.",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Launch the browser with a visible window instead of headless mode.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, run the selected mode, and print the result summary."""

    parser = build_parser()
    args = parser.parse_args(argv)

    run_config = RunConfig(browser=BrowserConfig(headless=not args.headful))
    registry_path = Path(args.registry_path) if args.registry_path else None
    gold_dir = Path(args.gold_dir) if args.gold_dir else None

    if args.mode in {"generic", "homepage"}:
        if args.benchmark:
            parser.exit(2, "Error: --benchmark currently supports only official-seed mode.\n")
        if not args.university:
            parser.exit(2, "Error: --university is required in generic mode.\n")
        if not args.seed_url:
            parser.exit(2, "Error: --seed-url is required in generic mode.\n")

        pipeline = AdmissionsPipeline(run_config=run_config)
        request = CrawlRequest(
            university=args.university,
            seed_url=args.seed_url,
        )

        try:
            result = pipeline.run(request)
        except Exception as exc:
            parser.exit(1, f"Error: {exc}\n")

        _print_generic_summary(pipeline, result)
        return 0

    if args.all_programs and args.program_code:
        parser.exit(2, "Error: use either --program-code or --all-programs in official-seed mode.\n")
    if not args.all_programs and not args.program_code:
        parser.exit(2, "Error: --program-code or --all-programs is required in official-seed mode.\n")

    try:
        registry = load_official_seed_registry(registry_path)
    except Exception as exc:
        parser.exit(1, f"Error: {exc}\n")

    targets = registry.targets
    if args.program_code:
        targets = [target for target in registry.targets if target.program_code == args.program_code]
        if not targets:
            parser.exit(
                1,
                f"Error: Program code not found in official seed-page registry: {args.program_code}\n",
            )

    for index, target in enumerate(targets):
        gold_label = None
        if args.benchmark:
            try:
                gold_label = load_gold_label(program_code=target.program_code, gold_dir=gold_dir)
            except FileNotFoundError as exc:
                if args.all_programs:
                    if index > 0:
                        print()
                    _print_missing_gold_label_summary(
                        program_code=target.program_code,
                        message=str(exc),
                    )
                    continue
                parser.exit(1, f"Error: {exc}\n")
            except Exception as exc:
                parser.exit(1, f"Error: {exc}\n")

        pipeline = AdmissionsPipeline(run_config=run_config)
        try:
            result = pipeline.run_official_seed_target(target)
        except Exception as exc:
            parser.exit(1, f"Error: {exc}\n")

        if index > 0:
            print()
        _print_official_seed_summary(pipeline, result, program_code=target.program_code)
        if args.benchmark:
            if gold_label is None:
                raise RuntimeError("Benchmark requested without a loaded gold label.")
            if pipeline.last_processed_output_path is None:
                raise RuntimeError("Official seed-page run completed without a processed output artifact path.")

            evaluation_report = evaluate_official_seed_result(
                target=target,
                extracted_result=result,
                gold_label=gold_label,
                processed_output_path=pipeline.last_processed_output_path,
                debug_output_path=pipeline.last_debug_output_path,
            )
            evaluation_output_dir = resolve_eval_output_dir(
                processed_data_dir=_resolve_output_dir(run_config.processed_data_dir),
                mode_subdir="official-seed",
            )
            evaluation_output_path = write_evaluation_report(
                evaluation_report,
                output_dir=evaluation_output_dir,
                artifact_name=pipeline.last_processed_output_path.name,
            )
            _print_benchmark_summary(
                evaluation_report,
                evaluation_output_path=evaluation_output_path,
            )
    return 0


def _print_generic_summary(pipeline: AdmissionsPipeline, result) -> None:
    if pipeline.last_output_path is None:
        raise RuntimeError("Pipeline run completed without producing a raw output artifact path.")
    if pipeline.last_processed_output_path is None:
        raise RuntimeError("Pipeline run completed without producing a processed output artifact path.")
    if pipeline.last_debug_output_path is None:
        raise RuntimeError("Pipeline run completed without producing a debug output artifact path.")
    if pipeline.last_debug_report is None:
        raise RuntimeError("Pipeline run completed without producing a debug report.")

    print("run_mode: generic")
    print(f"source_url: {result.source_url}")
    print(f"page_title: {result.page_title}")
    print(f"raw_output_path: {pipeline.last_output_path}")
    print(f"processed_output_path: {pipeline.last_processed_output_path}")
    print(f"debug_output_path: {pipeline.last_debug_output_path}")
    print(f"candidate_pages_inspected: {pipeline.last_inspected_candidate_count}")
    print(f"follow_up_triggered: {pipeline.last_debug_report.follow_up_triggered}")
    print(f"follow_up_candidates_found: {pipeline.last_debug_report.follow_up_candidates_found}")
    print(f"follow_up_candidates_fetched: {pipeline.last_debug_report.follow_up_candidates_fetched}")
    print(
        f"follow_up_fields_supplemented: {pipeline.last_debug_report.follow_up_fields_supplemented}"
    )


def _print_official_seed_summary(
    pipeline: AdmissionsPipeline,
    result,
    *,
    program_code: str,
) -> None:
    if pipeline.last_output_path is None:
        raise RuntimeError("Official seed-page run completed without a raw output artifact path.")
    if pipeline.last_processed_output_path is None:
        raise RuntimeError("Official seed-page run completed without a processed output artifact path.")
    if pipeline.last_debug_output_path is None:
        raise RuntimeError("Official seed-page run completed without a debug output artifact path.")
    if pipeline.last_debug_report is None:
        raise RuntimeError("Official seed-page run completed without a debug report.")

    print("run_mode: official-seed")
    print(f"program_code: {program_code}")
    print(f"source_url: {result.source_url}")
    print(f"page_title: {result.page_title}")
    print(f"raw_output_path: {pipeline.last_output_path}")
    print(f"processed_output_path: {pipeline.last_processed_output_path}")
    print(f"debug_output_path: {pipeline.last_debug_output_path}")
    print(f"seed_pages_inspected: {len(pipeline.last_debug_report.inspected_pages)}")


def _print_benchmark_summary(evaluation_report, *, evaluation_output_path: Path) -> None:
    if evaluation_report.summary is None:
        raise RuntimeError("Evaluation report completed without a summary.")

    print(f"benchmark_status: {evaluation_report.benchmark_status}")
    print(f"gold_label_status: {evaluation_report.label_status}")
    print(f"gold_label_path: {evaluation_report.gold_label_path}")
    print(f"evaluation_output_path: {evaluation_output_path}")
    print(f"required_field_count: {evaluation_report.summary.required_field_count}")
    print(f"scored_field_count: {evaluation_report.summary.scored_field_count}")
    print(
        "real_scored_fields: "
        f"{', '.join(evaluation_report.summary.scored_fields) or 'none'}"
    )
    print(
        "skipped_fields_due_to_missing_truth: "
        f"{', '.join(evaluation_report.summary.skipped_fields_due_to_missing_truth) or 'none'}"
    )
    print(f"score_not_meaningful: {evaluation_report.summary.score_not_meaningful}")
    if evaluation_report.benchmark_message:
        print(f"benchmark_message: {evaluation_report.benchmark_message}")
    print(
        "overall_field_score: "
        f"{_format_optional_metric(evaluation_report.summary.overall_field_score)}"
    )
    print(
        "exact_match_rate: "
        f"{_format_optional_metric(evaluation_report.summary.exact_match_rate)}"
    )
    print(
        "field_coverage_rate: "
        f"{_format_optional_metric(evaluation_report.summary.field_coverage_rate)}"
    )
    print(f"missing_fields: {', '.join(evaluation_report.summary.missing_fields) or 'none'}")


def _print_missing_gold_label_summary(*, program_code: str, message: str) -> None:
    print("run_mode: official-seed")
    print(f"program_code: {program_code}")
    print("benchmark_status: skipped_missing_gold_label")
    print(f"benchmark_message: {message}")


def _resolve_output_dir(base_dir: Path) -> Path:
    if base_dir.is_absolute():
        return base_dir
    return _repo_root() / base_dir


def _format_optional_metric(value: float | None) -> str:
    if value is None:
        return "score_not_meaningful"
    return f"{value:.3f}"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


if __name__ == "__main__":
    raise SystemExit(main())
