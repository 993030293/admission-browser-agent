"""Minimal browser access built on the sync Playwright API."""

from __future__ import annotations

import re
from typing import Any, Sequence
from urllib.parse import urljoin, urlparse, urlunparse

from .config import BrowserConfig
from .models import CandidateLink, RawPageCapture

_VISIBLE_LINKS_SCRIPT = """
(elements) => elements.map((element) => {
  const rect = element.getBoundingClientRect();
  const style = window.getComputedStyle(element);
  const visible =
    style.visibility !== 'hidden' &&
    style.display !== 'none' &&
    (rect.width > 0 || rect.height > 0 || element.getClientRects().length > 0);
  return {
    href: element.getAttribute('href'),
    text: (element.innerText || element.textContent || '').trim(),
    visible
  };
})
"""


def extract_same_domain_candidate_links(
    source_url: str,
    raw_links: Sequence[dict[str, object]],
) -> list[CandidateLink]:
    """Resolve, filter, and deduplicate same-site visible links."""

    source_scope = _domain_scope_key(source_url)
    if not source_scope:
        return []

    seen_urls: set[str] = set()
    candidates: list[CandidateLink] = []

    for raw_link in raw_links:
        href = str(raw_link.get("href") or "").strip()
        anchor_text = _normalize_text(str(raw_link.get("text") or ""))
        is_visible = bool(raw_link.get("visible", True))

        if not is_visible or not href:
            continue

        lowered_href = href.lower()
        if lowered_href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        resolved_url = _strip_fragment(urljoin(source_url, href))
        if not _is_http_url(resolved_url):
            continue

        if _domain_scope_key(resolved_url) != source_scope:
            continue

        if resolved_url in seen_urls:
            continue

        seen_urls.add(resolved_url)
        candidates.append(CandidateLink(anchor_text=anchor_text, url=resolved_url))

    return candidates


def _strip_fragment(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(fragment=""))


def _normalized_host(url: str) -> str:
    hostname = (urlparse(url).hostname or "").lower()
    if hostname.startswith("www."):
        return hostname[4:]
    return hostname


def _domain_scope_key(url: str) -> str:
    """Return a conservative site-scope key for same-site filtering."""

    host = _normalized_host(url)
    if not host:
        return ""
    parts = host.split(".")
    if len(parts) <= 2:
        return host

    second_level_markers = {"co", "com", "org", "net", "gov", "edu", "ac"}
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in second_level_markers:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _is_http_url(url: str) -> bool:
    return urlparse(url).scheme in {"http", "https"}


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _extract_text_urls(body_text: str) -> list[str]:
    return re.findall(r"https?://[^\s)>\]}]+", body_text)


class BrowserSession:
    """A thin wrapper around a single Playwright browser context."""

    def __init__(self, config: BrowserConfig | None = None) -> None:
        self.config = config or BrowserConfig()
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._context: Any | None = None

    @property
    def started(self) -> bool:
        """Whether the browser session has been started."""

        return self._context is not None

    def start(self) -> None:
        """Initialize Playwright and open a browser context."""

        if self.started:
            return

        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Playwright is not installed. Install dependencies and run 'playwright install'."
            ) from exc

        try:
            self._playwright = sync_playwright().start()
            browser_type = getattr(self._playwright, self.config.browser_name, None)
            if browser_type is None:
                raise ValueError(f"Unsupported browser name: {self.config.browser_name!r}.")

            self._browser = browser_type.launch(headless=self.config.headless)

            context_kwargs: dict[str, Any] = {}
            if self.config.user_agent:
                context_kwargs["user_agent"] = self.config.user_agent

            self._context = self._browser.new_context(**context_kwargs)
        except Exception:
            self.close()
            raise

    def open_page(self, url: str) -> RawPageCapture:
        """Open one page and capture its title and visible body text."""

        if not self.started:
            raise RuntimeError("BrowserSession.start() must be called before open_page().")

        if not url:
            raise ValueError("A non-empty URL is required.")

        from playwright.sync_api import Error as PlaywrightError

        page = None
        try:
            page = self._context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=self.config.timeout_ms)
            page.wait_for_load_state("domcontentloaded", timeout=self.config.timeout_ms)
            self._stabilize_page(page)
            title = (page.title() or "").strip()
            body_text = self._read_body_text(page)
            return RawPageCapture(
                source_url=page.url,
                page_title=title,
                body_text=body_text,
            )
        except PlaywrightError as exc:
            raise RuntimeError(f"Failed to fetch page {url!r}: {exc}") from exc
        finally:
            if page is not None:
                page.close()

    def fetch_page(self, url: str) -> RawPageCapture:
        """Fetch one page using a short-lived browser session."""

        self.start()
        try:
            return self.open_page(url)
        finally:
            self.close()

    def open_page_with_links(self, url: str) -> tuple[RawPageCapture, list[CandidateLink]]:
        """Open one page and return its capture plus same-domain candidate links."""

        if not self.started:
            raise RuntimeError("BrowserSession.start() must be called before open_page_with_links().")

        if not url:
            raise ValueError("A non-empty URL is required.")

        from playwright.sync_api import Error as PlaywrightError

        page = None
        try:
            page = self._context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=self.config.timeout_ms)
            page.wait_for_load_state("domcontentloaded", timeout=self.config.timeout_ms)
            self._stabilize_page(page)
            title = (page.title() or "").strip()
            body_text = self._read_body_text(page)
            raw_links = page.locator("a[href]").evaluate_all(_VISIBLE_LINKS_SCRIPT)
            for text_url in _extract_text_urls(body_text):
                raw_links.append(
                    {
                        "href": text_url,
                        "text": text_url,
                        "visible": True,
                    }
                )
            capture = RawPageCapture(
                source_url=page.url,
                page_title=title,
                body_text=body_text,
            )
            return capture, extract_same_domain_candidate_links(page.url, raw_links)
        except PlaywrightError as exc:
            raise RuntimeError(f"Failed to fetch page {url!r}: {exc}") from exc
        finally:
            if page is not None:
                page.close()

    def _stabilize_page(self, page: Any) -> None:
        """Best-effort wait for late-rendered content without failing the fetch."""

        from playwright.sync_api import Error as PlaywrightError

        network_idle_timeout_ms = min(5_000, self.config.timeout_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=network_idle_timeout_ms)
        except PlaywrightError:
            pass

        if self.config.stabilization_wait_ms <= 0:
            return

        try:
            page.wait_for_timeout(self.config.stabilization_wait_ms)
        except PlaywrightError:
            pass

    def _read_body_text(self, page: Any) -> str:
        """Capture body text after a short best-effort lazy-content scroll pass."""

        body = page.locator("body")
        best_text = body.inner_text(timeout=self.config.timeout_ms).strip()
        best_score = self._body_text_score(best_text)

        for _ in range(2):
            if not self._scroll_page(page):
                break
            candidate_text = body.inner_text(timeout=self.config.timeout_ms).strip()
            candidate_score = self._body_text_score(candidate_text)
            if candidate_score > best_score:
                best_text = candidate_text
                best_score = candidate_score

        return best_text

    def _scroll_page(self, page: Any) -> bool:
        """Best-effort scroll to trigger lazy-loaded content."""

        from playwright.sync_api import Error as PlaywrightError

        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            if self.config.stabilization_wait_ms > 0:
                page.wait_for_timeout(min(self.config.stabilization_wait_ms, 1_000))
            return True
        except PlaywrightError:
            return False

    @staticmethod
    def _body_text_score(text: str) -> tuple[int, int]:
        """Prefer denser captures that contain more high-value visible content."""

        normalized = _normalize_text(text)
        if not normalized:
            return (0, 0)
        line_count = text.count("\n") + 1
        return (len(normalized), line_count)

    def fetch_page_with_links(self, url: str) -> tuple[RawPageCapture, list[CandidateLink]]:
        """Fetch one page and discover same-domain candidate links from it."""

        self.start()
        try:
            return self.open_page_with_links(url)
        finally:
            self.close()

    def close(self) -> None:
        """Close the browser context and Playwright runtime."""

        context = self._context
        browser = self._browser
        playwright = self._playwright

        self._context = None
        self._browser = None
        self._playwright = None

        if context is not None:
            context.close()
        if browser is not None:
            browser.close()
        if playwright is not None:
            playwright.stop()
