"""Base interfaces for university-specific source adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import CrawlRequest, ProgramRecord


class UniversitySource(ABC):
    """Contract for future university-specific adapters."""

    name: str = "base"

    @abstractmethod
    def matches(self, url: str) -> bool:
        """Return whether this source should handle the given URL."""

    @abstractmethod
    def build_request(self, url: str) -> CrawlRequest:
        """Create a normalized crawl request for this source."""

    def normalize_record(self, record: ProgramRecord) -> ProgramRecord:
        """Allow source-specific cleanup once extraction exists."""

        return record
