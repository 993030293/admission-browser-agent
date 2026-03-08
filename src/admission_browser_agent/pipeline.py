"""Minimal pipeline for single-request raw page capture."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .browser import BrowserSession
from .config import RunConfig
from .extractor import AdmissionsExtractor
from .models import (
    CandidateLinkDebug,
    CrawlRequest,
    DebugRunReport,
    ExtractedProgramInfo,
    FollowUpDiscoverySourceDebug,
    OfficialTargetDefinition,
    PageInspectionDebug,
    RawPageCapture,
    ScoredCandidateLink,
)
from .navigator import (
    aggregate_program_results_with_debug,
    score_extracted_program,
    score_candidate_links,
    score_follow_up_candidate_links,
    select_top_candidate_links,
)
from .targets import get_target_definition, load_official_seed_registry

_FOLLOW_UP_SOURCE_KEYWORDS: tuple[tuple[str, int], ...] = (
    ("admission", 5),
    ("apply", 4),
    ("application", 4),
    ("requirement", 3),
    ("deadline", 3),
    ("faq", 1),
)
_OFFICIAL_SEED_AUTO_DISCOVERY_MAX_FETCHES = 6
_OFFICIAL_SEED_AUTO_DISCOVERY_MAX_DEPTH = 3


class AdmissionsPipeline:
    """Coordinate a one-hop request -> browse -> extract -> select workflow."""

    def __init__(
        self,
        *,
        run_config: RunConfig | None = None,
        browser_session: BrowserSession | None = None,
        extractor: AdmissionsExtractor | None = None,
    ) -> None:
        self.run_config = run_config or RunConfig()
        self.browser_session = browser_session or BrowserSession(self.run_config.browser)
        self.extractor = extractor or AdmissionsExtractor()
        self.last_output_path: Path | None = None
        self.last_processed_output_path: Path | None = None
        self.last_debug_output_path: Path | None = None
        self.last_extracted_program: ExtractedProgramInfo | None = None
        self.last_debug_report: DebugRunReport | None = None
        self.last_raw_output_paths: list[Path] = []
        self.last_candidate_links: list[ScoredCandidateLink] = []
        self.last_inspected_candidate_count: int = 0

    def run(self, request: CrawlRequest) -> ExtractedProgramInfo:
        """Fetch a seed page, inspect one-hop candidates, and return the best result."""

        if not request.seed_url:
            raise ValueError("CrawlRequest.seed_url must be provided.")

        artifact_name = self._build_artifact_name(request)
        self._reset_run_state()

        seed_capture, discovered_links = self.browser_session.fetch_page_with_links(request.seed_url)
        self.last_output_path = self._write_raw_capture(seed_capture, artifact_name)
        self.last_raw_output_paths.append(self.last_output_path)

        page_hint_text_by_url = {
            seed_capture.source_url: f"{seed_capture.page_title} {seed_capture.source_url}",
        }
        all_scored_candidates = score_candidate_links(discovered_links)
        self.last_candidate_links = select_top_candidate_links(discovered_links)
        selected_candidate_urls = {item.candidate.url for item in self.last_candidate_links}
        debug_candidate_links = [
            CandidateLinkDebug(
                anchor_text=item.candidate.anchor_text,
                url=item.candidate.url,
                relevance_score=item.relevance_score,
                eligible=item.relevance_score > 0,
                selected=item.candidate.url in selected_candidate_urls,
                discovery_stage="seed",
                discovered_from_url=seed_capture.source_url,
            )
            for item in all_scored_candidates
        ]

        seed_extracted = self.extractor.extract(capture=seed_capture)
        extracted_results = [seed_extracted]
        inspected_pages = [
            PageInspectionDebug(
                source_url=seed_capture.source_url,
                page_title=seed_capture.page_title,
                raw_output_path=str(self.last_output_path),
                extracted=seed_extracted,
                inspection_stage="seed",
            )
        ]

        for index, scored_link in enumerate(self.last_candidate_links, start=1):
            try:
                candidate_capture = self.browser_session.fetch_page(scored_link.candidate.url)
            except RuntimeError:
                continue

            raw_output_path = self._write_raw_capture(
                candidate_capture,
                self._append_artifact_suffix(artifact_name, f"candidate-{index}"),
            )
            self.last_raw_output_paths.append(raw_output_path)
            self.last_inspected_candidate_count += 1
            page_hint_text_by_url[candidate_capture.source_url] = " ".join(
                part
                for part in (
                    candidate_capture.page_title,
                    scored_link.candidate.anchor_text,
                    candidate_capture.source_url,
                )
                if part
            )
            candidate_extracted = self.extractor.extract(capture=candidate_capture)
            extracted_results.append(candidate_extracted)
            inspected_pages.append(
                PageInspectionDebug(
                    source_url=candidate_capture.source_url,
                    page_title=candidate_capture.page_title,
                    raw_output_path=str(raw_output_path),
                    anchor_text=scored_link.candidate.anchor_text,
                    relevance_score=scored_link.relevance_score,
                    extracted=candidate_extracted,
                    inspection_stage="primary_candidate",
                    discovered_from_url=seed_capture.source_url,
                )
            )

        aggregation_outcome = aggregate_program_results_with_debug(
            extracted_results,
            page_hint_text_by_url=page_hint_text_by_url,
        )
        if aggregation_outcome is None:
            raise RuntimeError("Pipeline run completed without any extracted results.")

        initial_aggregated_result = aggregation_outcome.aggregated_result
        follow_up_missing_fields = self._missing_follow_up_fields(initial_aggregated_result)
        follow_up_triggered = False
        follow_up_source_url: str | None = None
        follow_up_source_page: PageInspectionDebug | None = None
        follow_up_discovery_sources: list[FollowUpDiscoverySourceDebug] = []
        follow_up_candidates: list[CandidateLinkDebug] = []
        follow_up_candidates_fetched = 0
        follow_up_fields_updated: list[str] = []
        follow_up_update_reason = "no_missing_high_value_fields"

        if follow_up_missing_fields:
            follow_up_source_page = self._select_follow_up_source_page(
                aggregated_result=initial_aggregated_result,
                inspected_pages=inspected_pages,
            )
            if follow_up_source_page is not None:
                follow_up_source_url = follow_up_source_page.source_url
                follow_up_triggered = True
                (
                    follow_up_discovery_sources,
                    follow_up_candidates,
                    follow_up_candidates_fetched,
                    follow_up_update_reason,
                ) = self._run_constrained_follow_up_scan(
                    artifact_name=artifact_name,
                    follow_up_source_page=follow_up_source_page,
                    missing_fields=follow_up_missing_fields,
                    seed_capture=seed_capture,
                    seed_discovered_links=discovered_links,
                    extracted_results=extracted_results,
                    inspected_pages=inspected_pages,
                    page_hint_text_by_url=page_hint_text_by_url,
                    debug_candidate_links=debug_candidate_links,
                )
                if follow_up_candidates_fetched > 0:
                    aggregation_outcome = aggregate_program_results_with_debug(
                        extracted_results,
                        page_hint_text_by_url=page_hint_text_by_url,
                    )
                    if aggregation_outcome is None:
                        raise RuntimeError("Pipeline run completed without any extracted results.")
                    follow_up_fields_updated = self._updated_follow_up_fields(
                        before_result=initial_aggregated_result,
                        after_result=aggregation_outcome.aggregated_result,
                        missing_fields=follow_up_missing_fields,
                    )
                    if follow_up_fields_updated:
                        follow_up_update_reason = "fields_supplemented"
                    else:
                        follow_up_update_reason = "follow_up_pages_did_not_fill_missing_fields"
                elif not follow_up_update_reason:
                    follow_up_update_reason = "no_follow_up_candidates_selected_for_fetch"
            else:
                follow_up_update_reason = "no_follow_up_source_page_selected"

        aggregated_result = aggregation_outcome.aggregated_result
        self.last_extracted_program = aggregated_result
        self.last_processed_output_path = self._write_processed_result(
            aggregated_result,
            artifact_name,
        )
        self.last_debug_report = DebugRunReport(
            seed_url=request.seed_url,
            seed_page_title=seed_capture.page_title,
            run_mode="generic_exploration",
            discovered_candidate_links=debug_candidate_links,
            inspected_pages=inspected_pages,
            aggregation_decisions=aggregation_outcome.decisions,
            final_result=aggregated_result,
            follow_up_triggered=follow_up_triggered,
            follow_up_missing_fields=follow_up_missing_fields,
            follow_up_source_url=follow_up_source_url,
            follow_up_source_page_title=(
                follow_up_source_page.page_title if follow_up_source_page is not None else None
            ),
            follow_up_source_page_stage=(
                follow_up_source_page.inspection_stage if follow_up_source_page is not None else None
            ),
            follow_up_discovery_sources=follow_up_discovery_sources,
            follow_up_candidates=follow_up_candidates,
            follow_up_candidates_found=len(follow_up_candidates),
            follow_up_candidates_fetched=follow_up_candidates_fetched,
            follow_up_fields_updated=follow_up_fields_updated,
            follow_up_fields_supplemented=bool(follow_up_fields_updated),
            follow_up_update_reason=follow_up_update_reason,
        )
        self.last_debug_output_path = self._write_debug_report(
            self.last_debug_report,
            artifact_name,
        )
        return aggregated_result

    def run_official_seed_program(
        self,
        *,
        program_code: str,
        registry_path: Path | str | None = None,
    ) -> ExtractedProgramInfo:
        """Fetch and aggregate the curated official seed pages for one program."""

        registry = load_official_seed_registry(registry_path)
        target = get_target_definition(registry, program_code=program_code)
        return self.run_official_seed_target(target)

    def run_official_seed_target(
        self,
        target: OfficialTargetDefinition,
    ) -> ExtractedProgramInfo:
        """Fetch and aggregate the curated official seed pages for one program definition."""

        if not target.seed_pages:
            raise ValueError(
                f"Official target definition has no seed pages: {target.program_code}"
            )

        artifact_name = self._build_artifact_name_from_slug(target.program_code)
        self._reset_run_state()

        ordered_seed_pages = sorted(
            target.seed_pages,
            key=lambda item: (item.priority, item.url),
        )
        page_hint_text_by_url: dict[str, str] = {}
        extracted_results: list[ExtractedProgramInfo] = []
        inspected_pages: list[PageInspectionDebug] = []
        primary_capture: RawPageCapture | None = None
        discovered_links_by_source_url: dict[str, list] = {}

        for index, seed_page in enumerate(ordered_seed_pages, start=1):
            try:
                capture, discovered_links = self.browser_session.fetch_page_with_links(seed_page.url)
            except RuntimeError as exc:
                raise RuntimeError(
                    f"Failed to fetch official seed page {seed_page.url}: {exc}"
                ) from exc

            raw_output_path = self._write_raw_capture(
                capture,
                self._append_artifact_suffix(
                    artifact_name,
                    f"seed-{index}-{seed_page.page_type}",
                ),
                mode_subdir="official-seed",
            )
            if primary_capture is None:
                primary_capture = capture
                self.last_output_path = raw_output_path
            self.last_raw_output_paths.append(raw_output_path)
            discovered_links_by_source_url[capture.source_url] = discovered_links

            extracted = self.extractor.extract(capture=capture)
            extracted_results.append(extracted)
            page_hint_text_by_url[capture.source_url] = " ".join(
                part
                for part in (
                    capture.page_title,
                    seed_page.page_type.replace("_", " ").replace("-", " "),
                    " ".join(
                        field_name.replace("_", " ").replace("-", " ")
                        for field_name in seed_page.intended_fields
                    ),
                    capture.source_url,
                )
                if part
            )
            inspected_pages.append(
                PageInspectionDebug(
                    source_url=capture.source_url,
                    page_title=capture.page_title,
                    raw_output_path=str(raw_output_path),
                    extracted=extracted,
                    inspection_stage="official_seed_page",
                    page_type=seed_page.page_type,
                    priority=seed_page.priority,
                    intended_fields=list(seed_page.intended_fields),
                )
            )

        aggregation_outcome = aggregate_program_results_with_debug(
            extracted_results,
            page_hint_text_by_url=page_hint_text_by_url,
        )
        if aggregation_outcome is None or primary_capture is None:
            raise RuntimeError(
                f"Official seed-page run produced no extracted results for {target.program_code}."
            )

        initial_aggregated_result = aggregation_outcome.aggregated_result
        supplement_missing_fields = self._missing_official_seed_supplement_fields(
            target=target,
            aggregated_result=initial_aggregated_result,
        )
        follow_up_triggered = False
        follow_up_source_url: str | None = None
        follow_up_source_page: PageInspectionDebug | None = None
        follow_up_discovery_sources: list[FollowUpDiscoverySourceDebug] = []
        follow_up_candidates: list[CandidateLinkDebug] = []
        follow_up_candidates_fetched = 0
        follow_up_fields_updated: list[str] = []
        follow_up_update_reason = "no_missing_curated_fields"

        if supplement_missing_fields:
            follow_up_triggered = True
            (
                follow_up_source_page,
                follow_up_discovery_sources,
                follow_up_candidates,
                follow_up_candidates_fetched,
                follow_up_update_reason,
            ) = self._run_official_seed_supplement_scan(
                artifact_name=artifact_name,
                target=target,
                missing_fields=supplement_missing_fields,
                discovered_links_by_source_url=discovered_links_by_source_url,
                extracted_results=extracted_results,
                inspected_pages=inspected_pages,
                page_hint_text_by_url=page_hint_text_by_url,
            )
            if follow_up_source_page is not None:
                follow_up_source_url = follow_up_source_page.source_url
            if follow_up_candidates_fetched > 0:
                aggregation_outcome = aggregate_program_results_with_debug(
                    extracted_results,
                    page_hint_text_by_url=page_hint_text_by_url,
                )
                if aggregation_outcome is None:
                    raise RuntimeError(
                        f"Official seed-page run produced no extracted results for {target.program_code}."
                    )
                follow_up_fields_updated = self._updated_follow_up_fields(
                    before_result=initial_aggregated_result,
                    after_result=aggregation_outcome.aggregated_result,
                    missing_fields=supplement_missing_fields,
                )
                if follow_up_fields_updated:
                    follow_up_update_reason = "fields_supplemented"
                else:
                    follow_up_update_reason = "supplement_pages_did_not_fill_missing_fields"

        aggregated_result = aggregation_outcome.aggregated_result
        self.last_extracted_program = aggregated_result
        self.last_processed_output_path = self._write_processed_result(
            aggregated_result,
            artifact_name,
            mode_subdir="official-seed",
        )
        self.last_debug_report = DebugRunReport(
            seed_url=primary_capture.source_url,
            seed_page_title=primary_capture.page_title,
            run_mode="official_seed",
            program_code=target.program_code,
            program_name=target.program_name,
            target_tier=target.tier,
            inspected_pages=inspected_pages,
            aggregation_decisions=aggregation_outcome.decisions,
            final_result=aggregated_result,
            follow_up_triggered=follow_up_triggered,
            follow_up_missing_fields=supplement_missing_fields,
            follow_up_source_url=follow_up_source_url,
            follow_up_source_page_title=(
                follow_up_source_page.page_title if follow_up_source_page is not None else None
            ),
            follow_up_source_page_stage=(
                follow_up_source_page.inspection_stage if follow_up_source_page is not None else None
            ),
            follow_up_discovery_sources=follow_up_discovery_sources,
            follow_up_candidates=follow_up_candidates,
            follow_up_candidates_found=len(follow_up_candidates),
            follow_up_candidates_fetched=follow_up_candidates_fetched,
            follow_up_fields_updated=follow_up_fields_updated,
            follow_up_fields_supplemented=bool(follow_up_fields_updated),
            follow_up_update_reason=follow_up_update_reason,
        )
        self.last_debug_output_path = self._write_debug_report(
            self.last_debug_report,
            artifact_name,
            mode_subdir="official-seed",
        )
        return aggregated_result

    def _run_official_seed_supplement_scan(
        self,
        *,
        artifact_name: str,
        target: OfficialTargetDefinition,
        missing_fields: list[str],
        discovered_links_by_source_url: dict[str, list],
        extracted_results: list[ExtractedProgramInfo],
        inspected_pages: list[PageInspectionDebug],
        page_hint_text_by_url: dict[str, str],
    ) -> tuple[
        PageInspectionDebug | None,
        list[FollowUpDiscoverySourceDebug],
        list[CandidateLinkDebug],
        int,
        str,
    ]:
        missing_field_set = set(missing_fields)
        already_inspected_urls = {page.source_url for page in inspected_pages}
        source_pages = self._official_seed_supplement_source_pages(
            target=target,
            inspected_pages=inspected_pages,
            missing_field_set=missing_field_set,
        )
        if not source_pages:
            return None, [], [], 0, "no_curated_seed_pages_match_missing_fields"

        follow_up_source_page = source_pages[0]
        discovery_attempts: list[dict[str, object]] = []
        source_queue: list[tuple[PageInspectionDebug, int]] = [(page, 0) for page in source_pages]
        expanded_source_urls: set[str] = set()
        seen_candidate_keys: set[tuple[str, str]] = set()
        candidate_pool: list[tuple[int, int, ScoredCandidateLink]] = []
        selected_follow_up_entries: list[tuple[int, int, ScoredCandidateLink]] = []
        selected_follow_up_urls: set[str] = set()
        fetched_count = 0
        fetched_candidate_keys: set[tuple[str | None, str]] = set()

        while fetched_count < _OFFICIAL_SEED_AUTO_DISCOVERY_MAX_FETCHES:
            while source_queue:
                source_page, depth = source_queue.pop(0)
                if source_page.source_url in expanded_source_urls:
                    continue
                expanded_source_urls.add(source_page.source_url)
                attempt = self._build_follow_up_source_attempt(
                    source_url=source_page.source_url,
                    page_title=source_page.page_title,
                    source_stage=source_page.inspection_stage,
                    used_as_fallback=False,
                    discovered_links=discovered_links_by_source_url.get(source_page.source_url, []),
                    fetch_failed=False,
                    missing_field_set=missing_field_set,
                    already_inspected_urls=already_inspected_urls,
                )
                discovery_attempts.append(attempt)
                attempt_index = len(discovery_attempts) - 1
                for scored_link in attempt["scored_links"]:
                    candidate_key = (source_page.source_url, scored_link.candidate.url)
                    if candidate_key in seen_candidate_keys:
                        continue
                    seen_candidate_keys.add(candidate_key)
                    candidate_pool.append((attempt_index, depth, scored_link))

            eligible_follow_up_entries = [
                item
                for item in candidate_pool
                if item[2].relevance_score > 0
                and item[2].candidate.url not in already_inspected_urls
                and item[2].candidate.url not in selected_follow_up_urls
            ]
            if not eligible_follow_up_entries:
                break

            eligible_follow_up_entries.sort(
                key=lambda item: (
                    -self._official_seed_candidate_priority_score(
                        target=target,
                        scored_link=item[2],
                        missing_field_set=missing_field_set,
                        depth=item[1],
                    ),
                    -item[2].relevance_score,
                    item[1],
                    len(item[2].candidate.url),
                    item[2].candidate.url,
                    item[2].candidate.anchor_text.lower(),
                    item[0],
                )
            )
            attempt_index, depth, scored_link = eligible_follow_up_entries[0]
            selected_follow_up_entries.append((attempt_index, depth, scored_link))
            selected_follow_up_urls.add(scored_link.candidate.url)

            source_url = str(discovery_attempts[attempt_index]["source_url"])
            try:
                candidate_capture, discovered_links = self.browser_session.fetch_page_with_links(
                    scored_link.candidate.url
                )
            except RuntimeError:
                continue

            fetched_candidate_keys.add((source_url, scored_link.candidate.url))
            already_inspected_urls.add(scored_link.candidate.url)
            discovered_links_by_source_url[candidate_capture.source_url] = discovered_links
            raw_output_path = self._write_raw_capture(
                candidate_capture,
                self._append_artifact_suffix(artifact_name, f"supplement-{fetched_count + 1}"),
                mode_subdir="official-seed",
            )
            self.last_raw_output_paths.append(raw_output_path)
            self.last_inspected_candidate_count += 1
            fetched_count += 1
            page_hint_text_by_url[candidate_capture.source_url] = " ".join(
                part
                for part in (
                    candidate_capture.page_title,
                    scored_link.candidate.anchor_text,
                    candidate_capture.source_url,
                )
                if part
            )
            candidate_extracted = self.extractor.extract(capture=candidate_capture)
            extracted_results.append(candidate_extracted)
            candidate_page = PageInspectionDebug(
                source_url=candidate_capture.source_url,
                page_title=candidate_capture.page_title,
                raw_output_path=str(raw_output_path),
                anchor_text=scored_link.candidate.anchor_text,
                relevance_score=scored_link.relevance_score,
                extracted=candidate_extracted,
                inspection_stage="official_seed_auto_candidate",
                discovered_from_url=source_url,
            )
            inspected_pages.append(candidate_page)

            aggregation_outcome = aggregate_program_results_with_debug(
                extracted_results,
                page_hint_text_by_url=page_hint_text_by_url,
            )
            if aggregation_outcome is not None:
                remaining_missing_fields = self._missing_official_seed_supplement_fields(
                    target=target,
                    aggregated_result=aggregation_outcome.aggregated_result,
                )
                missing_field_set = set(remaining_missing_fields)
                if not missing_field_set:
                    break

            if depth + 1 < _OFFICIAL_SEED_AUTO_DISCOVERY_MAX_DEPTH:
                source_queue.append((candidate_page, depth + 1))

        follow_up_discovery_sources = self._build_follow_up_source_debug(
            discovery_attempts=discovery_attempts,
            already_inspected_urls=already_inspected_urls,
            selected_candidate_keys={
                (str(discovery_attempts[attempt_index]["source_url"]), scored_link.candidate.url)
                for attempt_index, _depth, scored_link in selected_follow_up_entries
            },
            fetched_candidate_keys=fetched_candidate_keys,
        )
        follow_up_candidates = self._build_follow_up_candidate_debug(
            discovery_attempts=discovery_attempts,
            already_inspected_urls=already_inspected_urls,
            selected_candidate_keys={
                (str(discovery_attempts[attempt_index]["source_url"]), scored_link.candidate.url)
                for attempt_index, _depth, scored_link in selected_follow_up_entries
            },
            selected_follow_up_urls=selected_follow_up_urls,
        )
        follow_up_candidate_by_key = {
            (item.discovered_from_url, item.url): item for item in follow_up_candidates
        }
        for source_url, candidate_url in fetched_candidate_keys:
            debug_candidate = follow_up_candidate_by_key.get((source_url, candidate_url))
            if debug_candidate is not None:
                debug_candidate.fetched = True
                debug_candidate.rejection_reason = None

        if not follow_up_candidates:
            return (
                follow_up_source_page,
                follow_up_discovery_sources,
                [],
                0,
                "no_same_domain_supplement_candidates_found",
            )
        if not any(
            scored_link.relevance_score > 0
            for attempt in discovery_attempts
            for scored_link in attempt["scored_links"]
        ):
            return (
                follow_up_source_page,
                follow_up_discovery_sources,
                follow_up_candidates,
                0,
                "no_supplement_candidates_matched_missing_fields",
            )
        if not selected_follow_up_entries:
            return (
                follow_up_source_page,
                follow_up_discovery_sources,
                follow_up_candidates,
                0,
                "all_supplement_candidates_rejected_by_filtering",
            )
        if fetched_count == 0:
            return (
                follow_up_source_page,
                follow_up_discovery_sources,
                follow_up_candidates,
                0,
                "supplement_candidates_selected_but_not_fetched",
            )
        return (
            follow_up_source_page,
            follow_up_discovery_sources,
            follow_up_candidates,
            fetched_count,
            "supplement_candidates_fetched",
        )

    def _run_constrained_follow_up_scan(
        self,
        *,
        artifact_name: str,
        follow_up_source_page: PageInspectionDebug,
        missing_fields: list[str],
        seed_capture: RawPageCapture,
        seed_discovered_links: list,
        extracted_results: list[ExtractedProgramInfo],
        inspected_pages: list[PageInspectionDebug],
        page_hint_text_by_url: dict[str, str],
        debug_candidate_links: list[CandidateLinkDebug],
    ) -> tuple[list[FollowUpDiscoverySourceDebug], list[CandidateLinkDebug], int, str]:
        missing_field_set = set(missing_fields)
        already_inspected_urls = {page.source_url for page in inspected_pages}
        discovery_attempts: list[dict[str, object]] = []
        follow_up_source_url = follow_up_source_page.source_url

        primary_links, primary_fetch_failed = self._load_follow_up_discovery_links(
            source_url=follow_up_source_page.source_url,
            seed_capture=seed_capture,
            seed_discovered_links=seed_discovered_links,
        )
        discovery_attempts.append(
            self._build_follow_up_source_attempt(
                source_url=follow_up_source_page.source_url,
                page_title=follow_up_source_page.page_title,
                source_stage=follow_up_source_page.inspection_stage,
                used_as_fallback=False,
                discovered_links=primary_links,
                fetch_failed=primary_fetch_failed,
                missing_field_set=missing_field_set,
                already_inspected_urls=already_inspected_urls,
            )
        )

        primary_eligible_count = int(discovery_attempts[0]["eligible_candidate_count"])
        if primary_eligible_count == 0 and follow_up_source_page.source_url != seed_capture.source_url:
            discovery_attempts.append(
                self._build_follow_up_source_attempt(
                    source_url=seed_capture.source_url,
                    page_title=seed_capture.page_title,
                    source_stage="seed",
                    used_as_fallback=True,
                    discovered_links=seed_discovered_links,
                    fetch_failed=False,
                    missing_field_set=missing_field_set,
                    already_inspected_urls=already_inspected_urls,
                )
            )

        eligible_follow_up_entries: list[tuple[int, ScoredCandidateLink]] = []
        for attempt_index, attempt in enumerate(discovery_attempts):
            for scored_link in attempt["scored_links"]:
                if scored_link.relevance_score <= 0:
                    continue
                if scored_link.candidate.url in already_inspected_urls:
                    continue
                eligible_follow_up_entries.append((attempt_index, scored_link))

        eligible_follow_up_entries.sort(
            key=lambda item: (
                -item[1].relevance_score,
                len(item[1].candidate.url),
                item[1].candidate.url,
                item[1].candidate.anchor_text.lower(),
                item[0],
            )
        )
        follow_up_limit = max(1, min(len(missing_field_set), 2))
        selected_follow_up_entries: list[tuple[int, ScoredCandidateLink]] = []
        selected_follow_up_urls: set[str] = set()
        for attempt_index, scored_link in eligible_follow_up_entries:
            if scored_link.candidate.url in selected_follow_up_urls:
                continue
            selected_follow_up_entries.append((attempt_index, scored_link))
            selected_follow_up_urls.add(scored_link.candidate.url)
            if len(selected_follow_up_entries) >= follow_up_limit:
                break

        selected_candidate_keys = {
            (discovery_attempts[attempt_index]["source_url"], scored_link.candidate.url)
            for attempt_index, scored_link in selected_follow_up_entries
        }
        follow_up_candidates = self._build_follow_up_candidate_debug(
            discovery_attempts=discovery_attempts,
            already_inspected_urls=already_inspected_urls,
            selected_candidate_keys=selected_candidate_keys,
            selected_follow_up_urls=selected_follow_up_urls,
        )
        debug_candidate_links.extend(follow_up_candidates)
        follow_up_candidate_by_key = {
            (item.discovered_from_url, item.url): item for item in follow_up_candidates
        }
        fetched_count = 0
        fetched_candidate_keys: set[tuple[str | None, str]] = set()

        for index, (attempt_index, scored_link) in enumerate(selected_follow_up_entries, start=1):
            source_url = str(discovery_attempts[attempt_index]["source_url"])
            debug_candidate = follow_up_candidate_by_key.get((source_url, scored_link.candidate.url))
            try:
                candidate_capture = self.browser_session.fetch_page(scored_link.candidate.url)
            except RuntimeError:
                if debug_candidate is not None:
                    debug_candidate.rejection_reason = "fetch_failed"
                continue

            if debug_candidate is not None:
                debug_candidate.fetched = True
            fetched_candidate_keys.add((source_url, scored_link.candidate.url))
            raw_output_path = self._write_raw_capture(
                candidate_capture,
                self._append_artifact_suffix(artifact_name, f"follow-up-{index}"),
            )
            self.last_raw_output_paths.append(raw_output_path)
            self.last_inspected_candidate_count += 1
            fetched_count += 1
            page_hint_text_by_url[candidate_capture.source_url] = " ".join(
                part
                for part in (
                    candidate_capture.page_title,
                    scored_link.candidate.anchor_text,
                    candidate_capture.source_url,
                )
                if part
            )
            candidate_extracted = self.extractor.extract(capture=candidate_capture)
            extracted_results.append(candidate_extracted)
            inspected_pages.append(
                PageInspectionDebug(
                    source_url=candidate_capture.source_url,
                    page_title=candidate_capture.page_title,
                    raw_output_path=str(raw_output_path),
                    anchor_text=scored_link.candidate.anchor_text,
                    relevance_score=scored_link.relevance_score,
                    extracted=candidate_extracted,
                    inspection_stage="follow_up_candidate",
                    discovered_from_url=source_url,
                )
            )

        follow_up_discovery_sources = self._build_follow_up_source_debug(
            discovery_attempts=discovery_attempts,
            already_inspected_urls=already_inspected_urls,
            selected_candidate_keys=selected_candidate_keys,
            fetched_candidate_keys=fetched_candidate_keys,
        )

        if not follow_up_candidates:
            return follow_up_discovery_sources, [], 0, "no_same_domain_follow_up_candidates_found"
        if not any(
            scored_link.relevance_score > 0
            for attempt in discovery_attempts
            for scored_link in attempt["scored_links"]
        ):
            return (
                follow_up_discovery_sources,
                follow_up_candidates,
                0,
                "no_follow_up_candidates_matched_missing_fields",
            )
        if not selected_follow_up_entries:
            return (
                follow_up_discovery_sources,
                follow_up_candidates,
                0,
                "all_follow_up_candidates_rejected_by_filtering",
            )
        if fetched_count == 0:
            return (
                follow_up_discovery_sources,
                follow_up_candidates,
                0,
                "follow_up_candidates_selected_but_not_fetched",
            )
        return (
            follow_up_discovery_sources,
            follow_up_candidates,
            fetched_count,
            "follow_up_candidates_fetched",
        )

    def _missing_follow_up_fields(self, aggregated_result: ExtractedProgramInfo) -> list[str]:
        missing_fields: list[str] = []
        if not aggregated_result.tuition:
            missing_fields.append("tuition")
        if not aggregated_result.english_requirement:
            missing_fields.append("english_requirement")
        return missing_fields

    def _missing_official_seed_supplement_fields(
        self,
        *,
        target: OfficialTargetDefinition,
        aggregated_result: ExtractedProgramInfo,
    ) -> list[str]:
        intended_fields = {
            field_name
            for seed_page in target.seed_pages
            for field_name in seed_page.intended_fields
        }
        missing_fields: list[str] = []
        for field_name in ("deadline", "tuition"):
            if field_name not in intended_fields:
                continue
            if getattr(aggregated_result, field_name):
                continue
            missing_fields.append(field_name)
        return missing_fields

    def _official_seed_supplement_source_pages(
        self,
        *,
        target: OfficialTargetDefinition,
        inspected_pages: list[PageInspectionDebug],
        missing_field_set: set[str],
    ) -> list[PageInspectionDebug]:
        intended_by_url = {
            seed_page.url: set(seed_page.intended_fields)
            for seed_page in target.seed_pages
        }
        ranked_pages: list[tuple[int, int, int, str, PageInspectionDebug]] = []
        for page in inspected_pages:
            overlap_count = len(intended_by_url.get(page.source_url, set()) & missing_field_set)
            ranked_pages.append(
                (
                    int(overlap_count <= 0),
                    -overlap_count,
                    page.priority or 999,
                    page.source_url,
                    page,
                )
            )
        ranked_pages.sort()
        return [item[4] for item in ranked_pages]

    def _official_seed_candidate_priority_score(
        self,
        *,
        target: OfficialTargetDefinition,
        scored_link: ScoredCandidateLink,
        missing_field_set: set[str],
        depth: int,
    ) -> int:
        combined_text = " ".join(
            part.lower()
            for part in (scored_link.candidate.anchor_text, scored_link.candidate.url)
            if part
        )
        score = scored_link.relevance_score
        score += self._official_seed_target_match_boost(
            target=target,
            combined_text=combined_text,
        )
        score += self._official_seed_missing_field_boost(
            combined_text=combined_text,
            missing_field_set=missing_field_set,
        )
        score -= depth
        return score

    def _official_seed_target_match_boost(
        self,
        *,
        target: OfficialTargetDefinition,
        combined_text: str,
    ) -> int:
        program_code_tokens = [
            token
            for token in re.split(r"[^a-z0-9]+", target.program_code.lower())
            if token and token not in {target.university.lower(), "msc", "ms"}
        ]
        boost = 0
        has_code_match = any(token in combined_text for token in program_code_tokens)
        if has_code_match:
            boost += 25

        significant_tokens = [
            token
            for token in re.split(r"[^a-z0-9]+", target.program_name.lower())
            if token and token not in {"master", "of", "science", "in", "for", "and"}
        ]
        token_matches = sum(1 for token in significant_tokens if token in combined_text)
        if token_matches >= 2:
            boost += 15
        elif token_matches == 1:
            boost += 7
        if (
            any(
                keyword in combined_text
                for keyword in ("programme-details", "program-details", "programme details", "program details")
            )
            and (has_code_match or token_matches >= 2)
        ):
            boost += 30
        if "?programme=" in combined_text and (has_code_match or token_matches >= 2):
            boost += 20
        return boost

    def _official_seed_missing_field_boost(
        self,
        *,
        combined_text: str,
        missing_field_set: set[str],
    ) -> int:
        boost = 0
        if "english_requirement" not in missing_field_set and "faq" in combined_text:
            boost -= 30
        if "tuition" in missing_field_set:
            if any(keyword in combined_text for keyword in ("programme details", "program details", "programme-details", "program-details")):
                boost += 12
            if any(keyword in combined_text for keyword in ("programme fee", "program fee", "tuition", "fee and payment")):
                boost += 5
            if "application fee" in combined_text:
                boost -= 20
            if "programme fee and payment" in combined_text and "?programme=" not in combined_text:
                boost -= 10
        if "deadline" in missing_field_set and any(
            keyword in combined_text for keyword in ("deadline", "apply", "application", "admission")
        ):
            boost += 4
        if "deadline" in missing_field_set and "application deadline" in combined_text:
            boost += 8
        if "deadline" in missing_field_set and any(
            phrase in combined_text
            for phrase in ("how do i apply", "when are the application deadlines")
        ):
            boost -= 25
        if "programme listing" in combined_text or "program listing" in combined_text:
            boost -= 8
        if "faculty=" in combined_text:
            boost -= 8
        return boost

    def _select_follow_up_source_page(
        self,
        *,
        aggregated_result: ExtractedProgramInfo,
        inspected_pages: list[PageInspectionDebug],
    ) -> PageInspectionDebug | None:
        preferred_urls = set(aggregated_result.field_sources.get("deadline", []))
        preferred_urls.update(aggregated_result.field_sources.get("academic_requirement", []))
        preferred_urls.update(aggregated_result.field_sources.get("english_requirement", []))

        ranked_pages: list[tuple[int, int, int, str, PageInspectionDebug]] = []
        for page in inspected_pages:
            score = self._follow_up_source_score(page)
            if score <= 0:
                continue

            completeness = score_extracted_program(page.extracted) if page.extracted is not None else 0
            ranked_pages.append(
                (
                    int(page.source_url in preferred_urls),
                    score,
                    completeness,
                    page.source_url,
                    page,
                )
            )

        if not ranked_pages:
            return None

        ranked_pages.sort(
            key=lambda item: (
                -item[0],
                -item[1],
                -item[2],
                item[3],
            )
        )
        return ranked_pages[0][4]

    def _follow_up_source_score(self, page: PageInspectionDebug) -> int:
        haystack = " ".join(
            part.lower()
            for part in (page.page_title, page.anchor_text or "", page.source_url)
            if part
        )
        score = 0
        for keyword, weight in _FOLLOW_UP_SOURCE_KEYWORDS:
            if keyword in haystack:
                score += weight
        return score

    def _load_follow_up_discovery_links(
        self,
        *,
        source_url: str,
        seed_capture: RawPageCapture,
        seed_discovered_links: list,
    ) -> tuple[list, bool]:
        if source_url == seed_capture.source_url:
            return seed_discovered_links, False

        try:
            _capture, discovered_links = self.browser_session.fetch_page_with_links(source_url)
        except RuntimeError:
            return [], True
        return discovered_links, False

    def _build_follow_up_source_attempt(
        self,
        *,
        source_url: str,
        page_title: str,
        source_stage: str,
        used_as_fallback: bool,
        discovered_links: list,
        fetch_failed: bool,
        missing_field_set: set[str],
        already_inspected_urls: set[str],
    ) -> dict[str, object]:
        scored_links = score_follow_up_candidate_links(
            discovered_links,
            missing_fields=missing_field_set,
        )
        eligible_candidate_count = sum(
            1
            for item in scored_links
            if item.relevance_score > 0 and item.candidate.url not in already_inspected_urls
        )
        return {
            "source_url": source_url,
            "page_title": page_title,
            "source_stage": source_stage,
            "used_as_fallback": used_as_fallback,
            "fetch_failed": fetch_failed,
            "scored_links": scored_links,
            "eligible_candidate_count": eligible_candidate_count,
        }

    def _build_follow_up_candidate_debug(
        self,
        *,
        discovery_attempts: list[dict[str, object]],
        already_inspected_urls: set[str],
        selected_candidate_keys: set[tuple[str, str]],
        selected_follow_up_urls: set[str],
    ) -> list[CandidateLinkDebug]:
        follow_up_candidates: list[CandidateLinkDebug] = []
        for attempt in discovery_attempts:
            source_url = str(attempt["source_url"])
            for scored_link in attempt["scored_links"]:
                candidate_key = (source_url, scored_link.candidate.url)
                eligible = (
                    scored_link.relevance_score > 0
                    and scored_link.candidate.url not in already_inspected_urls
                )
                selected = candidate_key in selected_candidate_keys
                follow_up_candidates.append(
                    CandidateLinkDebug(
                        anchor_text=scored_link.candidate.anchor_text,
                        url=scored_link.candidate.url,
                        relevance_score=scored_link.relevance_score,
                        eligible=eligible,
                        selected=selected,
                        rejection_reason=self._follow_up_rejection_reason(
                            scored_link=scored_link,
                            candidate_key=candidate_key,
                            already_inspected_urls=already_inspected_urls,
                            selected_candidate_keys=selected_candidate_keys,
                            selected_follow_up_urls=selected_follow_up_urls,
                        ),
                        discovery_stage="follow_up",
                        discovered_from_url=source_url,
                    )
                )
        return follow_up_candidates

    def _build_follow_up_source_debug(
        self,
        *,
        discovery_attempts: list[dict[str, object]],
        already_inspected_urls: set[str],
        selected_candidate_keys: set[tuple[str, str]],
        fetched_candidate_keys: set[tuple[str | None, str]],
    ) -> list[FollowUpDiscoverySourceDebug]:
        debug_sources: list[FollowUpDiscoverySourceDebug] = []
        for attempt in discovery_attempts:
            source_url = str(attempt["source_url"])
            scored_links = attempt["scored_links"]
            positive_candidate_count = sum(
                1 for item in scored_links if item.relevance_score > 0
            )
            selected_candidate_count = sum(
                1 for _, url in selected_candidate_keys if _ == source_url
            )
            fetched_candidate_count = sum(
                1 for discovered_from_url, url in fetched_candidate_keys if discovered_from_url == source_url
            )
            if attempt["fetch_failed"]:
                outcome = "source_fetch_failed"
            elif not scored_links:
                outcome = "no_candidates_found"
            elif positive_candidate_count == 0:
                outcome = "candidates_found_but_all_irrelevant"
            elif int(attempt["eligible_candidate_count"]) == 0:
                outcome = "all_eligible_candidates_already_inspected"
            elif fetched_candidate_count > 0:
                outcome = "selected_candidates_fetched"
            elif selected_candidate_count > 0:
                outcome = "selected_candidates_not_fetched"
            else:
                outcome = "eligible_candidates_not_selected"

            debug_sources.append(
                FollowUpDiscoverySourceDebug(
                    source_url=source_url,
                    page_title=str(attempt["page_title"]),
                    source_stage=str(attempt["source_stage"]),
                    used_as_fallback=bool(attempt["used_as_fallback"]),
                    candidate_count=len(scored_links),
                    eligible_candidate_count=int(attempt["eligible_candidate_count"]),
                    selected_candidate_count=selected_candidate_count,
                    fetched_candidate_count=fetched_candidate_count,
                    outcome=outcome,
                )
            )
        return debug_sources

    def _follow_up_rejection_reason(
        self,
        *,
        scored_link: ScoredCandidateLink,
        candidate_key: tuple[str, str],
        already_inspected_urls: set[str],
        selected_candidate_keys: set[tuple[str, str]],
        selected_follow_up_urls: set[str],
    ) -> str | None:
        if scored_link.relevance_score <= 0:
            return "irrelevant_to_missing_fields"
        if scored_link.candidate.url in already_inspected_urls:
            return "already_inspected"
        if candidate_key in selected_candidate_keys:
            return None
        if scored_link.candidate.url in selected_follow_up_urls:
            return "duplicate_of_selected_candidate"
        if scored_link.candidate.url not in selected_follow_up_urls:
            return "not_in_follow_up_top_k"
        return None

    def _updated_follow_up_fields(
        self,
        *,
        before_result: ExtractedProgramInfo,
        after_result: ExtractedProgramInfo,
        missing_fields: list[str],
    ) -> list[str]:
        updated_fields: list[str] = []
        for field_name in missing_fields:
            before_value = getattr(before_result, field_name)
            after_value = getattr(after_result, field_name)
            if before_value == after_value:
                continue
            if after_value:
                updated_fields.append(field_name)
        return updated_fields

    def _reset_run_state(self) -> None:
        self.last_output_path = None
        self.last_processed_output_path = None
        self.last_debug_output_path = None
        self.last_extracted_program = None
        self.last_debug_report = None
        self.last_raw_output_paths = []
        self.last_candidate_links = []
        self.last_inspected_candidate_count = 0

    def _write_raw_capture(
        self,
        capture: RawPageCapture,
        artifact_name: str,
        *,
        mode_subdir: str | None = None,
    ) -> Path:
        output_dir = self._resolve_output_dir(self.run_config.raw_data_dir, mode_subdir=mode_subdir)
        output_dir.mkdir(parents=True, exist_ok=True)

        artifact_path = output_dir / artifact_name
        artifact_path.write_text(
            json.dumps(asdict(capture), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return artifact_path

    def _write_processed_result(
        self,
        extracted_program: ExtractedProgramInfo,
        artifact_name: str,
        *,
        mode_subdir: str | None = None,
    ) -> Path:
        output_dir = self._resolve_output_dir(
            self.run_config.processed_data_dir,
            mode_subdir=mode_subdir,
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        artifact_path = output_dir / artifact_name
        artifact_path.write_text(
            json.dumps(asdict(extracted_program), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return artifact_path

    def _write_debug_report(
        self,
        debug_report: DebugRunReport,
        artifact_name: str,
        *,
        mode_subdir: str | None = None,
    ) -> Path:
        output_dir = self._resolve_output_dir(
            self.run_config.debug_data_dir,
            mode_subdir=mode_subdir,
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        artifact_path = output_dir / artifact_name
        artifact_path.write_text(
            json.dumps(asdict(debug_report), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return artifact_path

    def _build_artifact_name(self, request: CrawlRequest) -> str:
        slug_source = request.university.strip() if request.university else "capture"
        return self._build_artifact_name_from_slug(slug_source)

    def _build_artifact_name_from_slug(self, slug_source: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", slug_source.lower()).strip("-") or "capture"
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        return f"{timestamp}-{slug}-{uuid4().hex[:8]}.json"

    def _append_artifact_suffix(self, artifact_name: str, suffix: str) -> str:
        stem = Path(artifact_name).stem
        suffix = re.sub(r"[^a-z0-9\-]+", "-", suffix.lower()).strip("-")
        return f"{stem}-{suffix}.json"

    def _resolve_output_dir(self, base_dir: Path, *, mode_subdir: str | None = None) -> Path:
        output_dir = base_dir
        if not output_dir.is_absolute():
            output_dir = self._repo_root() / output_dir
        if mode_subdir:
            output_dir = output_dir / mode_subdir
        return output_dir

    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[2]
