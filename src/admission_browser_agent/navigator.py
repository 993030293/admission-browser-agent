"""Heuristic one-hop navigation helpers for admissions link discovery."""

from __future__ import annotations

import re

from .models import (
    AggregationOutcome,
    CandidateLink,
    ExtractedProgramInfo,
    FieldAggregationDecision,
    FieldValueCandidateDebug,
    ScoredCandidateLink,
    ScoredProgramResult,
)

DEFAULT_TOP_K = 5
FOLLOW_UP_TOP_K = 2

_LINK_POSITIVE_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"\badmissions?\b"), 5),
    (re.compile(r"\bapply\b"), 4),
    (re.compile(r"\bapplications?\b"), 4),
    (re.compile(r"\brequirements?\b"), 4),
    (re.compile(r"\bdeadline(?:s)?\b"), 4),
    (re.compile(r"\btuition\b"), 4),
    (re.compile(r"\bfees?\b"), 4),
    (re.compile(r"\bfaq\b|\bfrequently asked questions\b"), 2),
    (re.compile(r"\benglish\b"), 2),
    (re.compile(r"\bielts\b"), 3),
    (re.compile(r"\btoefl\b"), 3),
)
_LINK_NEGATIVE_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"\bnews\b"), 5),
    (re.compile(r"\bcontact\b"), 4),
    (re.compile(r"\bcurrent students?\b"), 5),
    (re.compile(r"\bsocial\b"), 4),
    (re.compile(r"\bposter\b"), 4),
    (re.compile(r"\bvideos?\b"), 4),
    (re.compile(r"\byoutube\b"), 5),
    (re.compile(r"\bfacebook\b"), 4),
    (re.compile(r"\binstagram\b"), 4),
    (re.compile(r"\blinkedin\b"), 4),
    (re.compile(r"\btwitter\b"), 4),
)
_ADMISSIONS_DISCOVERY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\badmissions?\b"),
    re.compile(r"\bapply\b"),
    re.compile(r"\bapplications?\b"),
)
_DECISION_FIELD_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\brequirements?\b"),
    re.compile(r"\bdeadline(?:s)?\b"),
    re.compile(r"\benglish\b"),
    re.compile(r"\bielts\b"),
    re.compile(r"\btoefl\b"),
)
_FEE_DISCOVERY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\btuition\b"),
    re.compile(r"\bfees?\b"),
    re.compile(r"\bprogramme fees?\b"),
    re.compile(r"\bprogram fees?\b"),
)
_ENGLISH_DISCOVERY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\benglish\b"),
    re.compile(r"\bielts\b"),
    re.compile(r"\btoefl\b"),
)
_FAQ_DISCOVERY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bfaq\b"),
    re.compile(r"\bfrequently asked questions\b"),
)
_FOLLOW_UP_FIELD_PATTERNS: dict[str, tuple[tuple[re.Pattern[str], int], ...]] = {
    "deadline": (
        (re.compile(r"\bapplication deadline(?:s)?\b"), 7),
        (re.compile(r"\bdeadline(?:s)?\b"), 6),
        (re.compile(r"\bapply(?:\s+now)?\b"), 5),
        (re.compile(r"\bapplications?\b"), 4),
        (re.compile(r"\badmissions?\b"), 4),
        (re.compile(r"\badmission procedure\b"), 5),
        (re.compile(r"\bimportant dates\b"), 4),
        (re.compile(r"\bkey dates\b"), 4),
        (re.compile(r"\bschedule\b"), 3),
    ),
    "tuition": (
        (re.compile(r"\btuition(?:\s+fees?)?\b"), 6),
        (re.compile(r"\btuition and fees\b"), 7),
        (re.compile(r"\b(?:programme|program)\s+fees?\b"), 7),
        (re.compile(r"\b(?:programme|program)\s+costs?\b"), 5),
        (re.compile(r"\bprogramme\b"), 2),
        (re.compile(r"\bprogram\b"), 2),
        (re.compile(r"\bfees?\b"), 4),
        (re.compile(r"\bcosts?\b"), 3),
    ),
    "english_requirement": (
        (re.compile(r"\benglish(?:\s+language)?\b"), 5),
        (re.compile(r"\benglish language requirements?\b"), 7),
        (re.compile(r"\blanguage requirements?\b"), 6),
        (re.compile(r"\blanguage proficiency\b"), 6),
        (re.compile(r"\benglish proficiency\b"), 6),
        (re.compile(r"\bielts\b"), 6),
        (re.compile(r"\btoefl\b"), 6),
        (re.compile(r"\bmedium of instruction\b"), 4),
        (re.compile(r"\bexempt(?:ion|ed)?\b"), 3),
        (re.compile(r"\bwaiv(?:e|er|ers)\b"), 3),
    ),
}
_FOLLOW_UP_SHARED_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"\bfaq\b|\bfrequently asked questions\b"), 2),
)

_FIELD_HINT_KEYWORDS: dict[str, tuple[tuple[str, int], ...]] = {
    "program_name": (
        ("programme information", 6),
        ("program information", 6),
        ("overview", 5),
        ("programme", 3),
        ("program", 3),
        ("master", 2),
        ("msc", 2),
    ),
    "department": (
        ("department", 8),
        ("school", 6),
        ("faculty", 6),
        ("college", 5),
        ("about", 2),
        ("programme information", 2),
    ),
    "duration": (
        ("duration", 8),
        ("study mode", 5),
        ("full-time", 4),
        ("part-time", 4),
        ("programme information", 2),
        ("program information", 2),
        ("overview", 1),
    ),
    "deadline": (
        ("application deadline", 6),
        ("application deadlines", 6),
        ("admission procedure", 5),
        ("admissions", 5),
        ("admission", 4),
        ("deadline", 3),
        ("admission", 2),
        ("application", 2),
        ("apply", 2),
        ("schedule", 2),
        ("important dates", 2),
        ("key dates", 2),
        ("round", 1),
    ),
    "tuition": (
        ("programme information", 6),
        ("program information", 6),
        ("overview", 4),
        ("programme fee", 6),
        ("program fee", 6),
        ("programme", 3),
        ("program", 3),
        ("tuition", 3),
        ("fee", 3),
        ("fees", 3),
        ("cost", 2),
    ),
    "english_requirement": (
        ("english faq", 8),
        ("graduate school requirements", 8),
        ("admissions requirements", 6),
        ("admission requirements", 6),
        ("faq", 4),
        ("english", 3),
        ("language", 2),
        ("ielts", 3),
        ("toefl", 3),
        ("pte", 2),
        ("duolingo", 2),
        ("proficiency", 2),
        ("instruction", 1),
    ),
    "academic_requirement": (
        ("minimum admission requirements", 8),
        ("admissions requirements", 7),
        ("admission requirements", 7),
        ("graduate school requirements", 6),
        ("admissions", 5),
        ("academic", 2),
        ("admission", 2),
        ("entry", 2),
        ("requirement", 2),
        ("requirements", 2),
        ("eligibility", 2),
        ("qualification", 1),
    ),
    "prerequisite_keywords": (
        ("minimum admission requirements", 8),
        ("admissions requirements", 7),
        ("admission requirements", 7),
        ("admissions", 5),
        ("admission", 1),
        ("requirement", 2),
        ("requirements", 2),
        ("prerequisite", 3),
        ("background", 2),
        ("curriculum", 1),
    ),
}
_CURRENCY_PATTERN = re.compile(r"\b(?:HK\$|HKD|US\$|USD|EUR|GBP|\$)\s*\d[\d,]*(?:\.\d{2})?\b", re.IGNORECASE)
_YEAR_PATTERN = re.compile(r"\b20\d{2}\b")
_MONTH_PATTERN = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
    re.IGNORECASE,
)
_PROGRAM_WORD_PATTERN = re.compile(r"\b(master|doctor|bachelor|msc|phd|ma|mba|mphil)\b", re.IGNORECASE)
_DEADLINE_VALUE_REJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bplease visit\b", re.IGNORECASE),
    re.compile(r"\bread article\b", re.IGNORECASE),
    re.compile(r"\bfor details?\b", re.IGNORECASE),
    re.compile(r"\bapplication method\b", re.IGNORECASE),
)
_DEADLINE_VALUE_ACCEPTANCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b20\d{2}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\brolling\b", re.IGNORECASE),
    re.compile(r"\bround\s*\d\b", re.IGNORECASE),
)
_TUITION_VALUE_REJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bapplication fees?\b", re.IGNORECASE),
    re.compile(r"\bcaution money\b", re.IGNORECASE),
    re.compile(r"\bstudent activity fee\b", re.IGNORECASE),
    re.compile(r"\bgraduation\b", re.IGNORECASE),
    re.compile(r"\bre-?examination\b", re.IGNORECASE),
    re.compile(r"\brepeating\b", re.IGNORECASE),
    re.compile(r"\btuition fee reduction\b", re.IGNORECASE),
    re.compile(r"\bfee reduction\b", re.IGNORECASE),
    re.compile(r"\bcredit transfer\b", re.IGNORECASE),
    re.compile(r"\bexemption\b", re.IGNORECASE),
    re.compile(r"\bmicromasters?\b", re.IGNORECASE),
)
_TUITION_CONTEXT_NOISE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bwaiv(?:er|ed|ing)?\b", re.IGNORECASE),
    re.compile(r"\bscholarship\b", re.IGNORECASE),
    re.compile(r"\bfellowship\b", re.IGNORECASE),
    re.compile(r"\bftss\b", re.IGNORECASE),
    re.compile(r"\bfinancial aid\b", re.IGNORECASE),
    re.compile(r"\bsubsid(?:y|ies|ized|ised)\b", re.IGNORECASE),
)


def score_candidate_link(candidate: CandidateLink) -> int:
    """Score a candidate link using URL and anchor-text keywords."""

    anchor_text = _normalize_link_text(candidate.anchor_text)
    url_text = _normalize_link_text(candidate.url)
    combined_text = " ".join(part for part in (anchor_text, url_text) if part)

    score = _score_link_component(anchor_text, multiplier=2)
    score += _score_link_component(url_text, multiplier=1)

    if _contains_any(combined_text, _ADMISSIONS_DISCOVERY_PATTERNS) and _contains_any(
        combined_text,
        _DECISION_FIELD_PATTERNS,
    ):
        score += 3

    if _contains_any(combined_text, _FEE_DISCOVERY_PATTERNS):
        score += 3

    if _contains_any(combined_text, _ENGLISH_DISCOVERY_PATTERNS):
        score += 2

    if _contains_any(combined_text, _FAQ_DISCOVERY_PATTERNS) and (
        _contains_any(combined_text, _ADMISSIONS_DISCOVERY_PATTERNS)
        or _contains_any(combined_text, _FEE_DISCOVERY_PATTERNS)
        or _contains_any(combined_text, _ENGLISH_DISCOVERY_PATTERNS)
    ):
        score += 1

    if _contains_any(combined_text, _LINK_NEGATIVE_PATTERNS) and not (
        _contains_any(combined_text, _ADMISSIONS_DISCOVERY_PATTERNS)
        or _contains_any(combined_text, _FEE_DISCOVERY_PATTERNS)
        or _contains_any(combined_text, _ENGLISH_DISCOVERY_PATTERNS)
    ):
        score -= 2

    return score


def score_candidate_links(candidates: list[CandidateLink]) -> list[ScoredCandidateLink]:
    """Score all discovered same-domain candidate links deterministically."""

    scored = [
        ScoredCandidateLink(candidate=candidate, relevance_score=score_candidate_link(candidate))
        for candidate in candidates
    ]
    scored.sort(
        key=lambda item: (
            -item.relevance_score,
            len(item.candidate.url),
            item.candidate.url,
            item.candidate.anchor_text.lower(),
        )
    )
    return scored


def score_follow_up_candidate_link(
    candidate: CandidateLink,
    *,
    missing_fields: set[str],
) -> int:
    """Score constrained secondary-scan links for missing high-value fields."""

    anchor_text = _normalize_link_text(candidate.anchor_text)
    url_text = _normalize_link_text(candidate.url)
    positive_patterns = _follow_up_positive_patterns(missing_fields)
    combined_text = " ".join(part for part in (anchor_text, url_text) if part)

    if not _contains_any(combined_text, positive_patterns):
        return 0

    score = _score_pattern_set(anchor_text, positive_patterns, multiplier=2)
    score += _score_pattern_set(url_text, positive_patterns, multiplier=1)
    # Preserve a small amount of the general admissions score as a fallback signal.
    score += min(max(score_candidate_link(candidate), 0), 6)
    score -= _score_pattern_set(anchor_text, _LINK_NEGATIVE_PATTERNS, multiplier=2)
    score -= _score_pattern_set(url_text, _LINK_NEGATIVE_PATTERNS, multiplier=1)
    return score


def score_follow_up_candidate_links(
    candidates: list[CandidateLink],
    *,
    missing_fields: set[str],
) -> list[ScoredCandidateLink]:
    """Score only the constrained follow-up candidates relevant to missing fields."""

    scored = [
        ScoredCandidateLink(
            candidate=candidate,
            relevance_score=score_follow_up_candidate_link(
                candidate,
                missing_fields=missing_fields,
            ),
        )
        for candidate in candidates
    ]
    scored.sort(
        key=lambda item: (
            -item.relevance_score,
            len(item.candidate.url),
            item.candidate.url,
            item.candidate.anchor_text.lower(),
        )
    )
    return scored


def select_follow_up_candidate_links(
    candidates: list[CandidateLink],
    *,
    missing_fields: set[str],
    top_k: int = FOLLOW_UP_TOP_K,
) -> list[ScoredCandidateLink]:
    """Select a tiny positive-scoring follow-up set for missing tuition/English fields."""

    scored = score_follow_up_candidate_links(
        candidates,
        missing_fields=missing_fields,
    )
    scored = [item for item in scored if item.relevance_score > 0]
    return scored[:top_k]


def select_top_candidate_links(
    candidates: list[CandidateLink],
    *,
    top_k: int = DEFAULT_TOP_K,
) -> list[ScoredCandidateLink]:
    """Return the top same-domain candidate links with positive relevance."""

    scored = score_candidate_links(candidates)
    scored = [item for item in scored if item.relevance_score > 0]
    return scored[:top_k]


def score_extracted_program(result: ExtractedProgramInfo) -> int:
    """Score extracted program information by field completeness."""

    score = 0
    if result.program_name:
        score += 2
    if result.department:
        score += 1
    if result.duration:
        score += 1
    if result.deadline:
        score += 2
    if result.tuition:
        score += 2
    if result.english_requirement:
        score += 2
    if result.academic_requirement:
        score += 2
    if result.prerequisite_keywords:
        score += min(len(result.prerequisite_keywords), 3)
    if result.foundation_mentions:
        score += sum(1 for value in result.foundation_mentions.values() if value)
    return score


def select_best_program_result(
    results: list[ExtractedProgramInfo],
) -> ScoredProgramResult | None:
    """Pick the most complete extracted result from inspected pages."""

    if not results:
        return None

    scored = [
        ScoredProgramResult(result=result, completeness_score=score_extracted_program(result))
        for result in results
    ]
    scored.sort(
        key=lambda item: (
            -item.completeness_score,
            -int(bool(item.result.department)),
            -int(bool(item.result.duration)),
            -int(bool(item.result.deadline)),
            -int(bool(item.result.tuition)),
            -int(bool(item.result.english_requirement)),
            -int(bool(item.result.academic_requirement)),
            -len(item.result.prerequisite_keywords),
            -int(bool(item.result.program_name)),
            item.result.source_url,
        )
    )
    return scored[0]


def aggregate_program_results(
    results: list[ExtractedProgramInfo],
    *,
    page_hint_text_by_url: dict[str, str] | None = None,
) -> ExtractedProgramInfo | None:
    """Aggregate field values across inspected pages with per-field source tracing."""

    outcome = aggregate_program_results_with_debug(
        results,
        page_hint_text_by_url=page_hint_text_by_url,
    )
    if outcome is None:
        return None
    return outcome.aggregated_result


def aggregate_program_results_with_debug(
    results: list[ExtractedProgramInfo],
    *,
    page_hint_text_by_url: dict[str, str] | None = None,
) -> AggregationOutcome | None:
    """Aggregate field values across inspected pages with decision provenance."""

    primary = select_best_program_result(results)
    if primary is None:
        return None

    page_hint_text_by_url = page_hint_text_by_url or {}
    aggregated = ExtractedProgramInfo(
        source_url=primary.result.source_url,
        page_title=primary.result.page_title,
        field_sources={},
    )
    decisions: dict[str, FieldAggregationDecision] = {}

    for field_name in (
        "program_name",
        "department",
        "duration",
        "deadline",
        "tuition",
        "english_requirement",
        "academic_requirement",
    ):
        decision = _build_scalar_field_decision(
            field_name,
            results,
            page_hint_text_by_url=page_hint_text_by_url,
        )
        decisions[field_name] = decision
        if decision.selected_value is None:
            continue

        setattr(aggregated, field_name, decision.selected_value)
        aggregated.field_sources[field_name] = decision.source_urls

    prerequisite_keywords, prerequisite_sources, prerequisite_candidates = _merge_prerequisite_keywords(
        results,
        page_hint_text_by_url=page_hint_text_by_url,
    )
    aggregated.prerequisite_keywords = prerequisite_keywords
    decisions["prerequisite_keywords"] = FieldAggregationDecision(
        field_name="prerequisite_keywords",
        selected_value=prerequisite_keywords,
        source_urls=prerequisite_sources,
        strategy="merge_unique_keywords_from_ranked_pages",
        candidates=prerequisite_candidates,
    )
    if prerequisite_sources:
        aggregated.field_sources["prerequisite_keywords"] = prerequisite_sources

    foundation_mentions, foundation_sources, foundation_candidates = _merge_foundation_mentions(
        results,
        page_hint_text_by_url=page_hint_text_by_url,
    )
    aggregated.foundation_mentions = foundation_mentions
    decisions["foundation_mentions"] = FieldAggregationDecision(
        field_name="foundation_mentions",
        selected_value=foundation_mentions,
        source_urls=foundation_sources,
        strategy="merge_true_flags_from_ranked_pages",
        candidates=foundation_candidates,
    )
    if foundation_sources:
        aggregated.field_sources["foundation_mentions"] = foundation_sources

    return AggregationOutcome(aggregated_result=aggregated, decisions=decisions)


def _build_scalar_field_decision(
    field_name: str,
    results: list[ExtractedProgramInfo],
    *,
    page_hint_text_by_url: dict[str, str],
) -> FieldAggregationDecision:
    candidates: list[FieldValueCandidateDebug] = []
    selected_index: int | None = None

    for result in results:
        value = getattr(result, field_name)
        hint_score = _field_hint_score(field_name, result, page_hint_text_by_url=page_hint_text_by_url)
        is_eligible = _is_field_value_eligible(field_name, value)
        specificity_score = _field_specificity_score(field_name, value) if is_eligible and isinstance(value, str) else 0
        candidates.append(
            FieldValueCandidateDebug(
                source_url=result.source_url,
                page_title=result.page_title,
                value=value,
                hint_score=hint_score,
                specificity_score=specificity_score,
                completeness_score=score_extracted_program(result),
                eligible=is_eligible,
            )
        )

    eligible_candidates = [
        (index, candidate)
        for index, candidate in enumerate(candidates)
        if candidate.eligible and isinstance(candidate.value, str)
    ]
    if eligible_candidates:
        eligible_candidates.sort(
            key=lambda item: _scalar_field_sort_key(
                field_name,
                item[1],
            )
        )
        selected_index = eligible_candidates[0][0]
        candidates[selected_index].selected = True
        selected_value = candidates[selected_index].value
        source_urls = [candidates[selected_index].source_url]
    else:
        selected_value = None
        source_urls = []

    strategy = _field_strategy(field_name)
    candidates.sort(key=lambda candidate: _field_candidate_display_sort_key(candidate))

    return FieldAggregationDecision(
        field_name=field_name,
        selected_value=selected_value,
        source_urls=source_urls,
        strategy=strategy,
        candidates=candidates,
    )


def _scalar_field_sort_key(
    field_name: str,
    candidate: FieldValueCandidateDebug,
) -> tuple[int, int, int, int, str]:
    if field_name == "program_name":
        return (
            -candidate.specificity_score,
            -candidate.hint_score,
            -candidate.completeness_score,
            -len(str(candidate.value)),
            candidate.source_url,
        )
    return (
        -candidate.hint_score,
        -candidate.specificity_score,
        -candidate.completeness_score,
        -len(str(candidate.value)),
        candidate.source_url,
    )


def _merge_prerequisite_keywords(
    results: list[ExtractedProgramInfo],
    *,
    page_hint_text_by_url: dict[str, str],
) -> tuple[list[str], list[str], list[FieldValueCandidateDebug]]:
    ordered_results = sorted(
        results,
        key=lambda result: (
            -_field_hint_score(
                "prerequisite_keywords",
                result,
                page_hint_text_by_url=page_hint_text_by_url,
            ),
            -score_extracted_program(result),
            result.source_url,
        ),
    )

    merged_keywords: list[str] = []
    merged_sources: list[str] = []
    seen_keywords: set[str] = set()
    candidate_debug: list[FieldValueCandidateDebug] = []

    for result in ordered_results:
        contributed = False
        value = list(result.prerequisite_keywords)
        for keyword in result.prerequisite_keywords:
            if keyword in seen_keywords:
                continue
            seen_keywords.add(keyword)
            merged_keywords.append(keyword)
            contributed = True
        if contributed and result.source_url not in merged_sources:
            merged_sources.append(result.source_url)
        candidate_debug.append(
            FieldValueCandidateDebug(
                source_url=result.source_url,
                page_title=result.page_title,
                value=value,
                hint_score=_field_hint_score(
                    "prerequisite_keywords",
                    result,
                    page_hint_text_by_url=page_hint_text_by_url,
                ),
                specificity_score=len(value),
                completeness_score=score_extracted_program(result),
                eligible=bool(value),
                selected=contributed,
            )
        )

    candidate_debug.sort(key=lambda candidate: _field_candidate_display_sort_key(candidate))
    return merged_keywords, merged_sources, candidate_debug


def _merge_foundation_mentions(
    results: list[ExtractedProgramInfo],
    *,
    page_hint_text_by_url: dict[str, str],
) -> tuple[dict[str, bool], list[str], list[FieldValueCandidateDebug]]:
    ordered_results = sorted(
        results,
        key=lambda result: (
            -_field_hint_score(
                "academic_requirement",
                result,
                page_hint_text_by_url=page_hint_text_by_url,
            ),
            -score_extracted_program(result),
            result.source_url,
        ),
    )

    merged_mentions = {
        "statistics": False,
        "programming": False,
        "mathematics": False,
    }
    merged_sources: list[str] = []
    candidate_debug: list[FieldValueCandidateDebug] = []

    for result in ordered_results:
        mentions = {
            "statistics": bool(result.foundation_mentions.get("statistics", False)),
            "programming": bool(result.foundation_mentions.get("programming", False)),
            "mathematics": bool(result.foundation_mentions.get("mathematics", False)),
        }
        contributed = False
        for key, value in mentions.items():
            if value and not merged_mentions[key]:
                merged_mentions[key] = True
                contributed = True
        if contributed and result.source_url not in merged_sources:
            merged_sources.append(result.source_url)
        candidate_debug.append(
            FieldValueCandidateDebug(
                source_url=result.source_url,
                page_title=result.page_title,
                value=mentions,
                hint_score=_field_hint_score(
                    "academic_requirement",
                    result,
                    page_hint_text_by_url=page_hint_text_by_url,
                ),
                specificity_score=sum(1 for value in mentions.values() if value),
                completeness_score=score_extracted_program(result),
                eligible=any(mentions.values()),
                selected=contributed,
            )
        )

    candidate_debug.sort(key=lambda candidate: _field_candidate_display_sort_key(candidate))
    return merged_mentions, merged_sources, candidate_debug


def _field_hint_score(
    field_name: str,
    result: ExtractedProgramInfo,
    *,
    page_hint_text_by_url: dict[str, str],
) -> int:
    haystack = _normalize_hint_text(page_hint_text_by_url.get(
        result.source_url,
        f"{result.page_title} {result.source_url}",
    ))
    score = 0
    for keyword, weight in _FIELD_HINT_KEYWORDS[field_name]:
        if keyword in haystack:
            score += weight
    return score


def _is_field_value_eligible(field_name: str, value: str | list[str] | dict[str, bool] | None) -> bool:
    if value is None:
        return False
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return any(bool(item) for item in value.values())
    normalized = value.strip()
    if not normalized:
        return False
    if field_name == "deadline":
        lowered = normalized.lower()
        if any(pattern.search(lowered) for pattern in _DEADLINE_VALUE_REJECTION_PATTERNS):
            return False
        if "http" in lowered and not (_MONTH_PATTERN.search(normalized) and _YEAR_PATTERN.search(normalized)):
            return False
        has_date_signal = bool(_MONTH_PATTERN.search(normalized) and _YEAR_PATTERN.search(normalized)) or any(
            pattern.search(normalized) for pattern in _DEADLINE_VALUE_ACCEPTANCE_PATTERNS
        )
        if not has_date_signal:
            return False
    if field_name == "department":
        lowered = normalized.lower()
        if not any(keyword in lowered for keyword in ("department", "school", "faculty", "college", "institute")):
            return False
        if len(normalized.split()) < 3:
            return False
    if field_name == "duration":
        lowered = normalized.lower()
        if not (
            re.search(r"\b\d(?:\.\d+)?\s*(?:year|years|month|months)\b", lowered)
            or (
                any(keyword in lowered for keyword in ("full-time", "part-time"))
                and any(keyword in lowered for keyword in ("year", "years", "month", "months"))
            )
        ):
            return False
    if field_name == "tuition":
        lowered = normalized.lower()
        if not _CURRENCY_PATTERN.search(normalized):
            return False
        if any(pattern.search(lowered) for pattern in _TUITION_VALUE_REJECTION_PATTERNS):
            return False
        if any(pattern.search(lowered) for pattern in _TUITION_CONTEXT_NOISE_PATTERNS):
            return False
        amounts = _extract_currency_amounts(normalized)
        if amounts and max(amounts) < 50_000:
            return False
        if "government-funded programmes" in lowered and "master of" not in lowered and "mdasc" not in lowered:
            return False
    return True


def _extract_currency_amounts(text: str) -> list[int]:
    amounts: list[int] = []
    for match in _CURRENCY_PATTERN.findall(text):
        number_match = re.search(r"\d[\d,]*(?:\.\d{2})?", match)
        if number_match is None:
            continue
        amounts.append(int(float(number_match.group(0).replace(",", ""))))
    return amounts


def _field_specificity_score(field_name: str, value: str) -> int:
    normalized = value.strip()
    word_count = len(normalized.split())

    if field_name == "program_name":
        return (20 if _PROGRAM_WORD_PATTERN.search(normalized) else 0) + word_count + len(normalized)
    if field_name == "department":
        return (
            (20 if any(keyword in normalized.lower() for keyword in ("department", "school", "faculty", "college")) else 0)
            + word_count
            + len(normalized)
        )
    if field_name == "duration":
        return (
            (20 if re.search(r"\byears?\b|\bmonths?\b", normalized, re.IGNORECASE) else 0)
            + word_count
            + len(normalized)
        )
    if field_name == "deadline":
        return (
            (20 if _YEAR_PATTERN.search(normalized) else 0)
            + (10 if _MONTH_PATTERN.search(normalized) else 0)
            + len(normalized)
        )
    if field_name == "tuition":
        digit_count = sum(character.isdigit() for character in normalized)
        return (
            (20 if _CURRENCY_PATTERN.search(normalized) else 0)
            + digit_count
            + len(normalized)
        )
    if field_name in {"english_requirement", "academic_requirement"}:
        return word_count * 2 + len(normalized)
    return len(normalized)


def _field_candidate_display_sort_key(candidate: FieldValueCandidateDebug) -> tuple[int, int, int, str]:
    return (
        -int(candidate.selected),
        -int(candidate.eligible),
        -candidate.hint_score,
        candidate.source_url,
    )


def _field_strategy(field_name: str) -> str:
    if field_name == "program_name":
        return "prefer_non_null_value_then_program_specificity_then_page_hint"
    return "prefer_non_null_value_then_field_hint_then_specificity"


def _score_link_component(text: str, *, multiplier: int) -> int:
    return _score_pattern_set(text, _LINK_POSITIVE_PATTERNS, multiplier=multiplier) - _score_pattern_set(
        text,
        _LINK_NEGATIVE_PATTERNS,
        multiplier=multiplier,
    )


def _contains_any(
    text: str,
    patterns: tuple[re.Pattern[str], ...] | tuple[tuple[re.Pattern[str], int], ...],
) -> bool:
    if not text:
        return False

    for item in patterns:
        pattern = item[0] if isinstance(item, tuple) else item
        if pattern.search(text):
            return True
    return False


def _normalize_link_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _normalize_hint_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _follow_up_positive_patterns(
    missing_fields: set[str],
) -> tuple[tuple[re.Pattern[str], int], ...]:
    patterns: list[tuple[re.Pattern[str], int]] = []
    for field_name in sorted(missing_fields):
        patterns.extend(_FOLLOW_UP_FIELD_PATTERNS.get(field_name, ()))
    patterns.extend(_FOLLOW_UP_SHARED_PATTERNS)
    return tuple(patterns)


def _score_pattern_set(
    text: str,
    patterns: tuple[tuple[re.Pattern[str], int], ...],
    *,
    multiplier: int,
) -> int:
    score = 0
    for pattern, weight in patterns:
        if pattern.search(text):
            score += weight * multiplier
    return score
