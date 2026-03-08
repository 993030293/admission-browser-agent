# admission-browser-agent

A Python scaffold for a browser-driven agent that will extract graduate-program admissions information from university websites.

## Status

This repository is still intentionally minimal, but it now supports homepage-first one-hop discovery, heuristic field extraction, and curated official-seed-page runs via Playwright. It still does not implement unrestricted multi-page crawling, LLM logic, or university-specific source adapters.

## Project Goal

The long-term goal is to build a browser agent that can:

- open university admissions and department pages
- inspect graduate program requirements and deadlines
- normalize findings into a consistent structured format
- support multiple university-specific adapters over time

## Non-Goals For This Scaffold

The current scaffold does not:

- crawl across multiple pages
- ship CSS selectors or extraction rules
- include university-specific adapters
- persist results to a database or external service
- install browser binaries automatically

## Proposed Architecture

The package is split into a small set of stable boundaries:

- `config.py`: runtime and browser configuration dataclasses
- `models.py`: request and output dataclasses
- `browser.py`: minimal Playwright single-page fetcher
- `evaluation.py`: gold-label loading and deterministic benchmark scoring
- `extractor.py`: future HTML-to-record extraction interface
- `pipeline.py`: minimal single-request raw capture pipeline
- `targets.py`: loader for curated official seed-page definitions
- `sources/base.py`: base interface for university-specific source adapters
- `cli.py`: local command-line entrypoint for one capture run

This keeps browser access, extraction, and source-specific logic separate from the start.

## Folder Layout

```text
admission-browser-agent/
|- AGENTS.md
|- README.md
|- requirements.txt
|- data/
|  |- gold/
|  |  \- official-seed/
|  |     |- HKU_MSC_AI.json
|  |     |- HKU_MDASC.json
|  |     \- template.json
|  \- targets/
|     \- official_seed_pages.json
|- src/
|  \- admission_browser_agent/
|     |- __init__.py
|     |- browser.py
|     |- cli.py
|     |- config.py
|     |- evaluation.py
|     |- extractor.py
|     |- models.py
|     |- pipeline.py
|     |- targets.py
|     \- sources/
|        |- __init__.py
|        \- base.py
\- tests/
   \- test_scaffold.py
```

## Setup

Python 3.11+ is the target for this repository.

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run tests:

```bash
python -m pytest
```

## First Real Run

From the repository root, install the Python dependencies and the Chromium browser for Playwright:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Then choose one of the two execution modes.

Generic exploration mode:

PowerShell:

```powershell
$env:PYTHONPATH="src"
python -m admission_browser_agent.cli --mode generic --university "Example University" --seed-url "https://www.example.edu/graduate/admissions"
```

This remains the open-ended browser-agent path for arbitrary programmes and universities. It starts from the user-provided `seed_url`, performs the current discovery and aggregation flow, and writes runtime artifacts under `data/raw/` and `data/processed/`.

Curated-seed mode:

```powershell
$env:PYTHONPATH="src"
python -m admission_browser_agent.cli --mode official-seed --program-code "HKU_MSC_AI"
```

To run every curated target from the registry:

```powershell
$env:PYTHONPATH="src"
python -m admission_browser_agent.cli --mode official-seed --all-programs
```

This is an optional benchmark-oriented path. It fetches only the manually curated official program pages from `data/targets/official_seed_pages.json` and writes separate artifacts under `data/raw/official-seed/` and `data/processed/official-seed/`.

The legacy `--mode homepage` spelling is still accepted as a backward-compatible alias for `--mode generic`.

## Benchmarking

Gold-label benchmarking sits on top of official-seed mode. It does not change the browsing flow: the system still runs the curated official seed pages first, then compares the extracted output against a manually maintained gold label under `data/gold/official-seed/`.

Benchmark one curated program:

```powershell
$env:PYTHONPATH="src"
python -m admission_browser_agent.cli --mode official-seed --program-code "HKU_MSC_AI" --benchmark
```

To prepare the next benchmark target, manually fill `data/gold/official-seed/HKU_MDASC.json` and then run:

```powershell
$env:PYTHONPATH="src"
python -m admission_browser_agent.cli --mode official-seed --program-code "HKU_MDASC" --benchmark
```

Third curated target (`HKUST_MSC_BDT`) is prepared with a manual template at `data/gold/official-seed/HKUST_MSC_BDT.json`. After curation, run:

```powershell
$env:PYTHONPATH="src"
python -m admission_browser_agent.cli --mode official-seed --program-code "HKUST_MSC_BDT" --benchmark
```

Benchmark every curated program that has a matching gold label:

```powershell
$env:PYTHONPATH="src"
python -m admission_browser_agent.cli --mode official-seed --all-programs --benchmark
```

Evaluation artifacts are written under `data/processed/eval/official-seed/`. The benchmark report includes per-field status, normalized matching, keyword overlap metrics, coverage rate, exact-match rate, and whether a miss should be treated as an extraction error, missing source coverage, or a field left null.

## Benchmark Snapshot

Latest verified official-seed benchmark run:

- Date: 2026-03-08
- Program: `HKU_MDASC`
- Command:

```powershell
$env:PYTHONPATH="src"
python -m admission_browser_agent.cli --mode official-seed --program-code "HKU_MDASC" --benchmark
```

- Result summary:
  - `benchmark_status: completed`
  - `required_field_count: 6`
  - `scored_field_count: 6`
  - `overall_field_score: 1.000`
  - `exact_match_rate: 1.000`
  - `field_coverage_rate: 1.000`
  - `missing_fields: none`

## Official Seed Pages

Homepage-only discovery is useful for exploration, but manually curated official seed pages are a better starting point when the goal is stable benchmarking and higher-value capture. They let the pipeline begin from known programme, admissions, tuition, and English-requirement pages instead of hoping those links are exposed clearly from a homepage.

The file at `data/targets/official_seed_pages.json` is a curated registry of official university URLs. It is intended for benchmark and gold-label workflows where repeatability matters more than blind discovery breadth.

## Placeholder Usage

This scaffold exposes importable types and interfaces so later implementation work has clear boundaries.

Example:

```python
from admission_browser_agent.config import RunConfig
from admission_browser_agent.models import CrawlRequest
from admission_browser_agent.pipeline import AdmissionsPipeline

config = RunConfig()
request = CrawlRequest(
    university="Example University",
    seed_url="https://www.example.edu/graduate/admissions",
)
pipeline = AdmissionsPipeline(run_config=config)

# Runs one single-page capture and writes a JSON artifact under data/raw/.
pipeline.run(request)
```

The CLI now supports a single local capture run and prints the basic result summary.

## Next Implementation Steps

Likely next steps after this scaffold:

1. add packaging metadata so `PYTHONPATH=src` is no longer needed
2. define one concrete university source adapter
3. add HTML extraction rules for a narrow admissions use case
4. introduce a structured extracted-record layer on top of raw captures

## Development Notes

- Keep tests offline and deterministic.
- Keep browser integration behind `browser.py`.
- Add site-specific logic under `src/admission_browser_agent/sources/`.
- Avoid mixing extraction heuristics into the CLI.
