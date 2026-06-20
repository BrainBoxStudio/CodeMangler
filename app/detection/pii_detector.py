"""PII detection: always-on regex patterns plus an optional NLP layer
(Microsoft Presidio) for free-text personal/organization name recognition.

Presidio is lazily imported so the application works without it installed —
the "must work without LLM" philosophy (CLAUDE.md section 12) extends to this
optional, heavier NLP dependency too (see claude.md section 21).
"""
from __future__ import annotations

import logging
import re

from app.config import Settings
from app.detection.findings import Finding

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+\b")
_URL_RE = re.compile(r"\bhttps?://[^\s'\"<>]+")
_IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
_PHONE_RE = re.compile(r"\b(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_DOMAIN_RE = re.compile(r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.){2,}[a-zA-Z]{2,}\b")
_HOSTNAME_KEYWORDS = {"internal", "corp", "prod", "dev", "stage", "staging", "test", "local", "lan"}
_WINDOWS_PATH_RE = re.compile(r"\b[A-Za-z]:\\(?:[^<>:\"|?*\r\n\\]+\\)*[^<>:\"|?*\r\n\\]+")
_UNIX_PATH_RE = re.compile(r"(?<![\w/])/(?:home|Users|var|etc|opt|root)/[\w./-]+")


def _regex_findings(text: str) -> list[Finding]:
    findings: list[Finding] = []
    for match in _EMAIL_RE.finditer(text):
        findings.append(Finding(*match.span(), "email", match.group(0), 0.85, "regex"))
    for match in _URL_RE.finditer(text):
        findings.append(Finding(*match.span(), "url", match.group(0), 0.8, "regex"))
    for match in _IPV4_RE.finditer(text):
        findings.append(Finding(*match.span(), "ip_address", match.group(0), 0.8, "regex"))
    for match in _PHONE_RE.finditer(text):
        findings.append(Finding(*match.span(), "phone", match.group(0), 0.55, "regex"))
    for match in _DOMAIN_RE.finditer(text):
        labels = match.group(0).lower().split(".")
        if any(label in _HOSTNAME_KEYWORDS for label in labels):
            findings.append(Finding(*match.span(), "hostname", match.group(0), 0.6, "regex"))
    for match in _WINDOWS_PATH_RE.finditer(text):
        findings.append(Finding(*match.span(), "file_path", match.group(0), 0.7, "regex"))
    for match in _UNIX_PATH_RE.finditer(text):
        findings.append(Finding(*match.span(), "file_path", match.group(0), 0.7, "regex"))
    return findings


_presidio_analyzer = None
_presidio_unavailable = False


def _get_presidio_analyzer():
    global _presidio_analyzer, _presidio_unavailable
    if _presidio_unavailable:
        return None
    if _presidio_analyzer is None:
        try:
            from presidio_analyzer import AnalyzerEngine
        except ImportError:
            _presidio_unavailable = True
            logger.warning(
                'presidio-analyzer not installed; skipping NLP-based PII detection '
                '(install with `pip install -e ".[pii]"` and download a spaCy model)'
            )
            return None
        try:
            _presidio_analyzer = AnalyzerEngine()
        except Exception:
            _presidio_unavailable = True
            logger.warning(
                "presidio-analyzer failed to initialize (likely missing spaCy model); "
                "skipping NLP-based PII detection"
            )
            return None
    return _presidio_analyzer


_PRESIDIO_CATEGORY_MAP = {
    "PERSON": "person_name",
    "ORGANIZATION": "org",
}


def _presidio_findings(text: str) -> list[Finding]:
    analyzer = _get_presidio_analyzer()
    if analyzer is None:
        return []
    findings: list[Finding] = []
    for result in analyzer.analyze(text=text, language="en", entities=list(_PRESIDIO_CATEGORY_MAP)):
        category = _PRESIDIO_CATEGORY_MAP.get(result.entity_type, result.entity_type.lower())
        findings.append(
            Finding(
                start=result.start,
                end=result.end,
                category=category,
                value=text[result.start : result.end],
                confidence=result.score,
                detector="presidio",
            )
        )
    return findings


def detect_pii(text: str, settings: Settings) -> list[Finding]:
    findings = _regex_findings(text)
    if settings.enable_pii_nlp:
        findings.extend(_presidio_findings(text))
    return findings
