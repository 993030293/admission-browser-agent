"""Load manually curated official seed pages for targeted program runs."""

from __future__ import annotations

import json
from pathlib import Path

from .models import OfficialSeedPage, OfficialSeedRegistry, OfficialTargetDefinition


def default_registry_path() -> Path:
    """Return the repository-local path to the official seed-page registry."""

    return Path(__file__).resolve().parents[2] / "data" / "targets" / "official_seed_pages.json"


def load_official_seed_registry(path: Path | str | None = None) -> OfficialSeedRegistry:
    """Load the curated official seed-page registry from JSON."""

    registry_path = Path(path) if path is not None else default_registry_path()
    if not registry_path.is_file():
        raise FileNotFoundError(f"Official seed-page registry not found: {registry_path}")

    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    targets_payload = payload.get("targets")
    if not isinstance(targets_payload, list):
        raise ValueError("Official seed-page registry must contain a top-level 'targets' list.")

    targets: list[OfficialTargetDefinition] = []
    for target_payload in targets_payload:
        seed_pages_payload = target_payload.get("seed_pages")
        if not isinstance(seed_pages_payload, list) or not seed_pages_payload:
            raise ValueError(
                "Each official target definition must contain a non-empty 'seed_pages' list."
            )

        seed_pages = [
            OfficialSeedPage(
                page_type=str(seed_page["page_type"]),
                url=str(seed_page["url"]),
                priority=int(seed_page["priority"]),
                intended_fields=[str(field_name) for field_name in seed_page.get("intended_fields", [])],
            )
            for seed_page in seed_pages_payload
        ]
        targets.append(
            OfficialTargetDefinition(
                university=str(target_payload["university"]),
                program_code=str(target_payload["program_code"]),
                program_name=str(target_payload["program_name"]),
                tier=str(target_payload["tier"]),
                seed_pages=seed_pages,
            )
        )

    return OfficialSeedRegistry(targets=targets)


def get_target_definition(
    registry: OfficialSeedRegistry,
    *,
    program_code: str,
) -> OfficialTargetDefinition:
    """Return one curated target definition by program code."""

    for target in registry.targets:
        if target.program_code == program_code:
            return target
    raise KeyError(f"Program code not found in official seed-page registry: {program_code}")
