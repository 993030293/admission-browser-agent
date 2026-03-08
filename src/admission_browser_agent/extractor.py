"""Rule-based extraction for admissions fields from a single page capture."""

from __future__ import annotations

import re
from typing import Callable

from .models import ExtractedProgramInfo, RawPageCapture


class AdmissionsExtractor:
    """Extract a small set of admissions fields with regex and keyword heuristics."""

    _MONTH_PATTERN = (
        r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?)"
    )
    _DATE_PATTERNS = (
        re.compile(rf"\b{_MONTH_PATTERN}\s+\d{{1,2}}(?:,\s*\d{{4}})?\b", re.IGNORECASE),
        re.compile(rf"\b\d{{1,2}}\s+{_MONTH_PATTERN}\s+\d{{4}}\b", re.IGNORECASE),
        re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
        re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    )
    _CURRENCY_PATTERN = re.compile(
        r"\b(?:HK\$|US\$|USD|EUR|GBP|\$)\s*\d[\d,]*(?:\.\d{2})?\b",
        re.IGNORECASE,
    )
    _PROGRAM_PATTERNS = (
        re.compile(
            r"\b(?:Master|Doctor|Bachelor)\s+of\s+[A-Za-z][A-Za-z0-9&(),/ \-]{4,}",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:MSc|MS|MA|MPhil|PhD|MBA|LLM)\s*(?:\([^)]+\)|in\s+[A-Za-z][A-Za-z0-9&(),/ \-]+)?",
            re.IGNORECASE,
        ),
    )
    _DEPARTMENT_PATTERNS = (
        re.compile(
            r"\b(?:Department|School|Faculty|College|Institute)\s+of\s+[A-Za-z][A-Za-z0-9&(),/ \-]{2,}",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:Department|School|Faculty|College|Institute)\s+[A-Za-z][A-Za-z0-9&(),/ \-]{2,}",
            re.IGNORECASE,
        ),
    )
    _DURATION_PATTERNS = (
        re.compile(
            r"\b\d(?:\.\d+)?\s*(?:year|years|month|months)\b(?:[^.]{0,80}?\b(?:full[- ]time|part[- ]time)\b)?",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:full[- ]time|part[- ]time)\b[^.]{0,80}?\b\d(?:\.\d+)?\s*(?:year|years|month|months)\b",
            re.IGNORECASE,
        ),
    )
    _HEADER_LABELS = (
        "english requirement",
        "english requirements",
        "english language requirement",
        "english language requirements",
        "english proficiency requirement",
        "english proficiency requirements",
        "academic requirement",
        "academic requirements",
        "admission requirement",
        "admission requirements",
        "entry requirement",
        "entry requirements",
        "prerequisite",
        "prerequisites",
        "tuition fee",
        "tuition fees",
        "programme fee",
        "programme fees",
        "program fee",
        "program fees",
        "admission schedule",
        "application schedule",
        "important dates",
        "key dates",
    )
    _ENGLISH_REQUIREMENT_LABELS = (
        "english requirement",
        "english requirements",
        "english language requirement",
        "english language requirements",
        "english proficiency requirement",
        "english proficiency requirements",
        "proof of english proficiency",
    )
    _ACADEMIC_REQUIREMENT_LABELS = (
        "academic requirement",
        "academic requirements",
        "admission requirement",
        "admission requirements",
        "entry requirement",
        "entry requirements",
    )
    _DEADLINE_LABELS = (
        "application deadline",
        "application deadlines",
        "deadline for application",
        "deadline for applications",
        "priority deadline",
        "submission deadline",
        "submit your application by",
        "deadline",
        "deadlines",
        "apply by",
        "applications close",
        "application closes",
        "closing date",
        "closing dates",
        "admission schedule",
        "application schedule",
        "important dates",
        "key dates",
        "timeline",
    )
    _TUITION_LABELS = (
        "tuition fee",
        "tuition fees",
        "tuition",
        "programme fee",
        "programme fees",
        "program fee",
        "program fees",
        "fee",
        "fees",
    )
    _DURATION_LABELS = (
        "duration",
        "study period",
        "normal study period",
        "period of study",
        "study mode",
    )
    _OPENING_KEYWORDS = (
        "opens on",
        "opening on",
        "opening date",
        "open on",
        "intake opens",
        "applications open",
        "application opens",
    )
    _TUITION_REJECTION_KEYWORDS = (
        "application fee",
        "application fees",
        "application form fee",
        "caution money",
        "student activity fee",
        "graduation fee",
        "re-examination",
        "re examination",
        "repeating",
    )
    _DEADLINE_REJECTION_KEYWORDS = (
        "please visit",
        "for details",
        "for detail",
        "read article",
        "application method",
        "for more information",
        "for the latest information",
    )
    _DEADLINE_EVENT_NOISE_KEYWORDS = (
        "fair",
        "information session",
        "webinar",
        "event",
        "pm",
        "am",
    )
    _ENGLISH_TEST_KEYWORDS = (
        "ielts",
        "toefl",
        "pte",
        "duolingo",
    )
    _ENGLISH_REQUIREMENT_SIGNAL_KEYWORDS = (
        "english language requirement",
        "english language requirements",
        "university english language requirement",
        "language requirement",
        "language requirements",
        "language proficiency",
        "english proficiency",
        "proof of english proficiency",
        "expected to satisfy",
        "must satisfy",
        "required to satisfy",
        "shall satisfy",
        "satisfy the university english language requirement",
        "waiver",
        "waive",
        "exemption",
        "exempt",
    )
    _MEDIUM_OF_INSTRUCTION_KEYWORDS = (
        "medium of instruction",
        "language of teaching",
        "language of instruction",
        "taught in english",
        "teaching and/or examination",
    )
    _QUESTION_PROMPT_KEYWORDS = (
        "are there any",
        "do i need to",
        "what are the minimum",
        "how may we help you",
        "search for",
    )
    _HEADER_CONTEXT_KEYWORDS = (
        "requirement",
        "requirements",
        "deadline",
        "deadlines",
        "tuition",
        "fee",
        "fees",
        "schedule",
        "dates",
        "duration",
        "instruction",
        "documents",
        "prerequisite",
        "prerequisites",
        "information",
    )
    _PREREQUISITE_PATTERNS = (
        ("computer science", re.compile(r"\bcomputer science\b", re.IGNORECASE)),
        ("mathematics", re.compile(r"\bmathematics?\b|\bmath\b", re.IGNORECASE)),
        ("statistics", re.compile(r"\bstatistics?\b", re.IGNORECASE)),
        ("algebra", re.compile(r"(?<!linear )\balgebra\b", re.IGNORECASE)),
        ("probability", re.compile(r"\bprobabilit(?:y|ies)\b", re.IGNORECASE)),
        ("linear algebra", re.compile(r"\blinear algebra\b", re.IGNORECASE)),
        ("calculus", re.compile(r"\bcalculus\b", re.IGNORECASE)),
        ("programming", re.compile(r"\bprogramming\b", re.IGNORECASE)),
        ("python", re.compile(r"\bpython\b", re.IGNORECASE)),
        ("machine learning", re.compile(r"\bmachine learning\b", re.IGNORECASE)),
        ("algorithms", re.compile(r"\balgorithms?\b", re.IGNORECASE)),
        ("data structures", re.compile(r"\bdata structures?\b", re.IGNORECASE)),
    )
    _FOUNDATION_MENTION_PATTERNS = {
        "statistics": re.compile(r"\bstatistics?\b|\bprobabilit(?:y|ies)\b", re.IGNORECASE),
        "programming": re.compile(r"\bprogramming\b|\bpython\b|\bcoding\b", re.IGNORECASE),
        "mathematics": re.compile(
            r"\bmathematics?\b|\bmath\b|\bcalculus\b|\balgebra\b|\blinear algebra\b",
            re.IGNORECASE,
        ),
    }

    def extract(
        self,
        *,
        capture: RawPageCapture,
    ) -> ExtractedProgramInfo:
        """Convert one raw page capture into a structured heuristic result."""

        lines = self._build_lines(capture)
        academic_requirement = self._extract_academic_requirement(lines)
        prerequisite_keywords = self._extract_prerequisite_keywords(lines, academic_requirement)
        foundation_mentions = self._extract_foundation_mentions(
            lines,
            prerequisite_keywords=prerequisite_keywords,
        )

        return ExtractedProgramInfo(
            source_url=capture.source_url,
            page_title=capture.page_title,
            program_name=self._extract_program_name(capture.page_title, lines),
            department=self._extract_department(lines),
            duration=self._extract_duration(lines),
            deadline=self._extract_deadline(lines),
            tuition=self._extract_tuition(lines),
            english_requirement=self._extract_english_requirement(lines),
            academic_requirement=academic_requirement,
            prerequisite_keywords=prerequisite_keywords,
            foundation_mentions=foundation_mentions,
        )

    def _build_lines(self, capture: RawPageCapture) -> list[str]:
        combined_text = f"{capture.page_title}\n{capture.body_text}"
        lines: list[str] = []
        for raw_line in combined_text.splitlines():
            line = self._normalize_text(raw_line)
            if line:
                lines.append(line)
        return lines

    def _extract_program_name(self, page_title: str, lines: list[str]) -> str | None:
        candidates = [page_title, *lines[:10]]
        for candidate in candidates:
            normalized = self._normalize_text(candidate)
            for pattern in self._PROGRAM_PATTERNS:
                match = pattern.search(normalized)
                if match:
                    return self._clean_program_name(match.group(0))
        return None

    def _extract_department(self, lines: list[str]) -> str | None:
        for line in lines[:40]:
            normalized = self._normalize_text(line)
            for pattern in self._DEPARTMENT_PATTERNS:
                match = pattern.search(normalized)
                if match:
                    value = self._clean_extracted_text(match.group(0))
                    if value and len(value.split()) >= 3:
                        return value
        return None

    def _extract_duration(self, lines: list[str]) -> str | None:
        candidates: list[tuple[int, str]] = []
        for index, line in enumerate(lines):
            snippet = self._snippet_with_context(lines, index)
            lowered = snippet.lower()
            if not any(keyword in lowered for keyword in ("duration", "full-time", "part-time", "year", "month")):
                continue

            labeled_value = self._clean_extracted_text(self._strip_label(snippet, self._DURATION_LABELS))
            if re.search(r"\b\d(?:\.\d+)?\s*(?:year|years|month|months)\b", labeled_value, re.IGNORECASE):
                score = 18 + len(labeled_value)
                if "/" in labeled_value:
                    score += 4
                if "full-time" in labeled_value.lower() and "part-time" in labeled_value.lower():
                    score += 4
                candidates.append((score, labeled_value))

            for pattern in self._DURATION_PATTERNS:
                match = pattern.search(snippet)
                if match is None:
                    continue
                value = self._clean_extracted_text(match.group(0))
                score = 5 + len(value)
                if re.match(r"^\d", value):
                    score += 3
                if "duration" in lowered:
                    score += 8
                if "full-time" in lowered or "part-time" in lowered:
                    score += 4
                candidates.append((score, value))
        return self._best_candidate_text(candidates)

    def _extract_deadline(self, lines: list[str]) -> str | None:
        candidates: list[tuple[int, str]] = []
        for index, line in enumerate(lines):
            snippet = self._snippet_with_context(lines, index)
            lowered_line = line.lower()
            lowered_snippet = snippet.lower()

            if self._is_opening_sentence(lowered_snippet):
                continue
            if self._is_deadline_noise(lowered_snippet):
                continue

            if not self._is_deadline_candidate(lines, index, lowered_line, lowered_snippet):
                continue

            date = self._extract_date(snippet)
            if date:
                score = 10
                if any(keyword in lowered_snippet for keyword in self._DEADLINE_LABELS):
                    score += 4
                if "round" in lowered_snippet:
                    score += 2
                candidates.append((score, date))
                continue

            cleaned = self._clean_extracted_text(self._strip_label(snippet, self._DEADLINE_LABELS))
            if cleaned and self._is_deadline_value(cleaned):
                score = 4
                if any(keyword in lowered_snippet for keyword in self._DEADLINE_LABELS):
                    score += 2
                candidates.append((score, cleaned))

        return self._best_candidate_text(candidates)

    def _extract_tuition(self, lines: list[str]) -> str | None:
        candidates: list[tuple[int, str]] = []
        for index, _line in enumerate(lines):
            snippet = self._snippet_with_context(lines, index)
            if not self._is_tuition_line(snippet.lower()):
                continue

            cleaned = self._clean_extracted_text(self._strip_label(snippet, self._TUITION_LABELS))
            cleaned = self._extract_tuition_value(cleaned)
            score = self._tuition_candidate_score(cleaned)
            if score > 0:
                candidates.append((score, cleaned))

        return self._best_candidate_text(candidates)

    def _extract_english_requirement(self, lines: list[str]) -> str | None:
        candidates: list[tuple[int, str]] = []
        for index, _line in enumerate(lines):
            snippet = self._snippet_with_context(lines, index)
            if not self._is_english_requirement_line(snippet.lower()):
                continue

            cleaned = self._clean_extracted_text(
                self._strip_label(snippet, self._ENGLISH_REQUIREMENT_LABELS)
            )
            english_sentence = self._extract_relevant_sentence(cleaned, self._is_english_requirement_line)
            score = self._english_requirement_candidate_score(english_sentence)
            if score > 0 and english_sentence:
                candidates.append((score, english_sentence))

        return self._best_candidate_text(candidates)

    def _extract_academic_requirement(self, lines: list[str]) -> str | None:
        candidates: list[tuple[int, str]] = []
        for index, _line in enumerate(lines):
            snippet = self._snippet_with_context(lines, index)
            if not self._is_academic_requirement_line(snippet.lower()):
                continue

            cleaned = self._clean_extracted_text(
                self._strip_label(snippet, self._ACADEMIC_REQUIREMENT_LABELS)
            )
            cleaned = self._trim_requirement_lead_in(cleaned)
            academic_sentence = self._extract_relevant_sentence(
                cleaned,
                self._is_academic_requirement_line,
            )
            score = self._academic_requirement_candidate_score(academic_sentence)
            if score > 0 and academic_sentence:
                candidates.append((score, academic_sentence))

        return self._best_candidate_text(candidates)

    def _extract_prerequisite_keywords(
        self,
        lines: list[str],
        academic_requirement: str | None,
    ) -> list[str]:
        context_keywords = (
            "prerequisite",
            "prerequisites",
            "background in",
            "knowledge of",
            "experience in",
            "experience with",
            "familiar with",
            "prior knowledge",
            "prior background",
            "applicants should have",
            "have taken at least one",
            "course in",
            "certificate course",
            "related areas",
            "subjects",
        )
        snippets = [
            self._find_snippet(lines, lambda line, keyword=keyword: keyword in line)
            for keyword in context_keywords
        ]
        context_text = " ".join(snippet for snippet in snippets if snippet)
        if academic_requirement:
            context_text = f"{context_text} {academic_requirement}".strip()
        if not context_text:
            return []

        found_keywords: list[str] = []
        for label, pattern in self._PREREQUISITE_PATTERNS:
            if pattern.search(context_text):
                found_keywords.append(label)
        return found_keywords

    def _extract_foundation_mentions(
        self,
        lines: list[str],
        *,
        prerequisite_keywords: list[str],
    ) -> dict[str, bool]:
        text = " ".join(lines)
        prerequisite_text = " ".join(prerequisite_keywords)
        combined = f"{text} {prerequisite_text}".strip()
        mentions: dict[str, bool] = {}
        for key, pattern in self._FOUNDATION_MENTION_PATTERNS.items():
            mentions[key] = bool(pattern.search(combined))
        return mentions

    def _find_snippet(
        self,
        lines: list[str],
        predicate: Callable[[str], bool],
    ) -> str | None:
        for index, line in enumerate(lines):
            lowered = line.lower()
            if predicate(lowered):
                return self._snippet_with_context(lines, index)
        return None

    def _snippet_with_context(self, lines: list[str], index: int) -> str:
        line = lines[index]
        if (
            self._looks_like_header(line)
            and index + 1 < len(lines)
            and not self._looks_like_header(lines[index + 1])
        ):
            parts = [line]
            for look_ahead_index in range(index + 1, min(index + 3, len(lines))):
                if self._looks_like_header(lines[look_ahead_index]):
                    break
                parts.append(lines[look_ahead_index])
            return self._normalize_text(" ".join(parts))
        return line

    def _is_tuition_line(self, line: str) -> bool:
        if any(keyword in line for keyword in self._TUITION_REJECTION_KEYWORDS):
            return False
        if any(keyword in line for keyword in self._TUITION_LABELS):
            return True
        return bool(self._CURRENCY_PATTERN.search(line)) and any(
            keyword in line
            for keyword in (
                "fee",
                "fees",
                "tuition",
                "programme",
                "program",
                "local",
                "non-local",
                "non local",
                "students",
            )
        )

    def _is_english_requirement_line(self, line: str) -> bool:
        if any(keyword in line for keyword in self._OPENING_KEYWORDS):
            return False

        if any(keyword in line for keyword in self._ENGLISH_REQUIREMENT_LABELS):
            return True

        if any(self._contains_token(line, keyword) for keyword in self._ENGLISH_TEST_KEYWORDS):
            return True

        has_english_context = "english" in line or "language" in line or "proficiency" in line
        has_requirement_signal = any(
            keyword in line
            for keyword in ("requirement", "requirements", "medium of instruction", "taught in english", "exempt")
        )
        if not (has_english_context and has_requirement_signal):
            return False
        if "medium of instruction" in line and not any(
            keyword in line
            for keyword in ("requirement", "requirements", "exempt", "waiv", "proof", "satisfy", "accepted")
        ):
            return False
        return True

    def _is_academic_requirement_line(self, line: str) -> bool:
        if self._looks_like_english_requirement_content(line):
            return False
        if any(keyword in line for keyword in self._ACADEMIC_REQUIREMENT_LABELS):
            return True

        has_degree_signal = self._has_academic_requirement_content(line)
        has_admissions_context = any(
            keyword in line
            for keyword in ("applicant", "admission", "eligible", "require", "must hold", "should hold", "should have")
        )
        return has_degree_signal and has_admissions_context

    def _strip_label(self, text: str, labels: tuple[str, ...]) -> str:
        if ":" in text:
            prefix, suffix = text.split(":", 1)
            if (
                len(prefix) <= 80
                and "http" not in prefix.lower()
                and any(label in prefix.lower() for label in labels)
            ):
                cleaned = self._normalize_text(suffix)
                if cleaned:
                    return cleaned

        lowered = text.lower()
        for label in labels:
            if lowered.startswith(label):
                cleaned = self._normalize_text(text[len(label) :].lstrip(" -:"))
                cleaned = re.sub(r"^(?:on|is)\s+", "", cleaned, flags=re.IGNORECASE)
                if cleaned:
                    return cleaned
        return self._normalize_text(text)

    def _extract_date(self, text: str) -> str | None:
        for pattern in self._DATE_PATTERNS:
            match = pattern.search(text)
            if match:
                return self._normalize_text(match.group(0))
        return None

    def _is_deadline_candidate(
        self,
        lines: list[str],
        index: int,
        lowered_line: str,
        lowered_snippet: str,
    ) -> bool:
        if any(keyword in lowered_line for keyword in self._DEADLINE_LABELS):
            return True
        if "round" in lowered_line and self._extract_date(lowered_line):
            return True
        if not self._extract_date(lowered_snippet):
            return False

        context_window = " ".join(lines[max(0, index - 2) : index + 1]).lower()
        return any(
            keyword in context_window
            for keyword in (
                "schedule",
                "deadline",
                "deadlines",
                "closing date",
                "important dates",
                "key dates",
                "timeline",
                "round",
            )
        )

    def _is_opening_sentence(self, text: str) -> bool:
        return any(keyword in text for keyword in self._OPENING_KEYWORDS)

    def _is_deadline_noise(self, text: str) -> bool:
        if any(keyword in text for keyword in self._DEADLINE_REJECTION_KEYWORDS):
            return True
        return any(keyword in text for keyword in self._DEADLINE_EVENT_NOISE_KEYWORDS) and bool(
            self._extract_date(text)
        )

    def _is_deadline_value(self, text: str) -> bool:
        lowered = text.lower()
        if self._is_opening_sentence(lowered):
            return False
        if self._is_deadline_noise(lowered):
            return False
        if lowered.endswith("?") or "?" in lowered:
            return False
        if any(
            lowered.startswith(prefix)
            for prefix in ("how do i apply", "when are the application deadlines")
        ):
            return False
        if "http" in lowered and not self._extract_date(text):
            return False
        return True

    def _extract_tuition_value(self, text: str) -> str | None:
        if not text:
            return None

        local_non_local_match = re.search(
            r"(local students?:[^.]{0,220}?hk\$\s*\d[\d,]*(?:\.\d{2})?[^.]{0,220}?"
            r"non[- ]local students?:[^.]{0,220}?hk\$\s*\d[\d,]*(?:\.\d{2})?)",
            text,
            flags=re.IGNORECASE,
        )
        if local_non_local_match:
            return self._clean_extracted_text(local_non_local_match.group(1))

        if self._CURRENCY_PATTERN.search(text):
            return text
        return None

    def _extract_relevant_sentence(
        self,
        text: str,
        predicate: Callable[[str], bool],
    ) -> str | None:
        if not text:
            return None

        sentences = re.split(r"(?<=[.!?])\s+", text)
        for sentence in sentences:
            normalized = self._clean_extracted_text(sentence)
            if normalized and predicate(normalized.lower()):
                return normalized

        cleaned = self._clean_extracted_text(text)
        if cleaned and predicate(cleaned.lower()):
            return cleaned
        return None

    def _clean_extracted_text(self, text: str) -> str:
        cleaned = self._normalize_text(text)
        cleaned = re.sub(r"^[\s\-:;,.()]+", "", cleaned)
        cleaned = re.sub(r"^[sS]\s+(?=[A-Z])", "", cleaned)
        cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
        return cleaned.strip()

    def _clean_program_name(self, value: str) -> str:
        cleaned = self._normalize_text(value)
        cleaned = re.split(r"\b(?:admissions?|overview|programme|program)\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
        return cleaned.rstrip(" -|:")

    def _looks_like_header(self, line: str) -> bool:
        lowered = line.lower().rstrip(":")
        if line.endswith(":") or lowered in self._HEADER_LABELS:
            return True

        if len(line.split()) > 6:
            return False

        if ":" in line or self._extract_date(line) or self._CURRENCY_PATTERN.search(line):
            return False

        if any(character in line for character in ".!?"):
            return False

        return any(keyword in lowered for keyword in self._HEADER_CONTEXT_KEYWORDS)

    @staticmethod
    def _has_academic_requirement_content(text: str) -> bool:
        return any(
            keyword in text
            for keyword in (
                "bachelor",
                "degree",
                "gpa",
                "honours",
                "honors",
                "upper second",
                "recognized university",
                "equivalent qualification",
                "course in",
                "courses in",
                "certificate course",
                "subjects",
                "related areas",
                "calculus",
                "algebra",
                "programming",
                "statistics",
            )
        )

    def _tuition_candidate_score(self, text: str | None) -> int:
        if not text:
            return 0

        lowered = text.lower()
        if any(keyword in lowered for keyword in self._TUITION_REJECTION_KEYWORDS):
            return 0
        if self._looks_like_header(text):
            return 0
        if "announced every year" in lowered:
            return 0
        if "for information" in lowered and not self._CURRENCY_PATTERN.search(text):
            return 0

        currency_matches = list(self._CURRENCY_PATTERN.finditer(text))
        if not currency_matches:
            return 0
        numeric_amounts = [
            self._parse_amount(match.group(0))
            for match in currency_matches
        ]
        numeric_amounts = [amount for amount in numeric_amounts if amount is not None]
        if not numeric_amounts:
            return 0
        max_amount = max(numeric_amounts)
        if max_amount < 10_000:
            return 0

        if not any(
            keyword in lowered
            for keyword in (
                "tuition",
                "fee",
                "fees",
                "instalment",
                "installment",
                "payable",
                "programme",
                "program",
                "local",
                "non-local",
                "non local",
                "students",
            )
        ):
            return 0

        score = 0
        score += 10
        if "tuition fee" in lowered or "tuition fees" in lowered:
            score += 5
        if "programme fee" in lowered or "program fee" in lowered:
            score += 5
        if "local students" in lowered or "non-local students" in lowered or "non local students" in lowered:
            score += 5
        if "students admitted" in lowered or "payable" in lowered or "instalment" in lowered or "installment" in lowered:
            score += 2
        if max_amount >= 100_000:
            score += 8
        if max_amount >= 300_000:
            score += 6
        return score + len(text)

    def _english_requirement_candidate_score(self, text: str | None) -> int:
        if not text:
            return 0

        lowered = text.lower()
        if self._is_question_only_text(lowered):
            return 0
        if self._looks_like_header(text):
            return 0
        if not self._is_english_requirement_line(lowered):
            return 0
        if "medium of instruction" in lowered and not any(
            keyword in lowered
            for keyword in ("exempt", "waiv", "proof", "satisfy", "accepted", "requirement")
        ):
            return 0

        score = 0
        if any(self._contains_token(lowered, keyword) for keyword in self._ENGLISH_TEST_KEYWORDS):
            score += 10
        if any(keyword in lowered for keyword in self._ENGLISH_REQUIREMENT_SIGNAL_KEYWORDS):
            score += 8
        if any(keyword in lowered for keyword in self._MEDIUM_OF_INSTRUCTION_KEYWORDS):
            score += 2
        if len(text.split()) < 5 and score < 10:
            return 0
        return score + len(text)

    def _academic_requirement_candidate_score(self, text: str | None) -> int:
        if not text:
            return 0

        lowered = text.lower()
        if self._looks_like_english_requirement_content(lowered):
            return 0
        if not self._has_academic_requirement_content(lowered):
            return 0

        score = 0
        if "bachelor" in lowered or "degree" in lowered:
            score += 8
        if any(
            keyword in lowered
            for keyword in (
                "have taken at least one",
                "course in",
                "courses in",
                "certificate course",
                "subjects",
                "related areas",
                "calculus",
                "algebra",
                "programming",
                "statistics",
            )
        ):
            score += 10
        if "equivalent qualification" in lowered:
            score += 4
        if any(keyword in lowered for keyword in ("applicants", "applicant", "candidates", "must hold", "shall hold", "should hold", "should have")):
            score += 4
        return score + len(text)

    def _looks_like_english_requirement_content(self, text: str) -> bool:
        if any(self._contains_token(text, keyword) for keyword in self._ENGLISH_TEST_KEYWORDS):
            return True
        if any(keyword in text for keyword in self._ENGLISH_REQUIREMENT_SIGNAL_KEYWORDS):
            return True
        if any(keyword in text for keyword in self._MEDIUM_OF_INSTRUCTION_KEYWORDS) and any(
            keyword in text for keyword in ("english", "language", "requirement", "satisfy", "exempt", "waiv")
        ):
            return True
        return False

    def _is_question_only_text(self, text: str) -> bool:
        if not text:
            return False
        if "?" not in text:
            return False
        if any(self._contains_token(text, keyword) for keyword in self._ENGLISH_TEST_KEYWORDS) and re.search(
            r"\b(?:ielts|toefl|pte|duolingo)\b\s*\d",
            text,
        ):
            return False
        if any(
            keyword in text
            for keyword in ("expected to satisfy", "must satisfy", "required to satisfy", "shall satisfy", "exempt", "waiv")
        ):
            return False
        return any(text.startswith(keyword) for keyword in self._QUESTION_PROMPT_KEYWORDS) or text.endswith("?")

    @staticmethod
    def _best_candidate_text(candidates: list[tuple[int, str]]) -> str | None:
        if not candidates:
            return None

        candidates.sort(key=lambda item: (-item[0], -len(item[1]), item[1]))
        return candidates[0][1]

    @staticmethod
    def _contains_token(text: str, keyword: str) -> bool:
        return bool(re.search(rf"\b{re.escape(keyword)}\b", text, flags=re.IGNORECASE))

    @staticmethod
    def _trim_requirement_lead_in(text: str) -> str:
        if not text:
            return text

        matches = [
            match.start()
            for match in re.finditer(
                r"\b(?:Applicants?|Candidates?)\b",
                text,
                flags=re.IGNORECASE,
            )
        ]
        if not matches:
            return text

        first_match = matches[0]
        if first_match == 0:
            return text
        return text[first_match:].strip()

    @staticmethod
    def _normalize_text(text: str) -> str:
        replacements = {
            "\u00a0": " ",
            "\u2018": "'",
            "\u2019": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u2013": "-",
            "\u2014": "-",
            "聽": " ",
            "鈥n": " ",
            "鈥?": " ",
            "鉁昞n": " ",
            "芦": " ",
            "禄": " ",
            "漏": "©",
        }
        normalized = text
        for original, replacement in replacements.items():
            normalized = normalized.replace(original, replacement)
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _parse_amount(text: str) -> int | None:
        match = re.search(r"\d[\d,]*(?:\.\d{2})?", text)
        if match is None:
            return None
        return int(float(match.group(0).replace(",", "")))
