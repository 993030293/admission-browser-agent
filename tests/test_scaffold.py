"""Smoke tests for the admissions browser agent scaffold."""

from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_placeholder_modules_import() -> None:
    modules = [
        "admission_browser_agent",
        "admission_browser_agent.browser",
        "admission_browser_agent.cli",
        "admission_browser_agent.config",
        "admission_browser_agent.evaluation",
        "admission_browser_agent.exports",
        "admission_browser_agent.extractor",
        "admission_browser_agent.models",
        "admission_browser_agent.navigator",
        "admission_browser_agent.pipeline",
        "admission_browser_agent.sources",
        "admission_browser_agent.sources.base",
        "admission_browser_agent.targets",
    ]

    for module_name in modules:
        importlib.import_module(module_name)


def test_dataclasses_can_be_instantiated() -> None:
    from admission_browser_agent.config import BrowserConfig, RunConfig
    from admission_browser_agent.models import CandidateLink
    from admission_browser_agent.models import (
        AggregationOutcome,
        CandidateLinkDebug,
        CrawlRequest,
        DebugRunReport,
        ExtractedProgramInfo,
        ExtractionResult,
        FieldAggregationDecision,
        FieldValueCandidateDebug,
        FollowUpDiscoverySourceDebug,
        OfficialSeedPage,
        OfficialSeedRegistry,
        OfficialTargetDefinition,
        PageInspectionDebug,
        ProgramRecord,
        RawPageCapture,
        ScoredCandidateLink,
        ScoredProgramResult,
    )

    browser = BrowserConfig()
    run_config = RunConfig(browser=browser)
    request = CrawlRequest(
        university="Example University",
        seed_url="https://www.example.edu/graduate/admissions",
        program_hint="Computer Science PhD",
    )
    record = ProgramRecord(
        university=request.university,
        program_name="Computer Science PhD",
        admissions_url=request.seed_url,
    )
    raw_capture = RawPageCapture(
        source_url=request.seed_url,
        page_title="Graduate Admissions",
        body_text="Apply by December 1.",
    )
    official_seed_page = OfficialSeedPage(
        page_type="admissions",
        url=request.seed_url,
        priority=1,
        intended_fields=["deadline"],
    )
    target_definition = OfficialTargetDefinition(
        university=request.university,
        program_code="EXAMPLE_MSCS",
        program_name="Computer Science PhD",
        tier="target",
        seed_pages=[official_seed_page],
    )
    registry = OfficialSeedRegistry(targets=[target_definition])
    extracted = ExtractedProgramInfo(
        source_url=request.seed_url,
        page_title=raw_capture.page_title,
        program_name="Computer Science PhD",
        prerequisite_keywords=["python"],
    )
    candidate_link = CandidateLink(anchor_text="Admissions", url=request.seed_url)
    candidate_debug = CandidateLinkDebug(anchor_text="Admissions", url=request.seed_url, relevance_score=3)
    field_candidate = FieldValueCandidateDebug(
        source_url=request.seed_url,
        page_title=raw_capture.page_title,
        value="Computer Science PhD",
        hint_score=3,
        specificity_score=5,
        completeness_score=3,
        eligible=True,
        selected=True,
    )
    field_decision = FieldAggregationDecision(
        field_name="program_name",
        selected_value="Computer Science PhD",
        source_urls=[request.seed_url],
        strategy="prefer_non_null_value_then_program_specificity_then_page_hint",
        candidates=[field_candidate],
    )
    inspection_debug = PageInspectionDebug(
        source_url=request.seed_url,
        page_title=raw_capture.page_title,
        raw_output_path="data/raw/example.json",
        extracted=extracted,
        page_type="admissions",
        priority=1,
        intended_fields=["deadline"],
    )
    follow_up_source = FollowUpDiscoverySourceDebug(
        source_url=request.seed_url,
        page_title=raw_capture.page_title,
        source_stage="seed",
        candidate_count=1,
    )
    run_debug = DebugRunReport(
        seed_url=request.seed_url,
        seed_page_title=raw_capture.page_title,
        run_mode="official_seed",
        program_code=target_definition.program_code,
        program_name=target_definition.program_name,
        target_tier=target_definition.tier,
        discovered_candidate_links=[candidate_debug],
        inspected_pages=[inspection_debug],
        follow_up_discovery_sources=[follow_up_source],
        aggregation_decisions={"program_name": field_decision},
        final_result=extracted,
    )
    aggregation_outcome = AggregationOutcome(
        aggregated_result=extracted,
        decisions={"program_name": field_decision},
    )
    scored_link = ScoredCandidateLink(candidate=candidate_link, relevance_score=3)
    scored_result = ScoredProgramResult(result=extracted, completeness_score=3)
    result = ExtractionResult(request=request, records=[record])

    assert run_config.browser.headless is True
    assert raw_capture.page_title == "Graduate Admissions"
    assert extracted.program_name == "Computer Science PhD"
    assert candidate_debug.relevance_score == 3
    assert candidate_debug.eligible is False
    assert candidate_debug.fetched is False
    assert candidate_debug.rejection_reason is None
    assert field_decision.source_urls == [request.seed_url]
    assert registry.targets[0].program_code == "EXAMPLE_MSCS"
    assert run_debug.seed_page_title == "Graduate Admissions"
    assert run_debug.run_mode == "official_seed"
    assert run_debug.follow_up_discovery_sources[0].candidate_count == 1
    assert inspection_debug.page_type == "admissions"
    assert aggregation_outcome.aggregated_result.program_name == "Computer Science PhD"
    assert scored_link.relevance_score == 3
    assert scored_result.completeness_score == 3
    assert result.records[0].program_name == "Computer Science PhD"


def test_cli_help_exits_cleanly() -> None:
    from admission_browser_agent.cli import main

    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])

    assert excinfo.value.code == 0


def test_cli_parser_includes_required_arguments() -> None:
    from admission_browser_agent.cli import build_parser

    parser = build_parser()
    help_text = parser.format_help()

    assert "admission-browser-agent" in help_text
    assert "--mode" in help_text
    assert "generic" in help_text
    assert "--university" in help_text
    assert "--seed-url" in help_text
    assert "--benchmark" in help_text
    assert "--gold-dir" in help_text
    assert "--propose-gold-draft" in help_text
    assert "--gold-draft-dir" in help_text
    assert "--program-code" in help_text
    assert "--all-programs" in help_text
    assert "--query" in help_text
    assert "--export-formats" in help_text
    assert "mvp" in help_text


def test_browser_session_fetches_page_with_fake_playwright(monkeypatch: pytest.MonkeyPatch) -> None:
    from admission_browser_agent.browser import BrowserSession

    sync_api = types.ModuleType("playwright.sync_api")

    class FakePlaywrightError(Exception):
        pass

    class FakeLocator:
        def inner_text(self, timeout: int) -> str:
            assert timeout == 30_000
            return "Visible body text"

    class FakePage:
        def __init__(self) -> None:
            self.url = ""
            self.load_states: list[str] = []
            self.waited_timeouts: list[int] = []
            self.scroll_calls = 0

        def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
            assert wait_until == "domcontentloaded"
            assert timeout == 30_000
            self.url = url

        def wait_for_load_state(self, state: str, *, timeout: int) -> None:
            assert state in {"domcontentloaded", "networkidle"}
            if state == "domcontentloaded":
                assert timeout == 30_000
            else:
                assert timeout == 5_000
            self.load_states.append(state)

        def wait_for_timeout(self, timeout: int) -> None:
            assert timeout in {1_500, 1_000}
            self.waited_timeouts.append(timeout)

        def evaluate(self, script: str):
            assert "window.scrollTo" in script
            self.scroll_calls += 1
            return None

        def title(self) -> str:
            return "Example Admissions"

        def locator(self, selector: str) -> FakeLocator:
            assert selector == "body"
            return FakeLocator()

        def close(self) -> None:
            return None

    class FakeContext:
        def new_page(self) -> FakePage:
            return FakePage()

        def close(self) -> None:
            return None

    class FakeBrowser:
        def new_context(self, **kwargs: object) -> FakeContext:
            assert kwargs == {}
            return FakeContext()

        def close(self) -> None:
            return None

    class FakeBrowserType:
        def launch(self, *, headless: bool) -> FakeBrowser:
            assert headless is True
            return FakeBrowser()

    class FakePlaywright:
        def __init__(self) -> None:
            self.chromium = FakeBrowserType()

        def stop(self) -> None:
            return None

    class FakePlaywrightManager:
        def start(self) -> FakePlaywright:
            return FakePlaywright()

    def fake_sync_playwright() -> FakePlaywrightManager:
        return FakePlaywrightManager()

    sync_api.Error = FakePlaywrightError
    sync_api.sync_playwright = fake_sync_playwright

    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)

    capture = BrowserSession().fetch_page("https://example.edu/admissions")

    assert capture.source_url == "https://example.edu/admissions"
    assert capture.page_title == "Example Admissions"
    assert capture.body_text == "Visible body text"


def test_browser_session_stabilizes_before_reading_body_text(monkeypatch: pytest.MonkeyPatch) -> None:
    from admission_browser_agent.browser import BrowserSession

    sync_api = types.ModuleType("playwright.sync_api")

    class FakePlaywrightError(Exception):
        pass

    class FakeLocator:
        def __init__(self, page) -> None:
            self.page = page

        def inner_text(self, timeout: int) -> str:
            assert timeout == 30_000
            if self.page.stabilized:
                return "Programme fee: HK$339,840"
            return "Loading"

    class FakePage:
        def __init__(self) -> None:
            self.url = ""
            self.stabilized = False
            self.scroll_calls = 0

        def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
            self.url = url

        def wait_for_load_state(self, state: str, *, timeout: int) -> None:
            if state == "networkidle":
                self.stabilized = True

        def wait_for_timeout(self, timeout: int) -> None:
            assert timeout in {1_500, 1_000}
            self.stabilized = True

        def evaluate(self, script: str):
            assert "window.scrollTo" in script
            self.scroll_calls += 1
            self.stabilized = True
            return None

        def title(self) -> str:
            return "Programme"

        def locator(self, selector: str) -> FakeLocator:
            assert selector == "body"
            return FakeLocator(self)

        def close(self) -> None:
            return None

    class FakeContext:
        def new_page(self) -> FakePage:
            return FakePage()

        def close(self) -> None:
            return None

    class FakeBrowser:
        def new_context(self, **kwargs: object) -> FakeContext:
            return FakeContext()

        def close(self) -> None:
            return None

    class FakeBrowserType:
        def launch(self, *, headless: bool) -> FakeBrowser:
            return FakeBrowser()

    class FakePlaywright:
        def __init__(self) -> None:
            self.chromium = FakeBrowserType()

        def stop(self) -> None:
            return None

    class FakePlaywrightManager:
        def start(self) -> FakePlaywright:
            return FakePlaywright()

    def fake_sync_playwright() -> FakePlaywrightManager:
        return FakePlaywrightManager()

    sync_api.Error = FakePlaywrightError
    sync_api.sync_playwright = fake_sync_playwright

    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)

    capture = BrowserSession().fetch_page("https://example.edu/programme")

    assert capture.body_text == "Programme fee: HK$339,840"


def test_browser_session_prefers_richer_body_text_after_scroll(monkeypatch: pytest.MonkeyPatch) -> None:
    from admission_browser_agent.browser import BrowserSession

    sync_api = types.ModuleType("playwright.sync_api")

    class FakePlaywrightError(Exception):
        pass

    class FakeLocator:
        def __init__(self, page) -> None:
            self.page = page

        def inner_text(self, timeout: int) -> str:
            assert timeout == 30_000
            if self.page.scroll_calls == 0:
                return "Master of Data Science"
            return "Master of Data Science\nApplication deadline: December 1, 2025\nTuition fee: HK$339,840"

    class FakePage:
        def __init__(self) -> None:
            self.url = ""
            self.scroll_calls = 0

        def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
            self.url = url

        def wait_for_load_state(self, state: str, *, timeout: int) -> None:
            return None

        def wait_for_timeout(self, timeout: int) -> None:
            assert timeout in {1_500, 1_000}
            return None

        def evaluate(self, script: str):
            assert "window.scrollTo" in script
            self.scroll_calls += 1
            return None

        def title(self) -> str:
            return "Programme"

        def locator(self, selector: str) -> FakeLocator:
            assert selector == "body"
            return FakeLocator(self)

        def close(self) -> None:
            return None

    class FakeContext:
        def new_page(self) -> FakePage:
            return FakePage()

        def close(self) -> None:
            return None

    class FakeBrowser:
        def new_context(self, **kwargs: object) -> FakeContext:
            return FakeContext()

        def close(self) -> None:
            return None

    class FakeBrowserType:
        def launch(self, *, headless: bool) -> FakeBrowser:
            return FakeBrowser()

    class FakePlaywright:
        def __init__(self) -> None:
            self.chromium = FakeBrowserType()

        def stop(self) -> None:
            return None

    class FakePlaywrightManager:
        def start(self) -> FakePlaywright:
            return FakePlaywright()

    def fake_sync_playwright() -> FakePlaywrightManager:
        return FakePlaywrightManager()

    sync_api.Error = FakePlaywrightError
    sync_api.sync_playwright = fake_sync_playwright

    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)

    capture = BrowserSession().fetch_page("https://example.edu/programme")

    assert capture.body_text == (
        "Master of Data Science\nApplication deadline: December 1, 2025\nTuition fee: HK$339,840"
    )


def test_browser_session_adds_plain_text_urls_to_discovered_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from admission_browser_agent.browser import BrowserSession

    sync_api = types.ModuleType("playwright.sync_api")

    class FakePlaywrightError(Exception):
        pass

    class FakeLocator:
        def __init__(self, *, selector: str, page) -> None:
            self.selector = selector
            self.page = page

        def inner_text(self, timeout: int) -> str:
            assert self.selector == "body"
            assert timeout == 30_000
            return (
                "Admissions FAQ\n"
                "See details at https://portal.hku.hk/tpg-admissions/applying/admission-requirements\n"
            )

        def evaluate_all(self, script: str):
            assert self.selector == "a[href]"
            assert "elements.map" in script
            return []

    class FakePage:
        def __init__(self) -> None:
            self.url = ""

        def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
            self.url = url

        def wait_for_load_state(self, state: str, *, timeout: int) -> None:
            return None

        def wait_for_timeout(self, timeout: int) -> None:
            return None

        def evaluate(self, script: str):
            return None

        def title(self) -> str:
            return "FAQ"

        def locator(self, selector: str) -> FakeLocator:
            return FakeLocator(selector=selector, page=self)

        def close(self) -> None:
            return None

    class FakeContext:
        def new_page(self) -> FakePage:
            return FakePage()

        def close(self) -> None:
            return None

    class FakeBrowser:
        def new_context(self, **kwargs: object) -> FakeContext:
            return FakeContext()

        def close(self) -> None:
            return None

    class FakeBrowserType:
        def launch(self, *, headless: bool) -> FakeBrowser:
            return FakeBrowser()

    class FakePlaywright:
        def __init__(self) -> None:
            self.chromium = FakeBrowserType()

        def stop(self) -> None:
            return None

    class FakePlaywrightManager:
        def start(self) -> FakePlaywright:
            return FakePlaywright()

    def fake_sync_playwright() -> FakePlaywrightManager:
        return FakePlaywrightManager()

    sync_api.Error = FakePlaywrightError
    sync_api.sync_playwright = fake_sync_playwright

    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)

    _capture, candidates = BrowserSession().fetch_page_with_links("https://mdasc.cds.hku.hk/faq/")

    assert [candidate.url for candidate in candidates] == [
        "https://portal.hku.hk/tpg-admissions/applying/admission-requirements"
    ]


def test_extract_same_domain_candidate_links_filters_and_resolves() -> None:
    from admission_browser_agent.browser import extract_same_domain_candidate_links

    candidates = extract_same_domain_candidate_links(
        "https://example.edu/programs",
        [
            {"href": "/admissions", "text": "Admissions", "visible": True},
            {"href": "https://www.example.edu/apply", "text": "Apply now", "visible": True},
            {"href": "https://other.edu/tuition", "text": "Tuition", "visible": True},
            {"href": "#faq", "text": "FAQ", "visible": True},
            {"href": "mailto:grad@example.edu", "text": "Email", "visible": True},
            {"href": "/hidden", "text": "Hidden", "visible": False},
        ],
    )

    assert [candidate.url for candidate in candidates] == [
        "https://example.edu/admissions",
        "https://www.example.edu/apply",
    ]
    assert [candidate.anchor_text for candidate in candidates] == ["Admissions", "Apply now"]


def test_extract_same_domain_candidate_links_blocks_cross_domain_urls() -> None:
    from admission_browser_agent.browser import extract_same_domain_candidate_links

    candidates = extract_same_domain_candidate_links(
        "https://example.edu/",
        [
            {"href": "https://example.edu/faq", "text": "FAQ", "visible": True},
            {"href": "https://admissions.example.edu/apply", "text": "Apply", "visible": True},
            {"href": "https://elsewhere.edu/admissions", "text": "Admissions", "visible": True},
        ],
    )

    assert [candidate.url for candidate in candidates] == [
        "https://example.edu/faq",
        "https://admissions.example.edu/apply",
    ]


def test_extract_same_domain_candidate_links_allows_related_hku_subdomains() -> None:
    from admission_browser_agent.browser import extract_same_domain_candidate_links

    candidates = extract_same_domain_candidate_links(
        "https://mdasc.cds.hku.hk/",
        [
            {
                "href": "https://portal.hku.hk/tpg-admissions/applying/admission-requirements",
                "text": "Admissions Requirements",
                "visible": True,
            },
            {
                "href": "https://fytgs.hkust.edu.hk/admissions",
                "text": "HKUST Admissions",
                "visible": True,
            },
        ],
    )

    assert [candidate.url for candidate in candidates] == [
        "https://portal.hku.hk/tpg-admissions/applying/admission-requirements"
    ]


def test_extract_same_domain_candidate_links_keeps_cuhk_scope_strict() -> None:
    from admission_browser_agent.browser import extract_same_domain_candidate_links

    candidates = extract_same_domain_candidate_links(
        "https://mscai.erg.cuhk.edu.hk/",
        [
            {"href": "https://www.gs.cuhk.edu.hk/admissions/admissions/requirements", "text": "GS", "visible": True},
            {"href": "https://www.hku.edu.hk/", "text": "HKU", "visible": True},
            {"href": "https://www.polyu.edu.hk/", "text": "PolyU", "visible": True},
        ],
    )

    assert [candidate.url for candidate in candidates] == [
        "https://www.gs.cuhk.edu.hk/admissions/admissions/requirements"
    ]


def test_extractor_returns_structured_fields_from_synthetic_text() -> None:
    from admission_browser_agent.extractor import AdmissionsExtractor
    from admission_browser_agent.models import RawPageCapture

    capture = RawPageCapture(
        source_url="https://example.edu/admissions",
        page_title="Example University - Master of Science in Artificial Intelligence Admissions",
        body_text=(
            "Admissions\n"
            "Application deadline: December 1, 2026\n"
            "Tuition fee: HK$320,000 for the full programme\n"
            "English language requirement: IELTS 6.5 overall or TOEFL 90.\n"
            "Academic requirement: Applicants should hold a bachelor's degree in computer science, "
            "mathematics, statistics, or a related field.\n"
            "Applicants should have prior knowledge of Python, linear algebra, calculus, probability, "
            "and machine learning.\n"
        ),
    )

    result = AdmissionsExtractor().extract(capture=capture)

    assert result.program_name == "Master of Science in Artificial Intelligence"
    assert result.deadline == "December 1, 2026"
    assert result.tuition == "HK$320,000 for the full programme"
    assert result.english_requirement == "IELTS 6.5 overall or TOEFL 90."
    assert result.academic_requirement == (
        "Applicants should hold a bachelor's degree in computer science, mathematics, statistics, "
        "or a related field."
    )
    assert result.prerequisite_keywords == [
        "computer science",
        "mathematics",
        "statistics",
        "probability",
        "linear algebra",
        "calculus",
        "python",
        "machine learning",
    ]


def test_extractor_handles_missing_fields_without_crashing() -> None:
    from admission_browser_agent.extractor import AdmissionsExtractor
    from admission_browser_agent.models import RawPageCapture

    capture = RawPageCapture(
        source_url="https://example.edu/program",
        page_title="Example University Admissions",
        body_text="Welcome to the graduate admissions page.",
    )

    result = AdmissionsExtractor().extract(capture=capture)

    assert result.program_name is None
    assert result.deadline is None
    assert result.tuition is None
    assert result.english_requirement is None
    assert result.academic_requirement is None
    assert result.prerequisite_keywords == []


def test_extractor_rejects_application_opening_sentence_as_english_requirement() -> None:
    from admission_browser_agent.extractor import AdmissionsExtractor
    from admission_browser_agent.models import RawPageCapture

    capture = RawPageCapture(
        source_url="https://example.edu/admissions",
        page_title="Admissions",
        body_text=(
            "Application for 2026-27 intake opens on September 22, 2025.\n"
            "Admission Requirements\n"
            "Applicants shall hold a bachelor's degree or equivalent qualification.\n"
        ),
    )

    result = AdmissionsExtractor().extract(capture=capture)

    assert result.english_requirement is None
    assert result.academic_requirement == "Applicants shall hold a bachelor's degree or equivalent qualification."


def test_extractor_cleans_academic_requirement_from_plural_header() -> None:
    from admission_browser_agent.extractor import AdmissionsExtractor
    from admission_browser_agent.models import RawPageCapture

    capture = RawPageCapture(
        source_url="https://example.edu/admissions",
        page_title="Admissions",
        body_text=(
            "Admission Requirements\n"
            "Applicants shall hold a Bachelor's degree or an equivalent qualification.\n"
        ),
    )

    result = AdmissionsExtractor().extract(capture=capture)

    assert result.academic_requirement == "Applicants shall hold a Bachelor's degree or an equivalent qualification."


def test_extractor_deadline_supports_schedule_round_wording() -> None:
    from admission_browser_agent.extractor import AdmissionsExtractor
    from admission_browser_agent.models import RawPageCapture

    capture = RawPageCapture(
        source_url="https://example.edu/admissions",
        page_title="Admissions",
        body_text=(
            "Application for 2026-27 intake opens on September 22, 2025.\n"
            "Admission Schedule\n"
            "Round 1 (Main): 12:00 noon (GMT +8), December 1, 2025\n"
            "Round 2 (Clearing): 12:00 noon (GMT +8), February 9, 2026\n"
        ),
    )

    result = AdmissionsExtractor().extract(capture=capture)

    assert result.deadline == "December 1, 2025"


def test_extractor_tuition_supports_programme_fee_patterns() -> None:
    from admission_browser_agent.extractor import AdmissionsExtractor
    from admission_browser_agent.models import RawPageCapture

    capture = RawPageCapture(
        source_url="https://example.edu/fees",
        page_title="Fees",
        body_text=(
            "Application fee: HK$300\n"
            "Programme Fees\n"
            "HK$320,000 for the whole programme\n"
        ),
    )

    result = AdmissionsExtractor().extract(capture=capture)

    assert result.tuition == "HK$320,000 for the whole programme"


def test_extractor_rejects_heading_only_tuition_and_prefers_amount_sentence() -> None:
    from admission_browser_agent.extractor import AdmissionsExtractor
    from admission_browser_agent.models import RawPageCapture

    capture = RawPageCapture(
        source_url="https://example.edu/programme",
        page_title="Programme",
        body_text=(
            "Medium of Instruction\n"
            "English\n"
            "Tuition Fees\n"
            "The tuition fee is HK$390,000 for students admitted in September 2026.\n"
        ),
    )

    result = AdmissionsExtractor().extract(capture=capture)

    assert result.tuition == "The tuition fee is HK$390,000 for students admitted in September 2026."
    assert result.english_requirement is None


def test_extractor_prefers_english_requirement_answer_over_question_title() -> None:
    from admission_browser_agent.extractor import AdmissionsExtractor
    from admission_browser_agent.models import RawPageCapture

    capture = RawPageCapture(
        source_url="https://example.edu/faq/english",
        page_title=(
            "Are there any English language requirements for admission? "
            "Do I need to take any English tests?"
        ),
        body_text=(
            "Are there any English language requirements for admission? "
            "Do I need to take any English tests?\n"
            "A candidate who is seeking admission on the basis of a qualification from a "
            "university outside Hong Kong of which the language of teaching and/or examination "
            "is not English, is expected to satisfy the University English language requirement "
            "applicable to higher degrees.\n"
        ),
    )

    result = AdmissionsExtractor().extract(capture=capture)

    assert result.english_requirement == (
        "A candidate who is seeking admission on the basis of a qualification from a "
        "university outside Hong Kong of which the language of teaching and/or examination "
        "is not English, is expected to satisfy the University English language requirement "
        "applicable to higher degrees."
    )


def test_extractor_prevents_english_requirement_text_from_filling_academic_requirement() -> None:
    from admission_browser_agent.extractor import AdmissionsExtractor
    from admission_browser_agent.models import RawPageCapture

    capture = RawPageCapture(
        source_url="https://example.edu/admissions",
        page_title="Admissions",
        body_text=(
            "Admission Requirements\n"
            "Applicants shall hold a Bachelor's degree or an equivalent qualification.\n"
            "English Language Requirement\n"
            "A candidate whose language of teaching and/or examination is not English is expected "
            "to satisfy the University English language requirement applicable to higher degrees.\n"
        ),
    )

    result = AdmissionsExtractor().extract(capture=capture)

    assert result.academic_requirement == (
        "Applicants shall hold a Bachelor's degree or an equivalent qualification."
    )
    assert result.english_requirement == (
        "A candidate whose language of teaching and/or examination is not English is expected "
        "to satisfy the University English language requirement applicable to higher degrees."
    )


def test_extractor_deadline_supports_overview_style_deadline_wording() -> None:
    from admission_browser_agent.extractor import AdmissionsExtractor
    from admission_browser_agent.models import RawPageCapture

    capture = RawPageCapture(
        source_url="https://example.edu/overview",
        page_title="Programme Overview",
        body_text=(
            "Overview\n"
            "Application deadline for 2026 intake: December 1, 2025\n"
        ),
    )

    result = AdmissionsExtractor().extract(capture=capture)

    assert result.deadline == "December 1, 2025"


def test_extractor_deadline_rejects_referral_sentence_without_date() -> None:
    from admission_browser_agent.extractor import AdmissionsExtractor
    from admission_browser_agent.models import RawPageCapture

    capture = RawPageCapture(
        source_url="https://example.edu/faq",
        page_title="FAQ",
        body_text=(
            "How do I apply for the programme? When are the application deadlines?\n"
            "For the application method and application deadline, please visit https://example.edu/admissions/\n"
        ),
    )

    result = AdmissionsExtractor().extract(capture=capture)

    assert result.deadline is None


def test_extractor_tuition_supports_local_and_non_local_fee_wording() -> None:
    from admission_browser_agent.extractor import AdmissionsExtractor
    from admission_browser_agent.models import RawPageCapture

    capture = RawPageCapture(
        source_url="https://example.edu/programme",
        page_title="Programme Information",
        body_text=(
            "Tuition Fee\n"
            "Local students: HK$169,920; Non-local students: HK$339,840\n"
        ),
    )

    result = AdmissionsExtractor().extract(capture=capture)

    assert result.tuition == "Local students: HK$169,920; Non-local students: HK$339,840"


def test_extractor_tuition_rejects_low_value_fee_table_rows() -> None:
    from admission_browser_agent.extractor import AdmissionsExtractor
    from admission_browser_agent.models import RawPageCapture

    capture = RawPageCapture(
        source_url="https://example.edu/fees",
        page_title="Programme Fee And Payment",
        body_text=(
            "Programme Fee and Payment\n"
            "Application $600\n"
            "Caution Money $350\n"
            "Student Activity Fee $100\n"
            "The schedule of fees for 2026-2027 is given below for information.\n"
        ),
    )

    result = AdmissionsExtractor().extract(capture=capture)

    assert result.tuition is None


def test_extractor_prerequisite_keywords_from_admissions_course_background_wording() -> None:
    from admission_browser_agent.extractor import AdmissionsExtractor
    from admission_browser_agent.models import RawPageCapture

    capture = RawPageCapture(
        source_url="https://example.edu/admissions",
        page_title="Admissions",
        body_text=(
            "Minimum Admission Requirements\n"
            "Applicants shall hold a Bachelor's degree or an equivalent qualification.\n"
            "Applicants shall have taken at least one university course in calculus and algebra, "
            "one course in computer programming, and one course in introductory statistics or related areas.\n"
        ),
    )

    result = AdmissionsExtractor().extract(capture=capture)

    assert result.academic_requirement == (
        "Applicants shall have taken at least one university course in calculus and algebra, "
        "one course in computer programming, and one course in introductory statistics or related areas."
    )
    assert result.prerequisite_keywords == [
        "statistics",
        "algebra",
        "calculus",
        "programming",
    ]


def test_extractor_normalizes_apostrophes_and_non_breaking_spaces() -> None:
    from admission_browser_agent.extractor import AdmissionsExtractor
    from admission_browser_agent.models import RawPageCapture

    capture = RawPageCapture(
        source_url="https://example.edu/admissions",
        page_title="Admissions",
        body_text=(
            "Admission Requirements\n"
            "Applicants shall hold a Bachelor\u2019s degree\u00a0or an equivalent qualification.\n"
        ),
    )

    result = AdmissionsExtractor().extract(capture=capture)

    assert result.academic_requirement == (
        "Applicants shall hold a Bachelor's degree or an equivalent qualification."
    )


def test_navigator_scores_admissions_links_above_generic_links() -> None:
    from admission_browser_agent.models import CandidateLink
    from admission_browser_agent.navigator import score_candidate_link, select_top_candidate_links

    admissions_link = CandidateLink(
        anchor_text="Admissions requirements and deadlines",
        url="https://example.edu/admissions",
    )
    generic_link = CandidateLink(
        anchor_text="Campus news",
        url="https://example.edu/news",
    )
    faq_link = CandidateLink(
        anchor_text="FAQ",
        url="https://example.edu/faq",
    )

    assert score_candidate_link(admissions_link) > score_candidate_link(generic_link)

    ranked = select_top_candidate_links([generic_link, faq_link, admissions_link], top_k=2)

    assert [item.candidate.url for item in ranked] == [
        "https://example.edu/admissions",
        "https://example.edu/faq",
    ]


def test_navigator_scores_fee_and_english_pages_above_generic_faq() -> None:
    from admission_browser_agent.models import CandidateLink
    from admission_browser_agent.navigator import score_candidate_link

    fee_link = CandidateLink(
        anchor_text="Tuition and fees",
        url="https://example.edu/fees",
    )
    english_link = CandidateLink(
        anchor_text="English language requirements",
        url="https://example.edu/english-requirements",
    )
    faq_link = CandidateLink(
        anchor_text="FAQ",
        url="https://example.edu/faq",
    )

    assert score_candidate_link(fee_link) > score_candidate_link(faq_link)
    assert score_candidate_link(english_link) > score_candidate_link(faq_link)


def test_navigator_demotes_irrelevant_pages_out_of_top_k() -> None:
    from admission_browser_agent.models import CandidateLink
    from admission_browser_agent.navigator import select_top_candidate_links

    ranked = select_top_candidate_links(
        [
            CandidateLink(
                anchor_text="Admissions requirements and deadlines",
                url="https://example.edu/admissions",
            ),
            CandidateLink(
                anchor_text="Tuition and fees",
                url="https://example.edu/fees",
            ),
            CandidateLink(
                anchor_text="English language requirements",
                url="https://example.edu/english-requirements",
            ),
            CandidateLink(anchor_text="Campus news", url="https://example.edu/news"),
            CandidateLink(anchor_text="Contact", url="https://example.edu/contact"),
            CandidateLink(
                anchor_text="Current Students",
                url="https://example.edu/current-students",
            ),
            CandidateLink(anchor_text="Poster", url="https://example.edu/poster"),
            CandidateLink(anchor_text="YouTube", url="https://example.edu/youtube"),
        ],
        top_k=3,
    )

    assert [item.candidate.url for item in ranked] == [
        "https://example.edu/admissions",
        "https://example.edu/fees",
        "https://example.edu/english-requirements",
    ]


def test_navigator_candidate_scoring_has_stable_tie_ordering() -> None:
    from admission_browser_agent.models import CandidateLink
    from admission_browser_agent.navigator import score_candidate_links

    ranked = score_candidate_links(
        [
            CandidateLink(anchor_text="Apply", url="https://example.edu/apply-b"),
            CandidateLink(anchor_text="Apply", url="https://example.edu/apply-a"),
        ]
    )

    assert [item.candidate.url for item in ranked] == [
        "https://example.edu/apply-a",
        "https://example.edu/apply-b",
    ]


def test_navigator_follow_up_selection_prefers_strong_fee_and_english_links_deterministically() -> None:
    from admission_browser_agent.models import CandidateLink
    from admission_browser_agent.navigator import select_follow_up_candidate_links

    ranked = select_follow_up_candidate_links(
        [
            CandidateLink(anchor_text="FAQ", url="https://example.edu/faq"),
            CandidateLink(anchor_text="Programme Fee", url="https://example.edu/programme-fee"),
            CandidateLink(
                anchor_text="English Language Requirements",
                url="https://example.edu/english-language-requirements",
            ),
        ],
        missing_fields={"tuition", "english_requirement"},
        top_k=2,
    )

    assert [item.candidate.url for item in ranked] == [
        "https://example.edu/english-language-requirements",
        "https://example.edu/programme-fee",
    ]


def test_navigator_selects_more_complete_program_result() -> None:
    from admission_browser_agent.models import ExtractedProgramInfo
    from admission_browser_agent.navigator import select_best_program_result

    homepage_result = ExtractedProgramInfo(
        source_url="https://example.edu/",
        page_title="Example University",
        program_name="Master of Science in AI",
    )
    admissions_result = ExtractedProgramInfo(
        source_url="https://example.edu/admissions",
        page_title="Admissions",
        program_name="Master of Science in AI",
        deadline="December 1, 2026",
        tuition="HK$320,000",
        english_requirement="IELTS 6.5",
        academic_requirement="Bachelor's degree required",
    )

    best = select_best_program_result([homepage_result, admissions_result])

    assert best is not None
    assert best.result.source_url == "https://example.edu/admissions"
    assert best.completeness_score > 0


def test_navigator_aggregates_complementary_fields_across_pages() -> None:
    from admission_browser_agent.models import ExtractedProgramInfo
    from admission_browser_agent.navigator import aggregate_program_results

    homepage_result = ExtractedProgramInfo(
        source_url="https://example.edu/",
        page_title="Master of Science in AI",
        program_name="Master of Science in Artificial Intelligence",
        prerequisite_keywords=["python"],
    )
    admissions_result = ExtractedProgramInfo(
        source_url="https://example.edu/admissions",
        page_title="Admissions",
        program_name="Master of Science in AI",
        deadline="December 1, 2026",
        academic_requirement="Bachelor's degree in computer science.",
        prerequisite_keywords=["statistics", "linear algebra"],
    )
    fee_result = ExtractedProgramInfo(
        source_url="https://example.edu/fees",
        page_title="Tuition and Fees",
        tuition="HK$320,000 for the whole programme",
    )

    aggregated = aggregate_program_results(
        [homepage_result, admissions_result, fee_result],
        page_hint_text_by_url={
            "https://example.edu/": "Master of Science in AI https://example.edu/",
            "https://example.edu/admissions": "Admissions requirements deadlines https://example.edu/admissions",
            "https://example.edu/fees": "Tuition and fees https://example.edu/fees",
        },
    )

    assert aggregated is not None
    assert aggregated.program_name == "Master of Science in Artificial Intelligence"
    assert aggregated.deadline == "December 1, 2026"
    assert aggregated.tuition == "HK$320,000 for the whole programme"
    assert aggregated.academic_requirement == "Bachelor's degree in computer science."
    assert aggregated.prerequisite_keywords == ["statistics", "linear algebra", "python"]
    assert aggregated.field_sources["program_name"] == ["https://example.edu/"]
    assert aggregated.field_sources["deadline"] == ["https://example.edu/admissions"]
    assert aggregated.field_sources["tuition"] == ["https://example.edu/fees"]
    assert aggregated.field_sources["prerequisite_keywords"] == [
        "https://example.edu/admissions",
        "https://example.edu/",
    ]


def test_navigator_aggregation_outcome_records_field_decisions() -> None:
    from admission_browser_agent.models import ExtractedProgramInfo
    from admission_browser_agent.navigator import aggregate_program_results_with_debug

    outcome = aggregate_program_results_with_debug(
        [
            ExtractedProgramInfo(
                source_url="https://example.edu/",
                page_title="Overview",
                program_name="Master of Science in Artificial Intelligence",
            ),
            ExtractedProgramInfo(
                source_url="https://example.edu/admissions",
                page_title="Admissions requirements",
                deadline="December 1, 2026",
                academic_requirement="Bachelor's degree required",
            ),
            ExtractedProgramInfo(
                source_url="https://example.edu/fees",
                page_title="Tuition and Fees",
                tuition="HK$320,000",
            ),
        ],
        page_hint_text_by_url={
            "https://example.edu/": "Overview https://example.edu/",
            "https://example.edu/admissions": "Admissions requirements deadlines https://example.edu/admissions",
            "https://example.edu/fees": "Tuition and fees https://example.edu/fees",
        },
    )

    assert outcome is not None
    assert outcome.decisions["deadline"].selected_value == "December 1, 2026"
    assert outcome.decisions["deadline"].source_urls == ["https://example.edu/admissions"]
    assert outcome.decisions["deadline"].candidates[0].selected is True
    assert outcome.decisions["tuition"].selected_value == "HK$320,000"
    assert outcome.decisions["tuition"].source_urls == ["https://example.edu/fees"]


def test_navigator_aggregation_skips_low_quality_deadline_and_tuition_values() -> None:
    from admission_browser_agent.models import ExtractedProgramInfo
    from admission_browser_agent.navigator import aggregate_program_results

    noisy_result = ExtractedProgramInfo(
        source_url="https://example.edu/faq-group/before-application",
        page_title="Before Application",
        deadline=(
            "For the application method and application deadline, please visit "
            "https://example.edu/admissions/"
        ),
        tuition=(
            "Programme Fee and Payment 1. Government-funded Programmes. "
            "Composition fees for local and non-local students will be announced every year."
        ),
    )
    deadline_result = ExtractedProgramInfo(
        source_url="https://example.edu/apply-now",
        page_title="Apply Now",
        deadline="December 1, 2026",
    )
    tuition_result = ExtractedProgramInfo(
        source_url="https://example.edu/programme-details",
        page_title="Master of Data Science",
        tuition="Local students: HK$169,920; Non-local students: HK$339,840",
    )

    aggregated = aggregate_program_results(
        [noisy_result, deadline_result, tuition_result],
        page_hint_text_by_url={
            "https://example.edu/faq-group/before-application": (
                "before application deadlines programme fee https://example.edu/faq-group/before-application"
            ),
            "https://example.edu/apply-now": "apply now admissions deadline https://example.edu/apply-now",
            "https://example.edu/programme-details": "programme details tuition https://example.edu/programme-details",
        },
    )

    assert aggregated is not None
    assert aggregated.deadline == "December 1, 2026"
    assert aggregated.tuition == "Local students: HK$169,920; Non-local students: HK$339,840"


def test_navigator_does_not_overwrite_good_fields_with_worse_or_null_values() -> None:
    from admission_browser_agent.models import ExtractedProgramInfo
    from admission_browser_agent.navigator import aggregate_program_results

    strong_result = ExtractedProgramInfo(
        source_url="https://example.edu/admissions",
        page_title="Admissions requirements",
        program_name="Master of Science in Artificial Intelligence",
        english_requirement="IELTS 6.5 overall or TOEFL 90.",
    )
    weak_result = ExtractedProgramInfo(
        source_url="https://example.edu/overview",
        page_title="Overview",
        program_name="MSc AI",
        english_requirement=None,
    )

    aggregated = aggregate_program_results(
        [strong_result, weak_result],
        page_hint_text_by_url={
            "https://example.edu/admissions": "Admissions english requirements https://example.edu/admissions",
            "https://example.edu/overview": "Overview https://example.edu/overview",
        },
    )

    assert aggregated is not None
    assert aggregated.program_name == "Master of Science in Artificial Intelligence"
    assert aggregated.english_requirement == "IELTS 6.5 overall or TOEFL 90."
    assert aggregated.field_sources["program_name"] == ["https://example.edu/admissions"]
    assert aggregated.field_sources["english_requirement"] == ["https://example.edu/admissions"]


class MappingBrowserSession:
    def __init__(self, *, page_with_links_map: dict[str, object], page_map: dict[str, object]) -> None:
        self.page_with_links_map = page_with_links_map
        self.page_map = page_map
        self.fetch_with_links_urls: list[str] = []
        self.fetch_urls: list[str] = []

    def fetch_page_with_links(self, url: str):
        self.fetch_with_links_urls.append(url)
        if url in self.page_with_links_map:
            return self.page_with_links_map[url]
        return self.page_map[url], []

    def fetch_page(self, url: str):
        self.fetch_urls.append(url)
        return self.page_map[url]


class MappingExtractor:
    def __init__(self, extracted_by_url: dict[str, object]) -> None:
        self.extracted_by_url = extracted_by_url

    def extract(self, *, capture):
        return self.extracted_by_url[capture.source_url]


def test_pipeline_writes_debug_artifact_with_provenance(tmp_path: Path) -> None:
    from admission_browser_agent.config import RunConfig
    from admission_browser_agent.models import CandidateLink, CrawlRequest, ExtractedProgramInfo, RawPageCapture
    from admission_browser_agent.pipeline import AdmissionsPipeline

    class StubBrowserSession:
        def __init__(self) -> None:
            self.fetched_urls: list[str] = []
            self.fetch_with_links_urls: list[str] = []

        def fetch_page_with_links(self, url: str) -> tuple[RawPageCapture, list[CandidateLink]]:
            self.fetched_urls.append(url)
            self.fetch_with_links_urls.append(url)
            return (
                RawPageCapture(
                    source_url=url,
                    page_title="Example University - Master of Science in AI",
                    body_text="Welcome to the programme homepage.",
                ),
                [
                    CandidateLink(
                        anchor_text="Admissions requirements and deadlines",
                        url="https://example.edu/admissions",
                    ),
                    CandidateLink(
                        anchor_text="Tuition and fees",
                        url="https://example.edu/fees",
                    ),
                    CandidateLink(anchor_text="Campus news", url="https://example.edu/news"),
                ],
            )

        def fetch_page(self, url: str) -> RawPageCapture:
            self.fetched_urls.append(url)
            if url == "https://example.edu/admissions":
                return RawPageCapture(
                    source_url=url,
                    page_title="Admissions",
                    body_text=(
                        "Application deadline: December 1, 2026\n"
                        "English language requirement: IELTS 6.5\n"
                        "Academic requirement: Bachelor's degree in computer science.\n"
                        "Applicants should have prior knowledge of calculus.\n"
                    ),
                )
            if url == "https://example.edu/fees":
                return RawPageCapture(
                    source_url=url,
                    page_title="Tuition and Fees",
                    body_text="Programme fee: HK$320,000\n",
                )
            return RawPageCapture(
                source_url=url,
                page_title="News",
                body_text="Campus news and events.",
            )

    class StubExtractor:
        def extract(self, *, capture: RawPageCapture) -> ExtractedProgramInfo:
            if capture.source_url == "https://example.edu/":
                return ExtractedProgramInfo(
                    source_url=capture.source_url,
                    page_title=capture.page_title,
                    program_name="Master of Science in AI",
                )
            if capture.source_url == "https://example.edu/admissions":
                return ExtractedProgramInfo(
                    source_url=capture.source_url,
                    page_title=capture.page_title,
                    deadline="December 1, 2026",
                    english_requirement="IELTS 6.5",
                    academic_requirement="Bachelor's degree in computer science.",
                    prerequisite_keywords=["calculus"],
                )
            if capture.source_url == "https://example.edu/fees":
                return ExtractedProgramInfo(
                    source_url=capture.source_url,
                    page_title=capture.page_title,
                    tuition="HK$320,000",
                )
            return ExtractedProgramInfo(
                source_url=capture.source_url,
                page_title=capture.page_title,
            )

    browser_session = StubBrowserSession()

    pipeline = AdmissionsPipeline(
        run_config=RunConfig(
            raw_data_dir=tmp_path / "raw",
            processed_data_dir=tmp_path / "processed",
            debug_data_dir=tmp_path / "debug",
        ),
        browser_session=browser_session,
        extractor=StubExtractor(),
    )
    request = CrawlRequest(
        university="Example University",
        seed_url="https://example.edu/",
    )

    result = pipeline.run(request)
    raw_artifacts = list((tmp_path / "raw").glob("*.json"))
    processed_artifacts = list((tmp_path / "processed").glob("*.json"))
    debug_artifacts = list((tmp_path / "debug").glob("*.json"))

    assert result.source_url == "https://example.edu/admissions"
    assert browser_session.fetched_urls == [
        "https://example.edu/",
        "https://example.edu/admissions",
        "https://example.edu/fees",
    ]
    assert browser_session.fetch_with_links_urls == ["https://example.edu/"]
    assert len(raw_artifacts) == 3
    assert len(processed_artifacts) == 1
    assert len(debug_artifacts) == 1
    assert len(pipeline.last_candidate_links) == 2
    assert pipeline.last_processed_output_path == processed_artifacts[0]
    assert pipeline.last_debug_output_path == debug_artifacts[0]
    assert pipeline.last_extracted_program is not None
    assert set(pipeline.last_raw_output_paths) == set(raw_artifacts)
    assert pipeline.last_inspected_candidate_count == 2
    assert pipeline.last_debug_report is not None

    processed_payload = json.loads(processed_artifacts[0].read_text(encoding="utf-8"))
    debug_payload = json.loads(debug_artifacts[0].read_text(encoding="utf-8"))

    assert processed_payload["source_url"] == "https://example.edu/admissions"
    assert processed_payload["deadline"] == "December 1, 2026"
    assert processed_payload["tuition"] == "HK$320,000"
    assert processed_payload["english_requirement"] == "IELTS 6.5"
    assert processed_payload["academic_requirement"] == "Bachelor's degree in computer science."
    assert processed_payload["prerequisite_keywords"] == ["calculus"]
    assert processed_payload["field_sources"]["deadline"] == ["https://example.edu/admissions"]
    assert processed_payload["field_sources"]["tuition"] == ["https://example.edu/fees"]
    assert processed_payload["field_sources"]["academic_requirement"] == ["https://example.edu/admissions"]
    assert processed_payload["field_sources"]["prerequisite_keywords"] == ["https://example.edu/admissions"]
    assert debug_payload["seed_url"] == "https://example.edu/"
    assert debug_payload["seed_page_title"] == "Example University - Master of Science in AI"
    assert debug_payload["discovered_candidate_links"] == [
        {
            "anchor_text": "Admissions requirements and deadlines",
            "url": "https://example.edu/admissions",
            "relevance_score": 34,
            "eligible": True,
            "selected": True,
            "fetched": False,
            "rejection_reason": None,
            "discovery_stage": "seed",
            "discovered_from_url": "https://example.edu/",
        },
        {
            "anchor_text": "Tuition and fees",
            "url": "https://example.edu/fees",
            "relevance_score": 23,
            "eligible": True,
            "selected": True,
            "fetched": False,
            "rejection_reason": None,
            "discovery_stage": "seed",
            "discovered_from_url": "https://example.edu/",
        },
        {
            "anchor_text": "Campus news",
            "url": "https://example.edu/news",
            "relevance_score": -17,
            "eligible": False,
            "selected": False,
            "fetched": False,
            "rejection_reason": None,
            "discovery_stage": "seed",
            "discovered_from_url": "https://example.edu/",
        },
    ]
    assert len(debug_payload["inspected_pages"]) == 3
    assert debug_payload["inspected_pages"][0]["inspection_stage"] == "seed"
    assert debug_payload["inspected_pages"][1]["page_title"] == "Admissions"
    assert debug_payload["inspected_pages"][1]["relevance_score"] == 34
    assert debug_payload["inspected_pages"][1]["inspection_stage"] == "primary_candidate"
    assert debug_payload["inspected_pages"][1]["discovered_from_url"] == "https://example.edu/"
    assert debug_payload["inspected_pages"][1]["extracted"]["deadline"] == "December 1, 2026"
    assert debug_payload["aggregation_decisions"]["tuition"]["selected_value"] == "HK$320,000"
    assert debug_payload["aggregation_decisions"]["tuition"]["source_urls"] == ["https://example.edu/fees"]
    assert debug_payload["aggregation_decisions"]["tuition"]["strategy"] == (
        "prefer_non_null_value_then_field_hint_then_specificity"
    )
    assert debug_payload["aggregation_decisions"]["tuition"]["candidates"][0]["selected"] is True
    assert debug_payload["aggregation_decisions"]["deadline"]["selected_value"] == "December 1, 2026"
    assert debug_payload["aggregation_decisions"]["deadline"]["source_urls"] == [
        "https://example.edu/admissions"
    ]
    assert debug_payload["aggregation_decisions"]["prerequisite_keywords"]["selected_value"] == ["calculus"]
    assert debug_payload["aggregation_decisions"]["prerequisite_keywords"]["source_urls"] == [
        "https://example.edu/admissions"
    ]
    assert debug_payload["final_result"]["field_sources"]["tuition"] == ["https://example.edu/fees"]
    assert debug_payload["follow_up_triggered"] is False
    assert debug_payload["follow_up_missing_fields"] == []
    assert debug_payload["follow_up_source_url"] is None
    assert debug_payload["follow_up_source_page_title"] is None
    assert debug_payload["follow_up_source_page_stage"] is None
    assert debug_payload["follow_up_discovery_sources"] == []
    assert debug_payload["follow_up_candidates"] == []
    assert debug_payload["follow_up_candidates_found"] == 0
    assert debug_payload["follow_up_candidates_fetched"] == 0
    assert debug_payload["follow_up_fields_updated"] == []
    assert debug_payload["follow_up_fields_supplemented"] is False
    assert debug_payload["follow_up_update_reason"] == "no_missing_high_value_fields"


def test_pipeline_follow_up_supplements_tuition_from_fee_page(tmp_path: Path) -> None:
    from admission_browser_agent.config import RunConfig
    from admission_browser_agent.models import CandidateLink, CrawlRequest, ExtractedProgramInfo, RawPageCapture
    from admission_browser_agent.pipeline import AdmissionsPipeline

    browser_session = MappingBrowserSession(
        page_with_links_map={
            "https://example.edu/": (
                RawPageCapture(
                    source_url="https://example.edu/",
                    page_title="Example University - Master of Science in AI",
                    body_text="Welcome to the programme homepage.",
                ),
                [
                    CandidateLink(
                        anchor_text="Admissions requirements and deadlines",
                        url="https://example.edu/admissions",
                    ),
                ],
            ),
            "https://example.edu/admissions": (
                RawPageCapture(
                    source_url="https://example.edu/admissions",
                    page_title="Admissions",
                    body_text=(
                        "Application deadline: December 1, 2026\n"
                        "English language requirement: IELTS 6.5\n"
                        "Academic requirement: Bachelor's degree in computer science.\n"
                    ),
                ),
                [
                    CandidateLink(
                        anchor_text="Tuition and fees",
                        url="https://example.edu/fees",
                    ),
                    CandidateLink(anchor_text="Contact", url="https://example.edu/contact"),
                ],
            ),
        },
        page_map={
            "https://example.edu/admissions": RawPageCapture(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                body_text=(
                    "Application deadline: December 1, 2026\n"
                    "English language requirement: IELTS 6.5\n"
                    "Academic requirement: Bachelor's degree in computer science.\n"
                ),
            ),
            "https://example.edu/fees": RawPageCapture(
                source_url="https://example.edu/fees",
                page_title="Tuition and Fees",
                body_text="Programme fee: HK$320,000\n",
            ),
        },
    )
    extractor = MappingExtractor(
        extracted_by_url={
            "https://example.edu/": ExtractedProgramInfo(
                source_url="https://example.edu/",
                page_title="Example University - Master of Science in AI",
                program_name="Master of Science in AI",
            ),
            "https://example.edu/admissions": ExtractedProgramInfo(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                deadline="December 1, 2026",
                english_requirement="IELTS 6.5",
                academic_requirement="Bachelor's degree in computer science.",
            ),
            "https://example.edu/fees": ExtractedProgramInfo(
                source_url="https://example.edu/fees",
                page_title="Tuition and Fees",
                tuition="HK$320,000",
            ),
        }
    )
    pipeline = AdmissionsPipeline(
        run_config=RunConfig(
            raw_data_dir=tmp_path / "raw",
            processed_data_dir=tmp_path / "processed",
            debug_data_dir=tmp_path / "debug",
        ),
        browser_session=browser_session,
        extractor=extractor,
    )

    result = pipeline.run(
        CrawlRequest(
            university="Example University",
            seed_url="https://example.edu/",
        )
    )

    assert result.tuition == "HK$320,000"
    assert result.field_sources["tuition"] == ["https://example.edu/fees"]
    assert browser_session.fetch_with_links_urls == [
        "https://example.edu/",
        "https://example.edu/admissions",
    ]
    assert browser_session.fetch_urls == [
        "https://example.edu/admissions",
        "https://example.edu/fees",
    ]
    assert pipeline.last_debug_report is not None
    assert pipeline.last_debug_report.follow_up_triggered is True
    assert pipeline.last_debug_report.follow_up_missing_fields == ["tuition"]
    assert pipeline.last_debug_report.follow_up_source_url == "https://example.edu/admissions"
    assert pipeline.last_debug_report.follow_up_source_page_title == "Admissions"
    assert pipeline.last_debug_report.follow_up_source_page_stage == "primary_candidate"
    assert [item.outcome for item in pipeline.last_debug_report.follow_up_discovery_sources] == [
        "selected_candidates_fetched"
    ]
    assert pipeline.last_debug_report.follow_up_candidates_found == 2
    assert pipeline.last_debug_report.follow_up_candidates_fetched == 1
    assert pipeline.last_debug_report.follow_up_fields_updated == ["tuition"]
    assert pipeline.last_debug_report.follow_up_fields_supplemented is True
    assert pipeline.last_debug_report.follow_up_update_reason == "fields_supplemented"
    assert pipeline.last_debug_report.follow_up_candidates[0].url == "https://example.edu/fees"
    assert pipeline.last_debug_report.follow_up_candidates[0].eligible is True
    assert pipeline.last_debug_report.follow_up_candidates[0].fetched is True
    assert pipeline.last_debug_report.follow_up_candidates[0].rejection_reason is None
    assert pipeline.last_debug_report.follow_up_candidates[1].eligible is False
    assert pipeline.last_debug_report.follow_up_candidates[1].rejection_reason == "irrelevant_to_missing_fields"
    assert any(
        page.inspection_stage == "follow_up_candidate" and page.source_url == "https://example.edu/fees"
        for page in pipeline.last_debug_report.inspected_pages
    )
    assert pipeline.last_debug_output_path is not None

    debug_payload = json.loads(pipeline.last_debug_output_path.read_text(encoding="utf-8"))
    assert debug_payload["follow_up_triggered"] is True
    assert debug_payload["follow_up_candidates_found"] == 2
    assert debug_payload["follow_up_candidates_fetched"] == 1
    assert debug_payload["follow_up_fields_updated"] == ["tuition"]
    assert debug_payload["follow_up_fields_supplemented"] is True
    assert debug_payload["follow_up_update_reason"] == "fields_supplemented"


def test_pipeline_follow_up_supplements_english_requirement_from_language_page(tmp_path: Path) -> None:
    from admission_browser_agent.config import RunConfig
    from admission_browser_agent.models import CandidateLink, CrawlRequest, ExtractedProgramInfo, RawPageCapture
    from admission_browser_agent.pipeline import AdmissionsPipeline

    browser_session = MappingBrowserSession(
        page_with_links_map={
            "https://example.edu/": (
                RawPageCapture(
                    source_url="https://example.edu/",
                    page_title="Example University - Master of Science in AI",
                    body_text="Welcome to the programme homepage.",
                ),
                [
                    CandidateLink(
                        anchor_text="Admissions requirements and deadlines",
                        url="https://example.edu/admissions",
                    ),
                ],
            ),
            "https://example.edu/admissions": (
                RawPageCapture(
                    source_url="https://example.edu/admissions",
                    page_title="Admissions",
                    body_text=(
                        "Application deadline: December 1, 2026\n"
                        "Programme fee: HK$320,000\n"
                        "Academic requirement: Bachelor's degree in computer science.\n"
                    ),
                ),
                [
                    CandidateLink(
                        anchor_text="English language requirements",
                        url="https://example.edu/english-requirements",
                    ),
                    CandidateLink(anchor_text="FAQ", url="https://example.edu/faq"),
                ],
            ),
        },
        page_map={
            "https://example.edu/admissions": RawPageCapture(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                body_text=(
                    "Application deadline: December 1, 2026\n"
                    "Programme fee: HK$320,000\n"
                    "Academic requirement: Bachelor's degree in computer science.\n"
                ),
            ),
            "https://example.edu/english-requirements": RawPageCapture(
                source_url="https://example.edu/english-requirements",
                page_title="English Language Requirements",
                body_text="English language requirement: IELTS 6.5 overall or TOEFL 90.\n",
            ),
        },
    )
    extractor = MappingExtractor(
        extracted_by_url={
            "https://example.edu/": ExtractedProgramInfo(
                source_url="https://example.edu/",
                page_title="Example University - Master of Science in AI",
                program_name="Master of Science in AI",
            ),
            "https://example.edu/admissions": ExtractedProgramInfo(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                deadline="December 1, 2026",
                tuition="HK$320,000",
                academic_requirement="Bachelor's degree in computer science.",
            ),
            "https://example.edu/english-requirements": ExtractedProgramInfo(
                source_url="https://example.edu/english-requirements",
                page_title="English Language Requirements",
                english_requirement="IELTS 6.5 overall or TOEFL 90.",
            ),
        }
    )
    pipeline = AdmissionsPipeline(
        run_config=RunConfig(
            raw_data_dir=tmp_path / "raw",
            processed_data_dir=tmp_path / "processed",
            debug_data_dir=tmp_path / "debug",
        ),
        browser_session=browser_session,
        extractor=extractor,
    )

    result = pipeline.run(
        CrawlRequest(
            university="Example University",
            seed_url="https://example.edu/",
        )
    )

    assert result.english_requirement == "IELTS 6.5 overall or TOEFL 90."
    assert result.field_sources["english_requirement"] == ["https://example.edu/english-requirements"]
    assert browser_session.fetch_with_links_urls == [
        "https://example.edu/",
        "https://example.edu/admissions",
    ]
    assert browser_session.fetch_urls == [
        "https://example.edu/admissions",
        "https://example.edu/english-requirements",
    ]
    assert pipeline.last_debug_report is not None
    assert pipeline.last_debug_report.follow_up_triggered is True
    assert pipeline.last_debug_report.follow_up_missing_fields == ["english_requirement"]
    assert pipeline.last_debug_report.follow_up_source_url == "https://example.edu/admissions"
    assert [item.outcome for item in pipeline.last_debug_report.follow_up_discovery_sources] == [
        "selected_candidates_fetched"
    ]
    assert pipeline.last_debug_report.follow_up_candidates_found == 2
    assert pipeline.last_debug_report.follow_up_candidates_fetched == 1
    assert pipeline.last_debug_report.follow_up_fields_updated == ["english_requirement"]
    assert pipeline.last_debug_report.follow_up_fields_supplemented is True
    assert pipeline.last_debug_report.follow_up_update_reason == "fields_supplemented"
    assert pipeline.last_debug_report.follow_up_candidates[0].eligible is True
    assert pipeline.last_debug_report.follow_up_candidates[0].fetched is True
    assert pipeline.last_debug_report.follow_up_candidates[1].eligible is True
    assert pipeline.last_debug_report.follow_up_candidates[1].selected is False
    assert pipeline.last_debug_report.follow_up_candidates[1].rejection_reason == "not_in_follow_up_top_k"
    assert any(
        page.inspection_stage == "follow_up_candidate"
        and page.source_url == "https://example.edu/english-requirements"
        for page in pipeline.last_debug_report.inspected_pages
    )


def test_pipeline_follow_up_falls_back_to_seed_when_primary_source_has_no_eligible_candidates(
    tmp_path: Path,
) -> None:
    from admission_browser_agent.config import RunConfig
    from admission_browser_agent.models import CandidateLink, CrawlRequest, ExtractedProgramInfo, RawPageCapture
    from admission_browser_agent.pipeline import AdmissionsPipeline

    browser_session = MappingBrowserSession(
        page_with_links_map={
            "https://example.edu/": (
                RawPageCapture(
                    source_url="https://example.edu/",
                    page_title="Example University - Master of Science in AI",
                    body_text="Welcome to the programme homepage.",
                ),
                [
                    CandidateLink(
                        anchor_text="Admissions requirements and deadlines",
                        url="https://example.edu/admissions",
                    ),
                    CandidateLink(
                        anchor_text="Programme costs",
                        url="https://example.edu/programme-costs",
                    ),
                    CandidateLink(
                        anchor_text="Language proficiency",
                        url="https://example.edu/language-proficiency",
                    ),
                ],
            ),
            "https://example.edu/admissions": (
                RawPageCapture(
                    source_url="https://example.edu/admissions",
                    page_title="Admissions",
                    body_text=(
                        "Application deadline: December 1, 2026\n"
                        "Academic requirement: Bachelor's degree in computer science.\n"
                    ),
                ),
                [
                    CandidateLink(anchor_text="Contact", url="https://example.edu/contact"),
                    CandidateLink(anchor_text="Campus news", url="https://example.edu/news"),
                ],
            ),
        },
        page_map={
            "https://example.edu/admissions": RawPageCapture(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                body_text=(
                    "Application deadline: December 1, 2026\n"
                    "Academic requirement: Bachelor's degree in computer science.\n"
                ),
            ),
            "https://example.edu/programme-costs": RawPageCapture(
                source_url="https://example.edu/programme-costs",
                page_title="Programme Costs",
                body_text="Programme fee: HK$320,000\n",
            ),
            "https://example.edu/language-proficiency": RawPageCapture(
                source_url="https://example.edu/language-proficiency",
                page_title="Language Proficiency",
                body_text="English language requirement: IELTS 6.5 overall or TOEFL 90.\n",
            ),
        },
    )
    extractor = MappingExtractor(
        extracted_by_url={
            "https://example.edu/": ExtractedProgramInfo(
                source_url="https://example.edu/",
                page_title="Example University - Master of Science in AI",
                program_name="Master of Science in AI",
            ),
            "https://example.edu/admissions": ExtractedProgramInfo(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                deadline="December 1, 2026",
                academic_requirement="Bachelor's degree in computer science.",
            ),
            "https://example.edu/programme-costs": ExtractedProgramInfo(
                source_url="https://example.edu/programme-costs",
                page_title="Programme Costs",
                tuition="HK$320,000",
            ),
            "https://example.edu/language-proficiency": ExtractedProgramInfo(
                source_url="https://example.edu/language-proficiency",
                page_title="Language Proficiency",
                english_requirement="IELTS 6.5 overall or TOEFL 90.",
            ),
        }
    )
    pipeline = AdmissionsPipeline(
        run_config=RunConfig(
            raw_data_dir=tmp_path / "raw",
            processed_data_dir=tmp_path / "processed",
            debug_data_dir=tmp_path / "debug",
        ),
        browser_session=browser_session,
        extractor=extractor,
    )

    result = pipeline.run(
        CrawlRequest(
            university="Example University",
            seed_url="https://example.edu/",
        )
    )

    assert result.tuition == "HK$320,000"
    assert result.english_requirement == "IELTS 6.5 overall or TOEFL 90."
    assert browser_session.fetch_with_links_urls == [
        "https://example.edu/",
        "https://example.edu/admissions",
    ]
    assert browser_session.fetch_urls == [
        "https://example.edu/admissions",
        "https://example.edu/programme-costs",
        "https://example.edu/language-proficiency",
    ]
    assert pipeline.last_debug_report is not None
    assert pipeline.last_debug_report.follow_up_triggered is True
    assert pipeline.last_debug_report.follow_up_missing_fields == ["tuition", "english_requirement"]
    assert pipeline.last_debug_report.follow_up_source_url == "https://example.edu/admissions"
    assert [item.source_url for item in pipeline.last_debug_report.follow_up_discovery_sources] == [
        "https://example.edu/admissions",
        "https://example.edu/",
    ]
    assert [item.used_as_fallback for item in pipeline.last_debug_report.follow_up_discovery_sources] == [
        False,
        True,
    ]
    assert [item.outcome for item in pipeline.last_debug_report.follow_up_discovery_sources] == [
        "candidates_found_but_all_irrelevant",
        "selected_candidates_fetched",
    ]
    assert [
        (item.discovered_from_url, item.url)
        for item in pipeline.last_debug_report.follow_up_candidates
    ] == [
        ("https://example.edu/admissions", "https://example.edu/news"),
        ("https://example.edu/admissions", "https://example.edu/contact"),
        ("https://example.edu/", "https://example.edu/programme-costs"),
        ("https://example.edu/", "https://example.edu/language-proficiency"),
        ("https://example.edu/", "https://example.edu/admissions"),
    ]
    assert pipeline.last_debug_report.follow_up_candidates_fetched == 2
    assert pipeline.last_debug_report.follow_up_fields_updated == [
        "tuition",
        "english_requirement",
    ]
    assert pipeline.last_debug_report.follow_up_fields_supplemented is True


def test_pipeline_follow_up_does_not_trigger_when_high_value_fields_are_present(
    tmp_path: Path,
) -> None:
    from admission_browser_agent.config import RunConfig
    from admission_browser_agent.models import CandidateLink, CrawlRequest, ExtractedProgramInfo, RawPageCapture
    from admission_browser_agent.pipeline import AdmissionsPipeline

    browser_session = MappingBrowserSession(
        page_with_links_map={
            "https://example.edu/": (
                RawPageCapture(
                    source_url="https://example.edu/",
                    page_title="Example University - Master of Science in AI",
                    body_text="Welcome to the programme homepage.",
                ),
                [
                    CandidateLink(
                        anchor_text="Admissions requirements",
                        url="https://example.edu/admissions",
                    ),
                ],
            ),
        },
        page_map={
            "https://example.edu/admissions": RawPageCapture(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                body_text=(
                    "Programme fee: HK$320,000\n"
                    "English language requirement: IELTS 6.5\n"
                    "Academic requirement: Bachelor's degree in computer science.\n"
                ),
            ),
        },
    )
    extractor = MappingExtractor(
        extracted_by_url={
            "https://example.edu/": ExtractedProgramInfo(
                source_url="https://example.edu/",
                page_title="Example University - Master of Science in AI",
                program_name="Master of Science in AI",
            ),
            "https://example.edu/admissions": ExtractedProgramInfo(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                tuition="HK$320,000",
                english_requirement="IELTS 6.5",
                academic_requirement="Bachelor's degree in computer science.",
            ),
        }
    )
    pipeline = AdmissionsPipeline(
        run_config=RunConfig(
            raw_data_dir=tmp_path / "raw",
            processed_data_dir=tmp_path / "processed",
            debug_data_dir=tmp_path / "debug",
        ),
        browser_session=browser_session,
        extractor=extractor,
    )

    result = pipeline.run(
        CrawlRequest(
            university="Example University",
            seed_url="https://example.edu/",
        )
    )

    assert result.deadline is None
    assert browser_session.fetch_with_links_urls == ["https://example.edu/"]
    assert browser_session.fetch_urls == ["https://example.edu/admissions"]
    assert pipeline.last_debug_report is not None
    assert pipeline.last_debug_report.follow_up_triggered is False
    assert pipeline.last_debug_report.follow_up_missing_fields == []
    assert pipeline.last_debug_report.follow_up_source_url is None
    assert pipeline.last_debug_report.follow_up_candidates_found == 0
    assert pipeline.last_debug_report.follow_up_candidates_fetched == 0
    assert pipeline.last_debug_report.follow_up_fields_updated == []
    assert pipeline.last_debug_report.follow_up_fields_supplemented is False
    assert pipeline.last_debug_report.follow_up_update_reason == "no_missing_high_value_fields"


def test_pipeline_follow_up_triggered_with_zero_valid_candidates(tmp_path: Path) -> None:
    from admission_browser_agent.config import RunConfig
    from admission_browser_agent.models import CandidateLink, CrawlRequest, ExtractedProgramInfo, RawPageCapture
    from admission_browser_agent.pipeline import AdmissionsPipeline

    browser_session = MappingBrowserSession(
        page_with_links_map={
            "https://example.edu/": (
                RawPageCapture(
                    source_url="https://example.edu/",
                    page_title="Example University - Master of Science in AI",
                    body_text="Welcome to the programme homepage.",
                ),
                [
                    CandidateLink(
                        anchor_text="Admissions requirements",
                        url="https://example.edu/admissions",
                    ),
                ],
            ),
            "https://example.edu/admissions": (
                RawPageCapture(
                    source_url="https://example.edu/admissions",
                    page_title="Admissions",
                    body_text=(
                        "Application deadline: December 1, 2026\n"
                        "English language requirement: IELTS 6.5\n"
                    ),
                ),
                [
                    CandidateLink(anchor_text="Contact", url="https://example.edu/contact"),
                    CandidateLink(anchor_text="Campus news", url="https://example.edu/news"),
                ],
            ),
        },
        page_map={
            "https://example.edu/admissions": RawPageCapture(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                body_text=(
                    "Application deadline: December 1, 2026\n"
                    "English language requirement: IELTS 6.5\n"
                ),
            ),
        },
    )
    extractor = MappingExtractor(
        extracted_by_url={
            "https://example.edu/": ExtractedProgramInfo(
                source_url="https://example.edu/",
                page_title="Example University - Master of Science in AI",
                program_name="Master of Science in AI",
            ),
            "https://example.edu/admissions": ExtractedProgramInfo(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                deadline="December 1, 2026",
                english_requirement="IELTS 6.5",
                academic_requirement="Bachelor's degree in computer science.",
            ),
        }
    )
    pipeline = AdmissionsPipeline(
        run_config=RunConfig(
            raw_data_dir=tmp_path / "raw",
            processed_data_dir=tmp_path / "processed",
            debug_data_dir=tmp_path / "debug",
        ),
        browser_session=browser_session,
        extractor=extractor,
    )

    result = pipeline.run(
        CrawlRequest(
            university="Example University",
            seed_url="https://example.edu/",
        )
    )

    assert result.tuition is None
    assert pipeline.last_debug_report is not None
    assert pipeline.last_debug_report.follow_up_triggered is True
    assert pipeline.last_debug_report.follow_up_missing_fields == ["tuition"]
    assert [item.outcome for item in pipeline.last_debug_report.follow_up_discovery_sources] == [
        "candidates_found_but_all_irrelevant",
        "candidates_found_but_all_irrelevant"
    ]
    assert pipeline.last_debug_report.follow_up_candidates_found == 3
    assert pipeline.last_debug_report.follow_up_candidates_fetched == 0
    assert pipeline.last_debug_report.follow_up_fields_updated == []
    assert pipeline.last_debug_report.follow_up_fields_supplemented is False
    assert pipeline.last_debug_report.follow_up_update_reason == (
        "no_follow_up_candidates_matched_missing_fields"
    )
    assert all(item.eligible is False for item in pipeline.last_debug_report.follow_up_candidates)
    assert [item.rejection_reason for item in pipeline.last_debug_report.follow_up_candidates] == [
        "irrelevant_to_missing_fields",
        "irrelevant_to_missing_fields",
        "irrelevant_to_missing_fields",
    ]


def test_pipeline_follow_up_records_candidates_rejected_by_filtering(tmp_path: Path) -> None:
    from admission_browser_agent.config import RunConfig
    from admission_browser_agent.models import CandidateLink, CrawlRequest, ExtractedProgramInfo, RawPageCapture
    from admission_browser_agent.pipeline import AdmissionsPipeline

    browser_session = MappingBrowserSession(
        page_with_links_map={
            "https://example.edu/": (
                RawPageCapture(
                    source_url="https://example.edu/",
                    page_title="Example University - Master of Science in AI",
                    body_text="Welcome to the programme homepage.",
                ),
                [
                    CandidateLink(
                        anchor_text="Admissions requirements and deadlines",
                        url="https://example.edu/admissions",
                    ),
                    CandidateLink(
                        anchor_text="Tuition and fees",
                        url="https://example.edu/fees",
                    ),
                ],
            ),
            "https://example.edu/admissions": (
                RawPageCapture(
                    source_url="https://example.edu/admissions",
                    page_title="Admissions",
                    body_text="Application deadline: December 1, 2026\n",
                ),
                [
                    CandidateLink(
                        anchor_text="Tuition and fees",
                        url="https://example.edu/fees",
                    ),
                ],
            ),
        },
        page_map={
            "https://example.edu/admissions": RawPageCapture(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                body_text="Application deadline: December 1, 2026\n",
            ),
            "https://example.edu/fees": RawPageCapture(
                source_url="https://example.edu/fees",
                page_title="Tuition and Fees",
                body_text="Fee details are published later.\n",
            ),
        },
    )
    extractor = MappingExtractor(
        extracted_by_url={
            "https://example.edu/": ExtractedProgramInfo(
                source_url="https://example.edu/",
                page_title="Example University - Master of Science in AI",
                program_name="Master of Science in AI",
            ),
            "https://example.edu/admissions": ExtractedProgramInfo(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                deadline="December 1, 2026",
                academic_requirement="Bachelor's degree in computer science.",
            ),
            "https://example.edu/fees": ExtractedProgramInfo(
                source_url="https://example.edu/fees",
                page_title="Tuition and Fees",
            ),
        }
    )
    pipeline = AdmissionsPipeline(
        run_config=RunConfig(
            raw_data_dir=tmp_path / "raw",
            processed_data_dir=tmp_path / "processed",
            debug_data_dir=tmp_path / "debug",
        ),
        browser_session=browser_session,
        extractor=extractor,
    )

    result = pipeline.run(
        CrawlRequest(
            university="Example University",
            seed_url="https://example.edu/",
        )
    )

    assert result.tuition is None
    assert pipeline.last_debug_report is not None
    assert pipeline.last_debug_report.follow_up_triggered is True
    assert pipeline.last_debug_report.follow_up_missing_fields == ["tuition", "english_requirement"]
    assert [item.outcome for item in pipeline.last_debug_report.follow_up_discovery_sources] == [
        "all_eligible_candidates_already_inspected",
        "all_eligible_candidates_already_inspected",
    ]
    assert pipeline.last_debug_report.follow_up_candidates_found == 3
    assert pipeline.last_debug_report.follow_up_candidates_fetched == 0
    assert pipeline.last_debug_report.follow_up_fields_updated == []
    assert pipeline.last_debug_report.follow_up_fields_supplemented is False
    assert pipeline.last_debug_report.follow_up_update_reason == (
        "all_follow_up_candidates_rejected_by_filtering"
    )
    assert pipeline.last_debug_report.follow_up_candidates[0].url == "https://example.edu/fees"
    assert pipeline.last_debug_report.follow_up_candidates[0].eligible is False
    assert pipeline.last_debug_report.follow_up_candidates[0].rejection_reason == "already_inspected"


def test_cli_runs_pipeline_and_prints_summary(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from admission_browser_agent.cli import main
    from admission_browser_agent.models import ExtractedProgramInfo

    class StubPipeline:
        def __init__(self, *, run_config, browser_session=None, extractor=None) -> None:
            self.run_config = run_config
            self.browser_session = browser_session
            self.extractor = extractor
            self.last_output_path = tmp_path / "raw-capture.json"
            self.last_processed_output_path = tmp_path / "processed-capture.json"
            self.last_debug_output_path = tmp_path / "debug-capture.json"
            self.last_inspected_candidate_count = 2
            self.last_debug_report = types.SimpleNamespace(
                follow_up_triggered=True,
                follow_up_candidates_found=3,
                follow_up_candidates_fetched=1,
                follow_up_fields_supplemented=True,
            )

        def run(self, request) -> ExtractedProgramInfo:
            assert request.university == "Example University"
            assert request.seed_url == "https://example.edu/admissions"
            return ExtractedProgramInfo(
                source_url=request.seed_url,
                page_title="Example Admissions",
                program_name="Example Admissions",
            )

    monkeypatch.setattr("admission_browser_agent.cli.AdmissionsPipeline", StubPipeline)

    exit_code = main(
        [
            "--university",
            "Example University",
            "--seed-url",
            "https://example.edu/admissions",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "run_mode: generic" in captured.out
    assert "source_url: https://example.edu/admissions" in captured.out
    assert "page_title: Example Admissions" in captured.out
    assert f"raw_output_path: {tmp_path / 'raw-capture.json'}" in captured.out
    assert f"processed_output_path: {tmp_path / 'processed-capture.json'}" in captured.out
    assert f"debug_output_path: {tmp_path / 'debug-capture.json'}" in captured.out
    assert "candidate_pages_inspected: 2" in captured.out
    assert "follow_up_triggered: True" in captured.out
    assert "follow_up_candidates_found: 3" in captured.out
    assert "follow_up_candidates_fetched: 1" in captured.out
    assert "follow_up_fields_supplemented: True" in captured.out


def test_cli_homepage_alias_still_routes_to_generic_flow(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from admission_browser_agent.cli import main
    from admission_browser_agent.models import ExtractedProgramInfo

    class StubPipeline:
        def __init__(self, *, run_config, browser_session=None, extractor=None) -> None:
            self.run_config = run_config
            self.browser_session = browser_session
            self.extractor = extractor
            self.last_output_path = tmp_path / "raw-capture.json"
            self.last_processed_output_path = tmp_path / "processed-capture.json"
            self.last_debug_output_path = tmp_path / "debug-capture.json"
            self.last_inspected_candidate_count = 0
            self.last_debug_report = types.SimpleNamespace(
                follow_up_triggered=False,
                follow_up_candidates_found=0,
                follow_up_candidates_fetched=0,
                follow_up_fields_supplemented=False,
            )

        def run(self, request) -> ExtractedProgramInfo:
            assert request.university == "Example University"
            assert request.seed_url == "https://example.edu/"
            return ExtractedProgramInfo(
                source_url=request.seed_url,
                page_title="Homepage",
            )

    monkeypatch.setattr("admission_browser_agent.cli.AdmissionsPipeline", StubPipeline)

    exit_code = main(
        [
            "--mode",
            "homepage",
            "--university",
            "Example University",
            "--seed-url",
            "https://example.edu/",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "run_mode: generic" in captured.out
    assert "source_url: https://example.edu/" in captured.out


def test_official_seed_registry_loads_curated_targets() -> None:
    from admission_browser_agent.targets import load_official_seed_registry

    registry = load_official_seed_registry()
    program_codes = [target.program_code for target in registry.targets]
    hku_msc_ai = next(target for target in registry.targets if target.program_code == "HKU_MSC_AI")

    assert len(registry.targets) == 9
    assert program_codes[0] == "HKU_MSC_AI"
    assert program_codes[-1] == "CUHK_DSBS"
    assert hku_msc_ai.program_name == "Master of Science in Artificial Intelligence"
    assert [seed_page.page_type for seed_page in hku_msc_ai.seed_pages] == [
        "programme",
        "admissions",
        "faq",
    ]
    assert hku_msc_ai.seed_pages[2].intended_fields == [
        "english_requirement",
        "supporting_documents",
    ]


def test_pipeline_runs_official_seed_target_and_aggregates_fields(tmp_path: Path) -> None:
    from admission_browser_agent.config import RunConfig
    from admission_browser_agent.models import (
        ExtractedProgramInfo,
        OfficialSeedPage,
        OfficialTargetDefinition,
        RawPageCapture,
    )
    from admission_browser_agent.pipeline import AdmissionsPipeline

    target = OfficialTargetDefinition(
        university="Example University",
        program_code="EXAMPLE_MSCS",
        program_name="Master of Science in Computer Science",
        tier="target",
        seed_pages=[
            OfficialSeedPage(
                page_type="programme",
                url="https://example.edu/programme",
                priority=1,
                intended_fields=["program_name", "tuition"],
            ),
            OfficialSeedPage(
                page_type="admissions",
                url="https://example.edu/admissions",
                priority=2,
                intended_fields=["deadline", "academic_requirement"],
            ),
            OfficialSeedPage(
                page_type="faq",
                url="https://example.edu/faq",
                priority=3,
                intended_fields=["english_requirement"],
            ),
        ],
    )
    browser_session = MappingBrowserSession(
        page_with_links_map={},
        page_map={
            "https://example.edu/programme": RawPageCapture(
                source_url="https://example.edu/programme",
                page_title="Programme",
                body_text="Programme fee: HK$320,000\n",
            ),
            "https://example.edu/admissions": RawPageCapture(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                body_text="Application deadline: December 1, 2026\n",
            ),
            "https://example.edu/faq": RawPageCapture(
                source_url="https://example.edu/faq",
                page_title="FAQ",
                body_text="English language requirement: IELTS 6.5 overall or TOEFL 90.\n",
            ),
        },
    )
    extractor = MappingExtractor(
        extracted_by_url={
            "https://example.edu/programme": ExtractedProgramInfo(
                source_url="https://example.edu/programme",
                page_title="Programme",
                program_name="Master of Science in Computer Science",
                tuition="HK$320,000",
            ),
            "https://example.edu/admissions": ExtractedProgramInfo(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                deadline="December 1, 2026",
                academic_requirement="Bachelor's degree in computer science.",
            ),
            "https://example.edu/faq": ExtractedProgramInfo(
                source_url="https://example.edu/faq",
                page_title="FAQ",
                english_requirement="IELTS 6.5 overall or TOEFL 90.",
            ),
        }
    )
    pipeline = AdmissionsPipeline(
        run_config=RunConfig(
            raw_data_dir=tmp_path / "raw",
            processed_data_dir=tmp_path / "processed",
            debug_data_dir=tmp_path / "debug",
        ),
        browser_session=browser_session,
        extractor=extractor,
    )

    result = pipeline.run_official_seed_target(target)

    assert result.source_url == "https://example.edu/programme"
    assert result.page_title == "Programme"
    assert result.program_name == "Master of Science in Computer Science"
    assert result.tuition == "HK$320,000"
    assert result.deadline == "December 1, 2026"
    assert result.english_requirement == "IELTS 6.5 overall or TOEFL 90."
    assert result.field_sources == {
        "program_name": ["https://example.edu/programme"],
        "tuition": ["https://example.edu/programme"],
        "deadline": ["https://example.edu/admissions"],
        "english_requirement": ["https://example.edu/faq"],
        "academic_requirement": ["https://example.edu/admissions"],
    }
    assert browser_session.fetch_with_links_urls == [
        "https://example.edu/programme",
        "https://example.edu/admissions",
        "https://example.edu/faq",
    ]
    assert browser_session.fetch_urls == []
    assert pipeline.last_output_path is not None
    assert "official-seed" in str(pipeline.last_output_path)
    assert pipeline.last_processed_output_path is not None
    assert "official-seed" in str(pipeline.last_processed_output_path)
    assert pipeline.last_debug_report is not None
    assert pipeline.last_debug_report.run_mode == "official_seed"
    assert pipeline.last_debug_report.program_code == "EXAMPLE_MSCS"
    assert [page.page_type for page in pipeline.last_debug_report.inspected_pages] == [
        "programme",
        "admissions",
        "faq",
    ]


def test_pipeline_official_seed_prefers_field_sources_by_page_type(tmp_path: Path) -> None:
    from admission_browser_agent.config import RunConfig
    from admission_browser_agent.models import (
        ExtractedProgramInfo,
        OfficialSeedPage,
        OfficialTargetDefinition,
        RawPageCapture,
    )
    from admission_browser_agent.pipeline import AdmissionsPipeline

    target = OfficialTargetDefinition(
        university="Example University",
        program_code="EXAMPLE_MSAI",
        program_name="Master of Science in AI",
        tier="target",
        seed_pages=[
            OfficialSeedPage(
                page_type="programme_information",
                url="https://example.edu/programme",
                priority=1,
                intended_fields=["program_name", "tuition"],
            ),
            OfficialSeedPage(
                page_type="admissions",
                url="https://example.edu/admissions",
                priority=1,
                intended_fields=["deadline", "academic_requirement", "prerequisite_keywords"],
            ),
            OfficialSeedPage(
                page_type="english_faq",
                url="https://example.edu/english-faq",
                priority=2,
                intended_fields=["english_requirement"],
            ),
        ],
    )
    browser_session = MappingBrowserSession(
        page_with_links_map={},
        page_map={
            "https://example.edu/programme": RawPageCapture(
                source_url="https://example.edu/programme",
                page_title="Programme Information",
                body_text="Programme page",
            ),
            "https://example.edu/admissions": RawPageCapture(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                body_text="Admissions page",
            ),
            "https://example.edu/english-faq": RawPageCapture(
                source_url="https://example.edu/english-faq",
                page_title="English FAQ",
                body_text="FAQ page",
            ),
        },
    )
    extractor = MappingExtractor(
        extracted_by_url={
            "https://example.edu/programme": ExtractedProgramInfo(
                source_url="https://example.edu/programme",
                page_title="Programme Information",
                program_name="Master of Science in AI",
                tuition="HK$300,000",
                english_requirement="Medium of instruction is English.",
            ),
            "https://example.edu/admissions": ExtractedProgramInfo(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                program_name="Master of Science in AI",
                deadline="December 1, 2026",
                tuition="HK$300,000",
                english_requirement=(
                    "Applicants whose language of instruction is not English must satisfy "
                    "the University English language requirement applicable to higher degrees."
                ),
                academic_requirement="Bachelor's degree in computer science.",
                prerequisite_keywords=["calculus", "programming"],
            ),
            "https://example.edu/english-faq": ExtractedProgramInfo(
                source_url="https://example.edu/english-faq",
                page_title="English FAQ",
                program_name="Master of Science in AI",
                english_requirement="IELTS 6.5 overall or TOEFL 90.",
            ),
        }
    )
    pipeline = AdmissionsPipeline(
        run_config=RunConfig(
            raw_data_dir=tmp_path / "raw",
            processed_data_dir=tmp_path / "processed",
            debug_data_dir=tmp_path / "debug",
        ),
        browser_session=browser_session,
        extractor=extractor,
    )

    result = pipeline.run_official_seed_target(target)

    assert result.program_name == "Master of Science in AI"
    assert result.tuition == "HK$300,000"
    assert result.deadline == "December 1, 2026"
    assert result.english_requirement == "IELTS 6.5 overall or TOEFL 90."
    assert result.academic_requirement == "Bachelor's degree in computer science."
    assert result.prerequisite_keywords == ["calculus", "programming"]
    assert result.field_sources["program_name"] == ["https://example.edu/programme"]
    assert result.field_sources["tuition"] == ["https://example.edu/programme"]
    assert result.field_sources["deadline"] == ["https://example.edu/admissions"]
    assert result.field_sources["academic_requirement"] == ["https://example.edu/admissions"]
    assert result.field_sources["english_requirement"] == ["https://example.edu/english-faq"]
    assert result.field_sources["prerequisite_keywords"] == ["https://example.edu/admissions"]


def test_pipeline_official_seed_supplements_missing_deadline_and_tuition_from_seed_links(
    tmp_path: Path,
) -> None:
    from admission_browser_agent.config import RunConfig
    from admission_browser_agent.models import (
        CandidateLink,
        ExtractedProgramInfo,
        OfficialSeedPage,
        OfficialTargetDefinition,
        RawPageCapture,
    )
    from admission_browser_agent.pipeline import AdmissionsPipeline

    target = OfficialTargetDefinition(
        university="Example University",
        program_code="EXAMPLE_MDASC",
        program_name="Master of Data Science",
        tier="target",
        seed_pages=[
            OfficialSeedPage(
                page_type="overview",
                url="https://example.edu/",
                priority=1,
                intended_fields=["program_name", "tuition", "deadline"],
            ),
            OfficialSeedPage(
                page_type="admissions",
                url="https://example.edu/admissions",
                priority=1,
                intended_fields=["academic_requirement", "prerequisite_keywords"],
            ),
            OfficialSeedPage(
                page_type="english_faq",
                url="https://example.edu/english-faq",
                priority=2,
                intended_fields=["english_requirement"],
            ),
        ],
    )
    browser_session = MappingBrowserSession(
        page_with_links_map={
            "https://example.edu/": (
                RawPageCapture(
                    source_url="https://example.edu/",
                    page_title="Overview",
                    body_text="Master of Data Science",
                ),
                [
                    CandidateLink(anchor_text="Programme", url="https://example.edu/programme"),
                    CandidateLink(anchor_text="Apply Now", url="https://example.edu/apply-now"),
                    CandidateLink(anchor_text="News", url="https://example.edu/news"),
                ],
            ),
            "https://example.edu/admissions": (
                RawPageCapture(
                    source_url="https://example.edu/admissions",
                    page_title="Admissions",
                    body_text="Admissions page",
                ),
                [],
            ),
            "https://example.edu/english-faq": (
                RawPageCapture(
                    source_url="https://example.edu/english-faq",
                    page_title="English FAQ",
                    body_text="FAQ page",
                ),
                [],
            ),
        },
        page_map={
            "https://example.edu/": RawPageCapture(
                source_url="https://example.edu/",
                page_title="Overview",
                body_text="Master of Data Science",
            ),
            "https://example.edu/admissions": RawPageCapture(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                body_text="Applicants shall have taken calculus and programming.",
            ),
            "https://example.edu/english-faq": RawPageCapture(
                source_url="https://example.edu/english-faq",
                page_title="English FAQ",
                body_text="English language requirement: IELTS 6.5 overall or TOEFL 90.",
            ),
            "https://example.edu/programme": RawPageCapture(
                source_url="https://example.edu/programme",
                page_title="Programme",
                body_text="Local students: HK$169,920; Non-local students: HK$339,840",
            ),
            "https://example.edu/apply-now": RawPageCapture(
                source_url="https://example.edu/apply-now",
                page_title="Apply Now",
                body_text="Application deadline: December 1, 2025",
            ),
        },
    )
    extractor = MappingExtractor(
        extracted_by_url={
            "https://example.edu/": ExtractedProgramInfo(
                source_url="https://example.edu/",
                page_title="Overview",
                program_name="Master of Data Science",
            ),
            "https://example.edu/admissions": ExtractedProgramInfo(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                academic_requirement="Applicants shall have taken calculus and programming.",
                prerequisite_keywords=["calculus", "programming"],
            ),
            "https://example.edu/english-faq": ExtractedProgramInfo(
                source_url="https://example.edu/english-faq",
                page_title="English FAQ",
                english_requirement="IELTS 6.5 overall or TOEFL 90.",
            ),
            "https://example.edu/programme": ExtractedProgramInfo(
                source_url="https://example.edu/programme",
                page_title="Programme",
                tuition="Local students: HK$169,920; Non-local students: HK$339,840",
            ),
            "https://example.edu/apply-now": ExtractedProgramInfo(
                source_url="https://example.edu/apply-now",
                page_title="Apply Now",
                deadline="December 1, 2025",
            ),
        }
    )
    pipeline = AdmissionsPipeline(
        run_config=RunConfig(
            raw_data_dir=tmp_path / "raw",
            processed_data_dir=tmp_path / "processed",
            debug_data_dir=tmp_path / "debug",
        ),
        browser_session=browser_session,
        extractor=extractor,
    )

    result = pipeline.run_official_seed_target(target)

    assert result.program_name == "Master of Data Science"
    assert result.deadline == "December 1, 2025"
    assert result.tuition == "Local students: HK$169,920; Non-local students: HK$339,840"
    assert result.field_sources["deadline"] == ["https://example.edu/apply-now"]
    assert result.field_sources["tuition"] == ["https://example.edu/programme"]
    assert browser_session.fetch_with_links_urls == [
        "https://example.edu/",
        "https://example.edu/admissions",
        "https://example.edu/english-faq",
        "https://example.edu/apply-now",
        "https://example.edu/programme",
    ]
    assert browser_session.fetch_urls == []
    assert pipeline.last_debug_report is not None
    assert pipeline.last_debug_report.follow_up_triggered is True
    assert pipeline.last_debug_report.follow_up_missing_fields == ["deadline", "tuition"]
    assert pipeline.last_debug_report.follow_up_candidates_fetched == 2
    assert pipeline.last_debug_report.follow_up_fields_updated == ["deadline", "tuition"]
    assert pipeline.last_debug_report.follow_up_fields_supplemented is True
    assert pipeline.last_debug_report.follow_up_update_reason == "fields_supplemented"


def test_pipeline_official_seed_auto_discovers_second_hop_fee_page(tmp_path: Path) -> None:
    from admission_browser_agent.config import RunConfig
    from admission_browser_agent.models import (
        CandidateLink,
        ExtractedProgramInfo,
        OfficialSeedPage,
        OfficialTargetDefinition,
        RawPageCapture,
    )
    from admission_browser_agent.pipeline import AdmissionsPipeline

    target = OfficialTargetDefinition(
        university="Example University",
        program_code="EXAMPLE_AUTO",
        program_name="Master of Data Science",
        tier="target",
        seed_pages=[
            OfficialSeedPage(
                page_type="overview",
                url="https://example.edu/",
                priority=1,
                intended_fields=["program_name", "tuition", "deadline"],
            ),
            OfficialSeedPage(
                page_type="admissions",
                url="https://example.edu/admissions",
                priority=1,
                intended_fields=["academic_requirement", "prerequisite_keywords"],
            ),
        ],
    )
    browser_session = MappingBrowserSession(
        page_with_links_map={
            "https://example.edu/": (
                RawPageCapture(
                    source_url="https://example.edu/",
                    page_title="Overview",
                    body_text="Master of Data Science",
                ),
                [
                    CandidateLink(anchor_text="Programme", url="https://example.edu/programme"),
                    CandidateLink(anchor_text="Apply Now", url="https://example.edu/apply-now"),
                ],
            ),
            "https://example.edu/admissions": (
                RawPageCapture(
                    source_url="https://example.edu/admissions",
                    page_title="Admissions",
                    body_text="Applicants need calculus and programming background.",
                ),
                [],
            ),
            "https://example.edu/programme": (
                RawPageCapture(
                    source_url="https://example.edu/programme",
                    page_title="Programme",
                    body_text="Learn more about the programme",
                ),
                [
                    CandidateLink(anchor_text="Programme Fees", url="https://example.edu/programme-fees"),
                ],
            ),
            "https://example.edu/apply-now": (
                RawPageCapture(
                    source_url="https://example.edu/apply-now",
                    page_title="Apply Now",
                    body_text="Apply now",
                ),
                [],
            ),
            "https://example.edu/programme-fees": (
                RawPageCapture(
                    source_url="https://example.edu/programme-fees",
                    page_title="Programme Fees",
                    body_text="Local students: HK$169,920; Non-local students: HK$339,840",
                ),
                [],
            ),
        },
        page_map={},
    )
    extractor = MappingExtractor(
        extracted_by_url={
            "https://example.edu/": ExtractedProgramInfo(
                source_url="https://example.edu/",
                page_title="Overview",
                program_name="Master of Data Science",
            ),
            "https://example.edu/admissions": ExtractedProgramInfo(
                source_url="https://example.edu/admissions",
                page_title="Admissions",
                academic_requirement="Applicants need calculus and programming background.",
                prerequisite_keywords=["calculus", "programming"],
            ),
            "https://example.edu/programme": ExtractedProgramInfo(
                source_url="https://example.edu/programme",
                page_title="Programme",
            ),
            "https://example.edu/apply-now": ExtractedProgramInfo(
                source_url="https://example.edu/apply-now",
                page_title="Apply Now",
                deadline="December 1, 2025",
            ),
            "https://example.edu/programme-fees": ExtractedProgramInfo(
                source_url="https://example.edu/programme-fees",
                page_title="Programme Fees",
                tuition="HK$339,840",
            ),
        }
    )
    pipeline = AdmissionsPipeline(
        run_config=RunConfig(
            raw_data_dir=tmp_path / "raw",
            processed_data_dir=tmp_path / "processed",
            debug_data_dir=tmp_path / "debug",
        ),
        browser_session=browser_session,
        extractor=extractor,
    )

    result = pipeline.run_official_seed_target(target)

    assert result.deadline == "December 1, 2025"
    assert result.tuition == "HK$339,840"
    assert result.field_sources["deadline"] == ["https://example.edu/apply-now"]
    assert result.field_sources["tuition"] == ["https://example.edu/programme-fees"]
    assert browser_session.fetch_with_links_urls == [
        "https://example.edu/",
        "https://example.edu/admissions",
        "https://example.edu/apply-now",
        "https://example.edu/programme",
        "https://example.edu/programme-fees",
    ]
    assert pipeline.last_debug_report is not None
    assert pipeline.last_debug_report.follow_up_triggered is True
    assert pipeline.last_debug_report.follow_up_candidates_fetched == 3
    assert pipeline.last_debug_report.follow_up_fields_updated == ["deadline", "tuition"]
    assert any(
        page.inspection_stage == "official_seed_auto_candidate"
        and page.source_url == "https://example.edu/programme-fees"
        for page in pipeline.last_debug_report.inspected_pages
    )


def test_pipeline_official_seed_prefers_target_programme_details_over_generic_application_fees(
    tmp_path: Path,
) -> None:
    from admission_browser_agent.config import RunConfig
    from admission_browser_agent.models import (
        CandidateLink,
        ExtractedProgramInfo,
        OfficialSeedPage,
        OfficialTargetDefinition,
        RawPageCapture,
    )
    from admission_browser_agent.pipeline import AdmissionsPipeline

    target = OfficialTargetDefinition(
        university="HKU",
        program_code="HKU_MDASC",
        program_name="Master of Data Science",
        tier="target",
        seed_pages=[
            OfficialSeedPage(
                page_type="overview",
                url="https://mdasc.cds.hku.hk/",
                priority=1,
                intended_fields=["program_name", "deadline", "tuition"],
            ),
            OfficialSeedPage(
                page_type="admissions",
                url="https://mdasc.cds.hku.hk/admissions/",
                priority=1,
                intended_fields=["academic_requirement", "prerequisite_keywords"],
            ),
        ],
    )
    browser_session = MappingBrowserSession(
        page_with_links_map={
            "https://mdasc.cds.hku.hk/": (
                RawPageCapture(
                    source_url="https://mdasc.cds.hku.hk/",
                    page_title="Overview",
                    body_text="Master of Data Science",
                ),
                [
                    CandidateLink(
                        anchor_text="Programme Listing",
                        url="https://portal.hku.hk/tpg-admissions/programme-listing",
                    ),
                ],
            ),
            "https://mdasc.cds.hku.hk/admissions/": (
                RawPageCapture(
                    source_url="https://mdasc.cds.hku.hk/admissions/",
                    page_title="Admissions",
                    body_text="Applicants should have programming background.",
                ),
                [],
            ),
            "https://portal.hku.hk/tpg-admissions/programme-listing": (
                RawPageCapture(
                    source_url="https://portal.hku.hk/tpg-admissions/programme-listing",
                    page_title="Programme Listing",
                    body_text="Programme listing",
                ),
                [
                    CandidateLink(
                        anchor_text="Application Fees",
                        url="https://portal.hku.hk/tpg-admissions/applying/application-fees",
                    ),
                    CandidateLink(
                        anchor_text="School of Computing and Data Science Master of Data Science MDASC",
                        url=(
                            "https://portal.hku.hk/tpg-admissions/programme-details"
                            "?programme=master-of-data-science-cds&mode=0"
                        ),
                    ),
                ],
            ),
            (
                "https://portal.hku.hk/tpg-admissions/programme-details"
                "?programme=master-of-data-science-cds&mode=0"
            ): (
                RawPageCapture(
                    source_url=(
                        "https://portal.hku.hk/tpg-admissions/programme-details"
                        "?programme=master-of-data-science-cds&mode=0"
                    ),
                    page_title="Master of Data Science",
                    body_text=(
                        "Application deadline: December 1, 2025\n"
                        "Programme fee: HK$339,840"
                    ),
                ),
                [],
            ),
            "https://portal.hku.hk/tpg-admissions/applying/application-fees": (
                RawPageCapture(
                    source_url="https://portal.hku.hk/tpg-admissions/applying/application-fees",
                    page_title="Application Fees",
                    body_text="Application fee: HK$600",
                ),
                [],
            ),
        },
        page_map={},
    )
    extractor = MappingExtractor(
        extracted_by_url={
            "https://mdasc.cds.hku.hk/": ExtractedProgramInfo(
                source_url="https://mdasc.cds.hku.hk/",
                page_title="Overview",
                program_name="Master of Data Science",
            ),
            "https://mdasc.cds.hku.hk/admissions/": ExtractedProgramInfo(
                source_url="https://mdasc.cds.hku.hk/admissions/",
                page_title="Admissions",
                academic_requirement="Applicants should have programming background.",
                prerequisite_keywords=["programming"],
            ),
            "https://portal.hku.hk/tpg-admissions/programme-listing": ExtractedProgramInfo(
                source_url="https://portal.hku.hk/tpg-admissions/programme-listing",
                page_title="Programme Listing",
            ),
            (
                "https://portal.hku.hk/tpg-admissions/programme-details"
                "?programme=master-of-data-science-cds&mode=0"
            ): ExtractedProgramInfo(
                source_url=(
                    "https://portal.hku.hk/tpg-admissions/programme-details"
                    "?programme=master-of-data-science-cds&mode=0"
                ),
                page_title="Master of Data Science",
                deadline="December 1, 2025",
                tuition="HK$339,840",
            ),
            "https://portal.hku.hk/tpg-admissions/applying/application-fees": ExtractedProgramInfo(
                source_url="https://portal.hku.hk/tpg-admissions/applying/application-fees",
                page_title="Application Fees",
                tuition=None,
            ),
        }
    )
    pipeline = AdmissionsPipeline(
        run_config=RunConfig(
            raw_data_dir=tmp_path / "raw",
            processed_data_dir=tmp_path / "processed",
            debug_data_dir=tmp_path / "debug",
        ),
        browser_session=browser_session,
        extractor=extractor,
    )

    result = pipeline.run_official_seed_target(target)

    assert result.deadline == "December 1, 2025"
    assert result.tuition == "HK$339,840"
    assert result.field_sources["deadline"] == [
        "https://portal.hku.hk/tpg-admissions/programme-details?programme=master-of-data-science-cds&mode=0"
    ]
    assert result.field_sources["tuition"] == [
        "https://portal.hku.hk/tpg-admissions/programme-details?programme=master-of-data-science-cds&mode=0"
    ]
    assert (
        "https://portal.hku.hk/tpg-admissions/programme-details?programme=master-of-data-science-cds&mode=0"
        in browser_session.fetch_with_links_urls
    )
    assert "https://portal.hku.hk/tpg-admissions/applying/application-fees" not in browser_session.fetch_with_links_urls


def test_pipeline_official_seed_uses_english_seed_as_discovery_source_for_missing_fields(
    tmp_path: Path,
) -> None:
    from admission_browser_agent.config import RunConfig
    from admission_browser_agent.models import (
        CandidateLink,
        ExtractedProgramInfo,
        OfficialSeedPage,
        OfficialTargetDefinition,
        RawPageCapture,
    )
    from admission_browser_agent.pipeline import AdmissionsPipeline

    target = OfficialTargetDefinition(
        university="HKU",
        program_code="EXAMPLE_HKU",
        program_name="Master of Data Science",
        tier="target",
        seed_pages=[
            OfficialSeedPage(
                page_type="overview",
                url="https://mdasc.cds.hku.hk/",
                priority=1,
                intended_fields=["program_name", "deadline", "tuition"],
            ),
            OfficialSeedPage(
                page_type="admissions",
                url="https://mdasc.cds.hku.hk/admissions/",
                priority=1,
                intended_fields=["academic_requirement", "prerequisite_keywords"],
            ),
            OfficialSeedPage(
                page_type="english_faq",
                url="https://mdasc.cds.hku.hk/faq/english/",
                priority=2,
                intended_fields=["english_requirement"],
            ),
        ],
    )
    browser_session = MappingBrowserSession(
        page_with_links_map={
            "https://mdasc.cds.hku.hk/": (
                RawPageCapture(
                    source_url="https://mdasc.cds.hku.hk/",
                    page_title="Overview",
                    body_text="Master of Data Science",
                ),
                [
                    CandidateLink(anchor_text="Programme", url="https://mdasc.cds.hku.hk/programme/"),
                ],
            ),
            "https://mdasc.cds.hku.hk/admissions/": (
                RawPageCapture(
                    source_url="https://mdasc.cds.hku.hk/admissions/",
                    page_title="Admissions",
                    body_text="Applicants should have programming background.",
                ),
                [],
            ),
            "https://mdasc.cds.hku.hk/faq/english/": (
                RawPageCapture(
                    source_url="https://mdasc.cds.hku.hk/faq/english/",
                    page_title="English FAQ",
                    body_text="Please see https://portal.hku.hk/tpg-admissions/applying/admission-requirements",
                ),
                [
                    CandidateLink(
                        anchor_text="Admissions Requirements",
                        url="https://portal.hku.hk/tpg-admissions/applying/admission-requirements",
                    ),
                ],
            ),
            "https://mdasc.cds.hku.hk/programme/": (
                RawPageCapture(
                    source_url="https://mdasc.cds.hku.hk/programme/",
                    page_title="Programme",
                    body_text="Programme overview",
                ),
                [],
            ),
            "https://portal.hku.hk/tpg-admissions/applying/admission-requirements": (
                RawPageCapture(
                    source_url="https://portal.hku.hk/tpg-admissions/applying/admission-requirements",
                    page_title="Admission Requirements",
                    body_text="Application deadline: December 1, 2025\nProgramme fee: HK$339,840",
                ),
                [],
            ),
        },
        page_map={},
    )
    extractor = MappingExtractor(
        extracted_by_url={
            "https://mdasc.cds.hku.hk/": ExtractedProgramInfo(
                source_url="https://mdasc.cds.hku.hk/",
                page_title="Overview",
                program_name="Master of Data Science",
            ),
            "https://mdasc.cds.hku.hk/admissions/": ExtractedProgramInfo(
                source_url="https://mdasc.cds.hku.hk/admissions/",
                page_title="Admissions",
                academic_requirement="Applicants should have programming background.",
                prerequisite_keywords=["programming"],
            ),
            "https://mdasc.cds.hku.hk/faq/english/": ExtractedProgramInfo(
                source_url="https://mdasc.cds.hku.hk/faq/english/",
                page_title="English FAQ",
                english_requirement="University English requirement applies.",
            ),
            "https://mdasc.cds.hku.hk/programme/": ExtractedProgramInfo(
                source_url="https://mdasc.cds.hku.hk/programme/",
                page_title="Programme",
            ),
            "https://portal.hku.hk/tpg-admissions/applying/admission-requirements": ExtractedProgramInfo(
                source_url="https://portal.hku.hk/tpg-admissions/applying/admission-requirements",
                page_title="Admission Requirements",
                deadline="December 1, 2025",
                tuition="HK$339,840",
            ),
        }
    )
    pipeline = AdmissionsPipeline(
        run_config=RunConfig(
            raw_data_dir=tmp_path / "raw",
            processed_data_dir=tmp_path / "processed",
            debug_data_dir=tmp_path / "debug",
        ),
        browser_session=browser_session,
        extractor=extractor,
    )

    result = pipeline.run_official_seed_target(target)

    assert result.deadline == "December 1, 2025"
    assert result.tuition == "HK$339,840"
    assert result.field_sources["deadline"] == [
        "https://portal.hku.hk/tpg-admissions/applying/admission-requirements"
    ]
    assert result.field_sources["tuition"] == [
        "https://portal.hku.hk/tpg-admissions/applying/admission-requirements"
    ]
    assert "https://mdasc.cds.hku.hk/faq/english/" in browser_session.fetch_with_links_urls
    assert "https://portal.hku.hk/tpg-admissions/applying/admission-requirements" in (
        browser_session.fetch_with_links_urls
    )


def test_pipeline_run_official_seed_program_loads_registry_path(tmp_path: Path) -> None:
    from admission_browser_agent.config import RunConfig
    from admission_browser_agent.models import ExtractedProgramInfo, RawPageCapture
    from admission_browser_agent.pipeline import AdmissionsPipeline

    registry_path = tmp_path / "official_seed_pages.json"
    registry_path.write_text(
        json.dumps(
            {
                "targets": [
                    {
                        "university": "Example University",
                        "program_code": "EXAMPLE_MSDS",
                        "program_name": "Master of Science in Data Science",
                        "tier": "target",
                        "seed_pages": [
                            {
                                "page_type": "programme",
                                "url": "https://example.edu/programme",
                                "priority": 1,
                                "intended_fields": ["program_name", "tuition"],
                            },
                            {
                                "page_type": "english_faq",
                                "url": "https://example.edu/english-faq",
                                "priority": 2,
                                "intended_fields": ["english_requirement"],
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    browser_session = MappingBrowserSession(
        page_with_links_map={},
        page_map={
            "https://example.edu/programme": RawPageCapture(
                source_url="https://example.edu/programme",
                page_title="Programme",
                body_text="Programme fee: HK$280,000\n",
            ),
            "https://example.edu/english-faq": RawPageCapture(
                source_url="https://example.edu/english-faq",
                page_title="English FAQ",
                body_text="English language requirement: IELTS 6.5.\n",
            ),
        },
    )
    extractor = MappingExtractor(
        extracted_by_url={
            "https://example.edu/programme": ExtractedProgramInfo(
                source_url="https://example.edu/programme",
                page_title="Programme",
                program_name="Master of Science in Data Science",
                tuition="HK$280,000",
            ),
            "https://example.edu/english-faq": ExtractedProgramInfo(
                source_url="https://example.edu/english-faq",
                page_title="English FAQ",
                english_requirement="IELTS 6.5.",
            ),
        }
    )
    pipeline = AdmissionsPipeline(
        run_config=RunConfig(
            raw_data_dir=tmp_path / "raw",
            processed_data_dir=tmp_path / "processed",
            debug_data_dir=tmp_path / "debug",
        ),
        browser_session=browser_session,
        extractor=extractor,
    )

    result = pipeline.run_official_seed_program(
        program_code="EXAMPLE_MSDS",
        registry_path=registry_path,
    )

    assert result.program_name == "Master of Science in Data Science"
    assert result.tuition == "HK$280,000"
    assert result.english_requirement == "IELTS 6.5."
    assert result.field_sources["english_requirement"] == ["https://example.edu/english-faq"]
    assert browser_session.fetch_with_links_urls == [
        "https://example.edu/programme",
        "https://example.edu/english-faq",
    ]
    assert browser_session.fetch_urls == []


def test_cli_runs_official_seed_program_and_prints_summary(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from admission_browser_agent.cli import main
    from admission_browser_agent.models import (
        DebugRunReport,
        ExtractedProgramInfo,
        OfficialSeedPage,
        OfficialSeedRegistry,
        OfficialTargetDefinition,
    )

    registry = OfficialSeedRegistry(
        targets=[
            OfficialTargetDefinition(
                university="Example University",
                program_code="EXAMPLE_MSCS",
                program_name="Master of Science in Computer Science",
                tier="target",
                seed_pages=[
                    OfficialSeedPage(
                        page_type="programme",
                        url="https://example.edu/programme",
                        priority=1,
                        intended_fields=["program_name"],
                    )
                ],
            )
        ]
    )

    class StubPipeline:
        def __init__(self, *, run_config, browser_session=None, extractor=None) -> None:
            self.run_config = run_config
            self.browser_session = browser_session
            self.extractor = extractor
            self.last_output_path = tmp_path / "official-seed" / "raw-capture.json"
            self.last_processed_output_path = tmp_path / "official-seed" / "processed-capture.json"
            self.last_debug_output_path = tmp_path / "official-seed" / "debug-capture.json"
            self.last_debug_report = DebugRunReport(
                seed_url="https://example.edu/programme",
                seed_page_title="Programme",
                run_mode="official_seed",
                program_code="EXAMPLE_MSCS",
                program_name="Master of Science in Computer Science",
                inspected_pages=[
                    types.SimpleNamespace(),
                    types.SimpleNamespace(),
                ],
            )

        def run_official_seed_target(self, target) -> ExtractedProgramInfo:
            assert target.program_code == "EXAMPLE_MSCS"
            return ExtractedProgramInfo(
                source_url="https://example.edu/programme",
                page_title="Programme",
                program_name="Master of Science in Computer Science",
            )

    monkeypatch.setattr("admission_browser_agent.cli.load_official_seed_registry", lambda path=None: registry)
    monkeypatch.setattr("admission_browser_agent.cli.AdmissionsPipeline", StubPipeline)

    exit_code = main(
        [
            "--mode",
            "official-seed",
            "--program-code",
            "EXAMPLE_MSCS",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "run_mode: official-seed" in captured.out
    assert "program_code: EXAMPLE_MSCS" in captured.out
    assert "source_url: https://example.edu/programme" in captured.out
    assert "page_title: Programme" in captured.out
    assert f"raw_output_path: {tmp_path / 'official-seed' / 'raw-capture.json'}" in captured.out
    assert (
        f"processed_output_path: {tmp_path / 'official-seed' / 'processed-capture.json'}"
        in captured.out
    )
    assert f"debug_output_path: {tmp_path / 'official-seed' / 'debug-capture.json'}" in captured.out
    assert "seed_pages_inspected: 2" in captured.out


def test_cli_writes_gold_draft_for_official_seed_program(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from admission_browser_agent.cli import main
    from admission_browser_agent.evaluation import GoldLabelRecord
    from admission_browser_agent.models import (
        DebugRunReport,
        ExtractedProgramInfo,
        OfficialSeedPage,
        OfficialSeedRegistry,
        OfficialTargetDefinition,
    )

    registry = OfficialSeedRegistry(
        targets=[
            OfficialTargetDefinition(
                university="Example University",
                program_code="EXAMPLE_MSCS",
                program_name="Master of Science in Computer Science",
                tier="target",
                seed_pages=[
                    OfficialSeedPage(
                        page_type="programme",
                        url="https://example.edu/programme",
                        priority=1,
                        intended_fields=["program_name"],
                    )
                ],
            )
        ]
    )

    class StubPipeline:
        def __init__(self, *, run_config, browser_session=None, extractor=None) -> None:
            self.last_output_path = tmp_path / "official-seed" / "raw-capture.json"
            self.last_processed_output_path = tmp_path / "official-seed" / "processed-capture.json"
            self.last_debug_output_path = tmp_path / "official-seed" / "debug-capture.json"
            self.last_debug_report = DebugRunReport(
                seed_url="https://example.edu/programme",
                seed_page_title="Programme",
                run_mode="official_seed",
                program_code="EXAMPLE_MSCS",
                program_name="Master of Science in Computer Science",
                inspected_pages=[types.SimpleNamespace()],
            )

        def run_official_seed_target(self, target) -> ExtractedProgramInfo:
            assert target.program_code == "EXAMPLE_MSCS"
            return ExtractedProgramInfo(
                source_url="https://example.edu/programme",
                page_title="Programme",
                program_name="Master of Science in Computer Science",
            )

    draft_output_path = tmp_path / "gold-candidates" / "EXAMPLE_MSCS.json"
    draft_record = GoldLabelRecord(
        program_code="EXAMPLE_MSCS",
        university="Example University",
        mode="official_seed",
        label_status="manual_template_pending",
        fields={
            "program_name": "Master of Science in Computer Science",
            "deadline": None,
            "tuition": None,
            "english_requirement": None,
            "academic_requirement": None,
            "prerequisite_keywords": [],
        },
        coverage_expectations={
            "program_name": True,
            "deadline": False,
            "tuition": False,
            "english_requirement": False,
            "academic_requirement": False,
            "prerequisite_keywords": False,
        },
    )

    monkeypatch.setattr("admission_browser_agent.cli.load_official_seed_registry", lambda path=None: registry)
    monkeypatch.setattr("admission_browser_agent.cli.AdmissionsPipeline", StubPipeline)
    monkeypatch.setattr(
        "admission_browser_agent.cli.build_gold_label_draft",
        lambda target, extracted_result: draft_record,
    )
    monkeypatch.setattr(
        "admission_browser_agent.cli.write_gold_label_draft",
        lambda draft, output_dir: draft_output_path,
    )

    exit_code = main(
        [
            "--mode",
            "official-seed",
            "--program-code",
            "EXAMPLE_MSCS",
            "--propose-gold-draft",
            "--gold-draft-dir",
            str(tmp_path / "gold-candidates"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert f"gold_draft_output_path: {draft_output_path}" in captured.out


def test_gold_label_loader_reads_curated_example() -> None:
    from admission_browser_agent.evaluation import load_gold_label

    gold_label = load_gold_label(program_code="HKU_MSC_AI")

    assert gold_label.program_code == "HKU_MSC_AI"
    assert gold_label.university == "HKU"
    assert gold_label.label_status == "manually_curated_example"
    assert gold_label.fields["program_name"] == "Master of Science in Artificial Intelligence"
    assert gold_label.fields["english_requirement"] is None
    assert gold_label.coverage_expectations["english_requirement"] is False


def test_gold_label_loader_reads_completed_hku_mdasc_label() -> None:
    from admission_browser_agent.evaluation import load_gold_label

    gold_label = load_gold_label(program_code="HKU_MDASC")

    assert gold_label.program_code == "HKU_MDASC"
    assert gold_label.university == "HKU"
    assert gold_label.label_status == "completed"
    assert gold_label.fields["program_name"] == "Master of Data Science"
    assert gold_label.fields["deadline"] == "December 1, 2025"
    assert gold_label.fields["tuition"] == "HK$339,840"
    assert gold_label.fields["english_requirement"] == (
        "Applicants must satisfy the HKU higher degree English language requirement; "
        "refer to the University admissions requirements page for details."
    )
    assert gold_label.fields["academic_requirement"] == (
        "Applicants should have completed at least one course in calculus and algebra, "
        "one course in computer programming, and one course in introductory statistics or related areas."
    )
    assert gold_label.fields["prerequisite_keywords"] == [
        "calculus",
        "algebra",
        "programming",
        "statistics",
    ]
    assert gold_label.coverage_expectations == {
        "program_name": True,
        "deadline": True,
        "tuition": True,
        "english_requirement": True,
        "academic_requirement": True,
        "prerequisite_keywords": True,
    }


def test_gold_label_loader_reads_hkust_msc_bdt_template() -> None:
    from admission_browser_agent.evaluation import load_gold_label

    gold_label = load_gold_label(program_code="HKUST_MSC_BDT")

    assert gold_label.program_code == "HKUST_MSC_BDT"
    assert gold_label.university == "HKUST"
    assert gold_label.mode == "official_seed"
    assert isinstance(gold_label.label_status, str)
    assert set(gold_label.fields.keys()) == {
        "program_name",
        "deadline",
        "tuition",
        "english_requirement",
        "academic_requirement",
        "prerequisite_keywords",
    }
    assert isinstance(gold_label.fields["prerequisite_keywords"], list)
    assert set(gold_label.coverage_expectations.keys()) == {
        "program_name",
        "deadline",
        "tuition",
        "english_requirement",
        "academic_requirement",
        "prerequisite_keywords",
    }


def test_build_and_write_gold_label_draft_from_extraction(tmp_path: Path) -> None:
    from admission_browser_agent.evaluation import build_gold_label_draft, write_gold_label_draft
    from admission_browser_agent.models import ExtractedProgramInfo

    target = _make_benchmark_target()
    extracted = ExtractedProgramInfo(
        source_url="https://example.edu/programme",
        page_title="Programme",
        program_name="Master of Science in Computer Science",
        deadline="December 1, 2026",
        tuition="HK$320,000",
        english_requirement="IELTS 6.5 overall.",
        academic_requirement="Bachelor's degree in computer science.",
        prerequisite_keywords=["calculus", "programming"],
    )

    draft = build_gold_label_draft(
        target=target,
        extracted_result=extracted,
    )
    output_path = write_gold_label_draft(
        draft,
        output_dir=tmp_path / "candidates",
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert output_path.is_file()
    assert draft.label_status == "manual_template_pending"
    assert payload["program_code"] == "EXAMPLE_MSCS"
    assert payload["mode"] == "official_seed"
    assert payload["label_status"] == "manual_template_pending"
    assert payload["fields"]["program_name"] == "Master of Science in Computer Science"
    assert payload["fields"]["deadline"] == "December 1, 2026"
    assert payload["fields"]["tuition"] == "HK$320,000"
    assert payload["fields"]["english_requirement"] == "IELTS 6.5 overall."
    assert payload["fields"]["academic_requirement"] == "Bachelor's degree in computer science."
    assert payload["fields"]["prerequisite_keywords"] == ["calculus", "programming"]
    assert payload["coverage_expectations"]["program_name"] is True
    assert payload["coverage_expectations"]["english_requirement"] is True
    assert "Machine-generated draft" in payload["notes"]


def _write_official_seed_gold_label(
    tmp_path: Path,
    *,
    program_code: str = "EXAMPLE_MSCS",
    label_status: str,
    fields: dict[str, object],
    coverage_expectations: dict[str, bool] | None = None,
) -> Path:
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir(exist_ok=True)
    gold_path = gold_dir / f"{program_code}.json"
    gold_path.write_text(
        json.dumps(
            {
                "program_code": program_code,
                "university": "Example University",
                "mode": "official_seed",
                "label_status": label_status,
                "coverage_expectations": coverage_expectations
                or {
                    "program_name": True,
                    "deadline": True,
                    "tuition": True,
                    "english_requirement": True,
                    "academic_requirement": True,
                    "prerequisite_keywords": True,
                },
                "fields": fields,
            }
        ),
        encoding="utf-8",
    )
    return gold_path


def _make_benchmark_target():
    from admission_browser_agent.models import OfficialSeedPage, OfficialTargetDefinition

    return OfficialTargetDefinition(
        university="Example University",
        program_code="EXAMPLE_MSCS",
        program_name="Master of Science in Computer Science",
        tier="target",
        seed_pages=[
            OfficialSeedPage(
                page_type="programme",
                url="https://example.edu/programme",
                priority=1,
                intended_fields=["program_name", "tuition"],
            ),
            OfficialSeedPage(
                page_type="admissions",
                url="https://example.edu/admissions",
                priority=1,
                intended_fields=["deadline", "academic_requirement", "prerequisite_keywords"],
            ),
            OfficialSeedPage(
                page_type="english_faq",
                url="https://example.edu/english-faq",
                priority=1,
                intended_fields=["english_requirement"],
            ),
        ],
    )


def test_scalar_field_comparison_distinguishes_match_and_missing_source_coverage() -> None:
    from admission_browser_agent.evaluation import compare_scalar_field

    matched = compare_scalar_field(
        field_name="tuition",
        extracted_value="HK$320,000",
        gold_value=" HK$320,000 ",
        coverage_expected=True,
    )
    missing_coverage = compare_scalar_field(
        field_name="deadline",
        extracted_value=None,
        gold_value="December 1, 2026",
        coverage_expected=False,
    )
    left_null = compare_scalar_field(
        field_name="deadline",
        extracted_value=None,
        gold_value="December 1, 2026",
        coverage_expected=True,
    )

    assert matched.status == "matched"
    assert matched.score == 1.0
    assert missing_coverage.status == "missing_source_coverage"
    assert missing_coverage.score == 0.0
    assert left_null.status == "field_left_null"
    assert left_null.score == 0.0


def test_program_name_normalization_ignores_trailing_acronym_parenthetical() -> None:
    from admission_browser_agent.evaluation import compare_scalar_field

    result = compare_scalar_field(
        field_name="program_name",
        extracted_value="Master of Data Science (MDASC)",
        gold_value="Master of Data Science",
        coverage_expected=True,
    )

    assert result.status == "matched"
    assert result.normalized_extracted == "master of data science"


def test_english_requirement_canonical_normalization_matches_university_level_wording() -> None:
    from admission_browser_agent.evaluation import compare_scalar_field

    result = compare_scalar_field(
        field_name="english_requirement",
        extracted_value=(
            "A candidate who is seeking admission on the basis of a qualification from a "
            "university outside Hong Kong of which the language of teaching and/or examination "
            "is not English, is expected to satisfy the University English language requirement "
            "applicable to higher degrees."
        ),
        gold_value=(
            "Applicants must satisfy the HKU higher degree English language requirement; "
            "refer to the University admissions requirements page for details."
        ),
        coverage_expected=True,
    )

    assert result.status == "matched"
    assert result.normalized_extracted == "university higher degree english language requirement"
    assert result.normalized_gold == "university higher degree english language requirement"


def test_deadline_normalization_treats_leading_zero_day_as_equivalent() -> None:
    from admission_browser_agent.evaluation import compare_scalar_field

    result = compare_scalar_field(
        field_name="deadline",
        extracted_value="December 01, 2025",
        gold_value="December 1, 2025",
        coverage_expected=True,
    )

    assert result.status == "matched"
    assert result.normalized_extracted == "december 1, 2025"
    assert result.normalized_gold == "december 1, 2025"


def test_tuition_scalar_comparison_accepts_gold_amount_in_multi_amount_value() -> None:
    from admission_browser_agent.evaluation import compare_scalar_field

    result = compare_scalar_field(
        field_name="tuition",
        extracted_value="HK$324,000 Non-local: HK$339,840",
        gold_value="HK$339,840",
        coverage_expected=True,
    )

    assert result.status == "matched"
    assert result.score == 1.0
    assert result.reason == "Extracted tuition contains all gold tuition amount(s)."


def test_academic_requirement_canonical_normalization_matches_equivalent_course_wording() -> None:
    from admission_browser_agent.evaluation import compare_scalar_field

    result = compare_scalar_field(
        field_name="academic_requirement",
        extracted_value=(
            "Applicants shall have taken at least one university or post-secondary "
            "certificate course in each of the following three subjects (calculus and "
            "algebra, computer programming and introductory statistics) or related areas."
        ),
        gold_value=(
            "Applicants should have completed at least one course in calculus and algebra, "
            "one course in computer programming, and one course in introductory statistics "
            "or related areas."
        ),
        coverage_expected=True,
    )

    assert result.status == "matched"
    assert (
        result.normalized_extracted
        == "course_background_calculus_algebra_programming_statistics"
    )
    assert (
        result.normalized_gold
        == "course_background_calculus_algebra_programming_statistics"
    )


def test_keyword_field_comparison_reports_overlap_metrics() -> None:
    from admission_browser_agent.evaluation import compare_keyword_field

    result = compare_keyword_field(
        field_name="prerequisite_keywords",
        extracted_keywords=["Probability", "Linear Algebra", "Python"],
        gold_keywords=["probability", "calculus", "linear algebra"],
        coverage_expected=True,
    )

    assert result.status == "extraction_error"
    assert result.precision == pytest.approx(2 / 3)
    assert result.recall == pytest.approx(2 / 3)
    assert result.f1 == pytest.approx(2 / 3)
    assert result.score == pytest.approx(2 / 3)


def test_incomplete_template_gold_label_is_skipped_and_not_scored(tmp_path: Path) -> None:
    from admission_browser_agent.evaluation import evaluate_official_seed_result, load_gold_label
    from admission_browser_agent.models import ExtractedProgramInfo

    _write_official_seed_gold_label(
        tmp_path,
        label_status="manual_template_pending",
        fields={
            "program_name": None,
            "deadline": None,
            "tuition": None,
            "english_requirement": None,
            "academic_requirement": None,
            "prerequisite_keywords": [],
        },
    )
    report = evaluate_official_seed_result(
        target=_make_benchmark_target(),
        extracted_result=ExtractedProgramInfo(
            source_url="https://example.edu/programme",
            page_title="Programme",
            program_name="Master of Science in Computer Science",
            tuition="HK$320,000",
        ),
        gold_label=load_gold_label(program_code="EXAMPLE_MSCS", gold_dir=tmp_path / "gold"),
    )

    assert report.benchmark_status == "skipped_due_to_incomplete_gold_label"
    assert report.summary is not None
    assert report.summary.required_field_count == 0
    assert report.summary.scored_field_count == 0
    assert report.summary.score_not_meaningful is True
    assert report.summary.exact_match_rate is None
    assert report.summary.overall_field_score is None
    assert set(report.summary.skipped_fields_due_to_missing_truth) == {
        "program_name",
        "deadline",
        "tuition",
        "english_requirement",
        "academic_requirement",
        "prerequisite_keywords",
    }


def test_ready_gold_label_with_zero_required_fields_is_not_meaningful(tmp_path: Path) -> None:
    from admission_browser_agent.evaluation import evaluate_official_seed_result, load_gold_label
    from admission_browser_agent.models import ExtractedProgramInfo

    _write_official_seed_gold_label(
        tmp_path,
        label_status="manually_curated",
        fields={
            "program_name": None,
            "deadline": None,
            "tuition": None,
            "english_requirement": None,
            "academic_requirement": None,
            "prerequisite_keywords": [],
        },
    )
    report = evaluate_official_seed_result(
        target=_make_benchmark_target(),
        extracted_result=ExtractedProgramInfo(
            source_url="https://example.edu/programme",
            page_title="Programme",
        ),
        gold_label=load_gold_label(program_code="EXAMPLE_MSCS", gold_dir=tmp_path / "gold"),
    )

    assert report.benchmark_status == "score_not_meaningful"
    assert report.summary is not None
    assert report.summary.required_field_count == 0
    assert report.summary.scored_field_count == 0
    assert report.summary.score_not_meaningful is True
    assert report.summary.exact_match_rate is None
    assert report.summary.overall_field_score is None
    assert report.field_results["program_name"].status == "expected_null"


def test_partially_filled_incomplete_gold_label_reports_partial_scoring(tmp_path: Path) -> None:
    from admission_browser_agent.evaluation import evaluate_official_seed_result, load_gold_label
    from admission_browser_agent.models import ExtractedProgramInfo

    _write_official_seed_gold_label(
        tmp_path,
        label_status="manual_template_pending",
        fields={
            "program_name": "Master of Science in Computer Science",
            "deadline": "December 1, 2026",
            "tuition": None,
            "english_requirement": None,
            "academic_requirement": None,
            "prerequisite_keywords": [],
        },
    )
    report = evaluate_official_seed_result(
        target=_make_benchmark_target(),
        extracted_result=ExtractedProgramInfo(
            source_url="https://example.edu/programme",
            page_title="Programme",
            program_name="Master of Science in Computer Science",
        ),
        gold_label=load_gold_label(program_code="EXAMPLE_MSCS", gold_dir=tmp_path / "gold"),
    )

    assert report.benchmark_status == "incomplete_gold_label"
    assert report.summary is not None
    assert report.summary.required_field_count == 2
    assert report.summary.scored_field_count == 2
    assert report.summary.scored_fields == ["program_name", "deadline"]
    assert report.summary.score_not_meaningful is True
    assert report.summary.exact_match_rate is None
    assert report.summary.overall_field_score is None
    assert report.field_results["program_name"].status == "matched"
    assert report.field_results["deadline"].status == "field_left_null"
    assert set(report.summary.skipped_fields_due_to_missing_truth) == {
        "tuition",
        "english_requirement",
        "academic_requirement",
        "prerequisite_keywords",
    }


def test_completed_gold_label_reports_real_aggregate_scores(tmp_path: Path) -> None:
    from admission_browser_agent.evaluation import evaluate_official_seed_result, load_gold_label
    from admission_browser_agent.models import ExtractedProgramInfo

    _write_official_seed_gold_label(
        tmp_path,
        label_status="manually_curated",
        fields={
            "program_name": "Master of Science in Computer Science",
            "deadline": "December 1, 2026",
            "tuition": "HK$320,000",
            "english_requirement": None,
            "academic_requirement": "Bachelor's degree in computer science.",
            "prerequisite_keywords": ["calculus", "programming"],
        },
    )
    report = evaluate_official_seed_result(
        target=_make_benchmark_target(),
        extracted_result=ExtractedProgramInfo(
            source_url="https://example.edu/programme",
            page_title="Programme",
            program_name="Master of Science in Computer Science",
            deadline=None,
            tuition="HK$320,000",
            academic_requirement="Bachelor's degree in computer science.",
            prerequisite_keywords=["calculus"],
        ),
        gold_label=load_gold_label(program_code="EXAMPLE_MSCS", gold_dir=tmp_path / "gold"),
    )

    assert report.benchmark_status == "completed"
    assert report.summary is not None
    assert report.summary.required_field_count == 5
    assert report.summary.scored_field_count == 5
    assert report.summary.score_not_meaningful is False
    assert report.summary.field_coverage_rate == pytest.approx(0.8)
    assert report.summary.exact_match_rate == pytest.approx(0.6)
    assert report.summary.overall_field_score == pytest.approx((1 + 0 + 1 + 1 + (2 / 3)) / 5)


def test_evaluation_report_creation_writes_artifact(tmp_path: Path) -> None:
    from admission_browser_agent.evaluation import (
        evaluate_official_seed_result,
        load_gold_label,
        resolve_eval_output_dir,
        write_evaluation_report,
    )
    from admission_browser_agent.models import ExtractedProgramInfo, OfficialSeedPage, OfficialTargetDefinition

    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    gold_path = gold_dir / "EXAMPLE_MSCS.json"
    gold_path.write_text(
        json.dumps(
            {
                "program_code": "EXAMPLE_MSCS",
                "university": "Example University",
                "mode": "official_seed",
                "label_status": "manually_curated",
                "fields": {
                    "program_name": "Master of Science in Computer Science",
                    "deadline": "December 1, 2026",
                    "tuition": "HK$320,000",
                    "english_requirement": None,
                    "academic_requirement": "Bachelor's degree in computer science.",
                    "prerequisite_keywords": ["calculus", "programming"],
                },
            }
        ),
        encoding="utf-8",
    )
    target = OfficialTargetDefinition(
        university="Example University",
        program_code="EXAMPLE_MSCS",
        program_name="Master of Science in Computer Science",
        tier="target",
        seed_pages=[
            OfficialSeedPage(
                page_type="programme",
                url="https://example.edu/programme",
                priority=1,
                intended_fields=["program_name", "tuition"],
            ),
            OfficialSeedPage(
                page_type="admissions",
                url="https://example.edu/admissions",
                priority=1,
                intended_fields=["deadline", "academic_requirement", "prerequisite_keywords"],
            ),
        ],
    )
    extracted = ExtractedProgramInfo(
        source_url="https://example.edu/programme",
        page_title="Programme",
        program_name="Master of Science in Computer Science",
        deadline=None,
        tuition="HK$320,000",
        english_requirement=None,
        academic_requirement="Bachelor's degree in computer science.",
        prerequisite_keywords=["calculus"],
    )

    gold_label = load_gold_label(program_code="EXAMPLE_MSCS", gold_dir=gold_dir)
    report = evaluate_official_seed_result(
        target=target,
        extracted_result=extracted,
        gold_label=gold_label,
        processed_output_path=tmp_path / "processed.json",
        debug_output_path=tmp_path / "debug.json",
    )
    output_dir = resolve_eval_output_dir(processed_data_dir=tmp_path / "processed", mode_subdir="official-seed")
    artifact_path = write_evaluation_report(
        report,
        output_dir=output_dir,
        artifact_name="example-eval.json",
    )
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert artifact_path.is_file()
    assert payload["program_code"] == "EXAMPLE_MSCS"
    assert payload["benchmark_status"] == "completed"
    assert payload["summary"]["required_field_count"] == 5
    assert payload["summary"]["scored_field_count"] == 5
    assert payload["summary"]["field_coverage_rate"] == pytest.approx(0.8)
    assert payload["field_results"]["deadline"]["status"] == "field_left_null"
    assert payload["field_results"]["prerequisite_keywords"]["f1"] == pytest.approx(2 / 3)


def test_cli_runs_benchmark_for_official_seed_program(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from admission_browser_agent.cli import main
    from admission_browser_agent.evaluation import EvaluationReport, EvaluationSummary, FieldEvaluationResult, GoldLabelRecord
    from admission_browser_agent.models import (
        DebugRunReport,
        ExtractedProgramInfo,
        OfficialSeedPage,
        OfficialSeedRegistry,
        OfficialTargetDefinition,
    )

    registry = OfficialSeedRegistry(
        targets=[
            OfficialTargetDefinition(
                university="Example University",
                program_code="EXAMPLE_MSCS",
                program_name="Master of Science in Computer Science",
                tier="target",
                seed_pages=[
                    OfficialSeedPage(
                        page_type="programme",
                        url="https://example.edu/programme",
                        priority=1,
                        intended_fields=["program_name"],
                    )
                ],
            )
        ]
    )

    class StubPipeline:
        def __init__(self, *, run_config, browser_session=None, extractor=None) -> None:
            self.run_config = run_config
            self.browser_session = browser_session
            self.extractor = extractor
            self.last_output_path = tmp_path / "official-seed" / "raw-capture.json"
            self.last_processed_output_path = tmp_path / "official-seed" / "processed-capture.json"
            self.last_debug_output_path = tmp_path / "official-seed" / "debug-capture.json"
            self.last_debug_report = DebugRunReport(
                seed_url="https://example.edu/programme",
                seed_page_title="Programme",
                run_mode="official_seed",
                program_code="EXAMPLE_MSCS",
                program_name="Master of Science in Computer Science",
                inspected_pages=[types.SimpleNamespace()],
            )

        def run_official_seed_target(self, target) -> ExtractedProgramInfo:
            assert target.program_code == "EXAMPLE_MSCS"
            return ExtractedProgramInfo(
                source_url="https://example.edu/programme",
                page_title="Programme",
                program_name="Master of Science in Computer Science",
            )

    gold_label = GoldLabelRecord(
        program_code="EXAMPLE_MSCS",
        university="Example University",
        mode="official_seed",
        label_status="manually_curated",
        fields={
            "program_name": "Master of Science in Computer Science",
            "deadline": None,
            "tuition": None,
            "english_requirement": None,
            "academic_requirement": None,
            "prerequisite_keywords": [],
        },
    )
    evaluation_report = EvaluationReport(
        mode="official_seed",
        program_code="EXAMPLE_MSCS",
        university="Example University",
        label_status="manually_curated",
        gold_label_path=str(tmp_path / "gold" / "EXAMPLE_MSCS.json"),
        processed_output_path=str(tmp_path / "official-seed" / "processed-capture.json"),
        debug_output_path=str(tmp_path / "official-seed" / "debug-capture.json"),
        field_results={
            "program_name": FieldEvaluationResult(
                field_name="program_name",
                comparison_kind="scalar",
                extracted_value="Master of Science in Computer Science",
                gold_value="Master of Science in Computer Science",
                normalized_extracted="master of science in computer science",
                normalized_gold="master of science in computer science",
                score=1.0,
                exact_match=True,
                status="matched",
                coverage_expected=True,
                reason="Normalized extracted value matches the gold label.",
            )
        },
        summary=EvaluationSummary(
            required_field_count=1,
            covered_required_field_count=1,
            matched_required_field_count=1,
            extracted_populated_field_count=1,
            scored_field_count=1,
            field_coverage_rate=1.0,
            exact_match_rate=1.0,
            overall_field_score=1.0,
            score_not_meaningful=False,
            scored_fields=["program_name"],
            skipped_fields_due_to_missing_truth=[],
            missing_fields=[],
            status_counts={"matched": 1},
        ),
    )
    eval_output_path = tmp_path / "processed" / "eval" / "official-seed" / "processed-capture.json"

    monkeypatch.setattr("admission_browser_agent.cli.load_official_seed_registry", lambda path=None: registry)
    monkeypatch.setattr("admission_browser_agent.cli.AdmissionsPipeline", StubPipeline)
    monkeypatch.setattr(
        "admission_browser_agent.cli.load_gold_label",
        lambda program_code, gold_dir=None: gold_label,
    )
    monkeypatch.setattr(
        "admission_browser_agent.cli.evaluate_official_seed_result",
        lambda **kwargs: evaluation_report,
    )
    monkeypatch.setattr(
        "admission_browser_agent.cli.write_evaluation_report",
        lambda report, output_dir, artifact_name: eval_output_path,
    )

    exit_code = main(
        [
            "--mode",
            "official-seed",
            "--program-code",
            "EXAMPLE_MSCS",
            "--benchmark",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "benchmark_status: completed" in captured.out
    assert "gold_label_status: manually_curated" in captured.out
    assert f"gold_label_path: {evaluation_report.gold_label_path}" in captured.out
    assert f"evaluation_output_path: {eval_output_path}" in captured.out
    assert "required_field_count: 1" in captured.out
    assert "scored_field_count: 1" in captured.out
    assert "real_scored_fields: program_name" in captured.out
    assert "skipped_fields_due_to_missing_truth: none" in captured.out
    assert "score_not_meaningful: False" in captured.out
    assert "overall_field_score: 1.000" in captured.out


def test_resolve_target_definition_from_query_uses_short_alias() -> None:
    from admission_browser_agent.models import OfficialSeedPage, OfficialSeedRegistry, OfficialTargetDefinition
    from admission_browser_agent.targets import resolve_target_definition_from_query

    registry = OfficialSeedRegistry(
        targets=[
            OfficialTargetDefinition(
                university="HKU",
                program_code="HKU_MSC_AI",
                program_name="Master of Science in Artificial Intelligence",
                tier="reach",
                seed_pages=[
                    OfficialSeedPage(
                        page_type="admissions",
                        url="https://example.edu/hku-ai",
                        priority=1,
                        intended_fields=["deadline"],
                    )
                ],
            ),
            OfficialTargetDefinition(
                university="HKUST",
                program_code="HKUST_MSC_BDT",
                program_name="MSc in Big Data Technology",
                tier="target",
                seed_pages=[
                    OfficialSeedPage(
                        page_type="programme",
                        url="https://example.edu/hkust-bdt",
                        priority=1,
                        intended_fields=["tuition"],
                    )
                ],
            ),
        ]
    )

    resolved = resolve_target_definition_from_query(registry, query="HKU AI")

    assert resolved.program_code == "HKU_MSC_AI"


def test_extractor_includes_department_duration_and_foundation_mentions() -> None:
    from admission_browser_agent.extractor import AdmissionsExtractor
    from admission_browser_agent.models import RawPageCapture

    capture = RawPageCapture(
        source_url="https://example.edu/programme",
        page_title="Master of Science in Data Science",
        body_text=(
            "Department of Computer Science\n"
            "Duration: 1.5 years (full-time) / 2.5 years (part-time)\n"
            "Applicants should have background in statistics, programming, and linear algebra.\n"
        ),
    )

    result = AdmissionsExtractor().extract(capture=capture)

    assert result.department == "Department of Computer Science"
    assert "1.5 years" in (result.duration or "")
    assert result.foundation_mentions["statistics"] is True
    assert result.foundation_mentions["programming"] is True
    assert result.foundation_mentions["mathematics"] is True


def test_export_program_result_writes_json_csv_and_markdown(tmp_path: Path) -> None:
    from admission_browser_agent.exports import export_program_result, parse_export_formats
    from admission_browser_agent.models import ExtractedProgramInfo, OfficialSeedPage, OfficialTargetDefinition

    target = OfficialTargetDefinition(
        university="HKU",
        program_code="HKU_MSC_AI",
        program_name="Master of Science in Artificial Intelligence",
        tier="reach",
        seed_pages=[
            OfficialSeedPage(
                page_type="programme",
                url="https://example.edu/programme",
                priority=1,
                intended_fields=["program_name"],
            )
        ],
    )
    result = ExtractedProgramInfo(
        source_url="https://example.edu/programme",
        page_title="Programme",
        program_name="Master of Science in Artificial Intelligence",
        department="Department of Computer Science",
        duration="1.5 years",
        tuition="HK$390,000",
        deadline="December 1, 2026",
        english_requirement="IELTS 6.5",
        academic_requirement="Bachelor's degree",
        prerequisite_keywords=["statistics", "programming"],
        foundation_mentions={
            "statistics": True,
            "programming": True,
            "mathematics": False,
        },
    )

    formats = parse_export_formats("json,csv,markdown")
    output_paths = export_program_result(
        target=target,
        result=result,
        output_dir=tmp_path,
        artifact_stem="example",
        formats=formats,
    )

    assert output_paths["json"].is_file()
    assert output_paths["csv"].is_file()
    assert output_paths["markdown"].is_file()
    assert "Master of Science in Artificial Intelligence" in output_paths["json"].read_text(encoding="utf-8")
    assert "HK$390,000" in output_paths["csv"].read_text(encoding="utf-8")
    assert "| program_code |" in output_paths["markdown"].read_text(encoding="utf-8")


def test_cli_runs_mvp_mode_and_prints_export_paths(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from admission_browser_agent.cli import main
    from admission_browser_agent.models import (
        DebugRunReport,
        ExtractedProgramInfo,
        OfficialSeedPage,
        OfficialSeedRegistry,
        OfficialTargetDefinition,
    )

    target = OfficialTargetDefinition(
        university="HKU",
        program_code="HKU_MSC_AI",
        program_name="Master of Science in Artificial Intelligence",
        tier="reach",
        seed_pages=[
            OfficialSeedPage(
                page_type="programme",
                url="https://example.edu/programme",
                priority=1,
                intended_fields=["program_name"],
            )
        ],
    )
    registry = OfficialSeedRegistry(targets=[target])

    class StubPipeline:
        def __init__(self, *, run_config, browser_session=None, extractor=None) -> None:
            self.run_config = run_config
            self.last_output_path = tmp_path / "raw.json"
            self.last_processed_output_path = tmp_path / "processed.json"
            self.last_debug_output_path = tmp_path / "debug.json"
            self.last_debug_report = DebugRunReport(
                seed_url="https://example.edu/programme",
                seed_page_title="Programme",
                run_mode="official_seed",
                inspected_pages=[types.SimpleNamespace()],
            )

        def run_official_seed_target(self, selected_target) -> ExtractedProgramInfo:
            assert selected_target.program_code == "HKU_MSC_AI"
            return ExtractedProgramInfo(
                source_url="https://example.edu/programme",
                page_title="Programme",
                program_name="Master of Science in Artificial Intelligence",
            )

    export_paths = {
        "json": tmp_path / "mvp.json",
        "csv": tmp_path / "mvp.csv",
        "markdown": tmp_path / "mvp.md",
    }

    monkeypatch.setattr("admission_browser_agent.cli.AdmissionsPipeline", StubPipeline)
    monkeypatch.setattr("admission_browser_agent.cli.load_official_seed_registry", lambda path=None: registry)
    monkeypatch.setattr(
        "admission_browser_agent.cli.resolve_target_definition_from_query",
        lambda loaded_registry, query: target,
    )
    monkeypatch.setattr(
        "admission_browser_agent.cli.export_program_result",
        lambda **kwargs: export_paths,
    )

    exit_code = main(
        [
            "--mode",
            "mvp",
            "--query",
            "HKU AI",
            "--export-formats",
            "json,csv,markdown",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "run_mode: mvp" in captured.out
    assert "query: HKU AI" in captured.out
    assert "resolved_program_code: HKU_MSC_AI" in captured.out
    assert f"export_json_path: {export_paths['json']}" in captured.out
    assert f"export_csv_path: {export_paths['csv']}" in captured.out
    assert f"export_markdown_path: {export_paths['markdown']}" in captured.out
