"""Load manually curated official seed pages for targeted program runs."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import OfficialSeedPage, OfficialSeedRegistry, OfficialTargetDefinition

_DEFAULT_QUERY_ALIASES: dict[str, str] = {
    "hku ai": "HKU_MSC_AI",
    "hkust bdt": "HKUST_MSC_BDT",
    "cuhk ai": "CUHK_MSC_AI",
}


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


def resolve_target_definition_from_query(
    registry: OfficialSeedRegistry,
    *,
    query: str,
) -> OfficialTargetDefinition:
    """Resolve a short user query like 'HKU AI' to one curated target program."""

    normalized_query = _normalize_text(query)
    if not normalized_query:
        raise ValueError("Query must not be empty.")

    alias_program_code = _DEFAULT_QUERY_ALIASES.get(normalized_query)
    if alias_program_code is not None:
        return get_target_definition(registry, program_code=alias_program_code)

    query_tokens = _tokenize(normalized_query)
    scored_targets: list[tuple[int, OfficialTargetDefinition]] = []
    for target in registry.targets:
        score = _target_query_score(target=target, query_tokens=query_tokens, normalized_query=normalized_query)
        scored_targets.append((score, target))

    scored_targets.sort(key=lambda item: (-item[0], item[1].program_code))
    best_score, best_target = scored_targets[0]
    if best_score <= 0:
        raise KeyError(f"No curated program matched query: {query}")

    tied_targets = [target for score, target in scored_targets if score == best_score]
    if len(tied_targets) > 1:
        tied_codes = ", ".join(target.program_code for target in tied_targets)
        raise ValueError(
            f"Ambiguous query '{query}'. Matching program codes: {tied_codes}. "
            "Please provide a more specific query."
        )
    return best_target


def _target_query_score(
    *,
    target: OfficialTargetDefinition,
    query_tokens: set[str],
    normalized_query: str,
) -> int:
    target_tokens = _target_tokens(target)
    score = 0

    if normalized_query == _normalize_text(target.program_code):
        score += 40
    if normalized_query == _normalize_text(f"{target.university} {target.program_name}"):
        score += 40

    acronym = _program_acronym(target.program_name)
    if acronym and acronym in query_tokens:
        score += 20

    university_token = _normalize_text(target.university)
    if university_token in query_tokens:
        score += 20

    for token in query_tokens:
        if token in target_tokens:
            score += 8

    if query_tokens and query_tokens.issubset(target_tokens):
        score += 12

    return score


def _target_tokens(target: OfficialTargetDefinition) -> set[str]:
    token_source = " ".join(
        (
            target.university,
            target.program_code,
            target.program_name,
        )
    )
    tokens = _tokenize(token_source)
    tokens.update(_tokenize(target.program_code.replace("_", " ")))
    acronym = _program_acronym(target.program_name)
    if acronym:
        tokens.add(acronym)
    return tokens


def _program_acronym(program_name: str) -> str:
    tokens = [
        token
        for token in _tokenize(program_name)
        if token not in {"master", "science", "of", "in", "for", "and", "data", "driven"}
    ]
    if not tokens:
        return ""
    return "".join(token[0] for token in tokens)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))
