"""Shared dataclasses for crawl requests and normalized output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CrawlRequest:
    """A high-level request to inspect a university admissions surface."""

    university: str
    seed_url: str
    program_hint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RawPageCapture:
    """Raw content captured from a single fetched page."""

    source_url: str
    page_title: str
    body_text: str


@dataclass(slots=True)
class CandidateLink:
    """A visible same-domain link discovered from a captured page."""

    anchor_text: str
    url: str


@dataclass(slots=True)
class OfficialSeedPage:
    """A manually curated official page to seed targeted program runs."""

    page_type: str
    url: str
    priority: int
    intended_fields: list[str] = field(default_factory=list)


@dataclass(slots=True)
class OfficialTargetDefinition:
    """A manually curated target program and its official seed pages."""

    university: str
    program_code: str
    program_name: str
    tier: str
    seed_pages: list[OfficialSeedPage] = field(default_factory=list)


@dataclass(slots=True)
class OfficialSeedRegistry:
    """Container for all manually curated targeted programs."""

    targets: list[OfficialTargetDefinition] = field(default_factory=list)


@dataclass(slots=True)
class ExtractedProgramInfo:
    """Heuristic fields extracted from a single admissions-related page."""

    source_url: str
    page_title: str
    program_name: str | None = None
    department: str | None = None
    duration: str | None = None
    deadline: str | None = None
    tuition: str | None = None
    english_requirement: str | None = None
    academic_requirement: str | None = None
    prerequisite_keywords: list[str] = field(default_factory=list)
    foundation_mentions: dict[str, bool] = field(default_factory=dict)
    field_sources: dict[str, list[str]] = field(default_factory=dict)


@dataclass(slots=True)
class CandidateLinkDebug:
    """Debug metadata for a discovered one-hop candidate link."""

    anchor_text: str
    url: str
    relevance_score: int
    eligible: bool = False
    selected: bool = False
    fetched: bool = False
    rejection_reason: str | None = None
    discovery_stage: str = "seed"
    discovered_from_url: str | None = None


@dataclass(slots=True)
class FieldValueCandidateDebug:
    """Candidate value considered during field-wise aggregation."""

    source_url: str
    page_title: str
    value: str | list[str] | dict[str, bool] | None
    hint_score: int
    specificity_score: int
    completeness_score: int
    eligible: bool
    selected: bool = False


@dataclass(slots=True)
class FieldAggregationDecision:
    """Debug information describing how one aggregated field was chosen."""

    field_name: str
    selected_value: str | list[str] | dict[str, bool] | None
    source_urls: list[str] = field(default_factory=list)
    strategy: str = ""
    candidates: list[FieldValueCandidateDebug] = field(default_factory=list)


@dataclass(slots=True)
class PageInspectionDebug:
    """Debug metadata for one inspected page in the one-hop flow."""

    source_url: str
    page_title: str
    raw_output_path: str
    anchor_text: str | None = None
    relevance_score: int | None = None
    extracted: ExtractedProgramInfo | None = None
    inspection_stage: str = "seed"
    discovered_from_url: str | None = None
    page_type: str | None = None
    priority: int | None = None
    intended_fields: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AggregationOutcome:
    """Aggregated result together with per-field decision details."""

    aggregated_result: ExtractedProgramInfo
    decisions: dict[str, FieldAggregationDecision] = field(default_factory=dict)


@dataclass(slots=True)
class DebugRunReport:
    """Run-level provenance artifact for one-hop discovery and aggregation."""

    seed_url: str
    seed_page_title: str
    run_mode: str = "generic_exploration"
    program_code: str | None = None
    program_name: str | None = None
    target_tier: str | None = None
    discovered_candidate_links: list[CandidateLinkDebug] = field(default_factory=list)
    inspected_pages: list[PageInspectionDebug] = field(default_factory=list)
    aggregation_decisions: dict[str, FieldAggregationDecision] = field(default_factory=dict)
    final_result: ExtractedProgramInfo | None = None
    follow_up_triggered: bool = False
    follow_up_missing_fields: list[str] = field(default_factory=list)
    follow_up_source_url: str | None = None
    follow_up_source_page_title: str | None = None
    follow_up_source_page_stage: str | None = None
    follow_up_discovery_sources: list["FollowUpDiscoverySourceDebug"] = field(default_factory=list)
    follow_up_candidates: list[CandidateLinkDebug] = field(default_factory=list)
    follow_up_candidates_found: int = 0
    follow_up_candidates_fetched: int = 0
    follow_up_fields_updated: list[str] = field(default_factory=list)
    follow_up_fields_supplemented: bool = False
    follow_up_update_reason: str | None = None


@dataclass(slots=True)
class FollowUpDiscoverySourceDebug:
    """Debug metadata for one constrained follow-up discovery source."""

    source_url: str
    page_title: str
    source_stage: str
    used_as_fallback: bool = False
    candidate_count: int = 0
    eligible_candidate_count: int = 0
    selected_candidate_count: int = 0
    fetched_candidate_count: int = 0
    outcome: str = ""


@dataclass(slots=True)
class ScoredCandidateLink:
    """A candidate link with a heuristic relevance score."""

    candidate: CandidateLink
    relevance_score: int


@dataclass(slots=True)
class ScoredProgramResult:
    """An extracted program result with a completeness score."""

    result: ExtractedProgramInfo
    completeness_score: int


@dataclass(slots=True)
class ProgramRecord:
    """Normalized admissions data for a single graduate program."""

    university: str
    program_name: str
    degree: str | None = None
    admissions_url: str | None = None
    deadline: str | None = None
    tuition: str | None = None
    notes: list[str] = field(default_factory=list)
    raw_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExtractionResult:
    """Container for extracted records and pipeline metadata."""

    request: CrawlRequest
    records: list[ProgramRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    visited_urls: list[str] = field(default_factory=list)
