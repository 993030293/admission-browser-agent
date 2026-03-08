# AGENTS.md

## Repository Purpose

This repository is for a browser-agent project that will extract graduate-program admissions information from university websites.

## Current Phase

The repo is currently in scaffold mode. Structural work is expected. Full scraping logic is not expected unless the user explicitly asks for it.

## Guardrails

- Do not add production scraping logic, selectors, or crawling heuristics unless requested.
- Do not add university-specific business rules outside `src/admission_browser_agent/sources/`.
- Keep tests offline and deterministic.
- Avoid module-level imports that require installed browser binaries or live network access.
- Prefer small dataclasses and explicit interfaces over hidden global state.

## Expected Layout

- Shared configuration and models belong in `src/admission_browser_agent/`.
- Browser lifecycle code belongs in `src/admission_browser_agent/browser.py`.
- Extraction interfaces belong in `src/admission_browser_agent/extractor.py`.
- Source-specific adapters belong in `src/admission_browser_agent/sources/`.
- CLI orchestration belongs in `src/admission_browser_agent/cli.py`.

## Implementation Guidance

- Preserve the boundary `request -> browser -> extractor -> normalized records`.
- Keep placeholder stubs simple and well documented.
- If browser support is expanded later, keep Playwright-specific details behind `BrowserSession`.
- When introducing a concrete source adapter, expose only the minimum hooks needed for URL seeding and record normalization.

## Testing Guidance

- Prefer smoke tests and unit tests over end-to-end browsing until real browser workflows exist.
- Avoid tests that depend on a specific university website remaining unchanged.
