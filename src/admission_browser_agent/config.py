"""Configuration models for the admissions browser agent scaffold."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class BrowserConfig:
    """Runtime settings for the future browser backend."""

    browser_name: str = "chromium"
    headless: bool = True
    timeout_ms: int = 30_000
    stabilization_wait_ms: int = 1_500
    user_agent: str | None = None


@dataclass(slots=True)
class RunConfig:
    """Top-level run configuration for the future admissions pipeline."""

    max_pages: int = 20
    output_path: Path | None = None
    raw_data_dir: Path = field(default_factory=lambda: Path("data") / "raw")
    processed_data_dir: Path = field(default_factory=lambda: Path("data") / "processed")
    export_data_dir: Path = field(default_factory=lambda: Path("data") / "exports")
    debug_data_dir: Path = field(default_factory=lambda: Path("data") / "processed" / "debug")
    capture_html: bool = False
    respect_robots_txt: bool = True
    browser: BrowserConfig = field(default_factory=BrowserConfig)
