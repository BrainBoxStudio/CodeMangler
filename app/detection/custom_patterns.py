"""User-configurable detection: arbitrary regex patterns plus literal known
terms (org/project/internal server names) that can't be regex-detected and
must be supplied by the user (see Settings.known_terms in app/config.py).
"""
from __future__ import annotations

import re

from app.config import Settings
from app.detection.findings import Finding


def detect_custom_patterns(text: str, settings: Settings) -> list[Finding]:
    findings: list[Finding] = []
    for name, pattern in settings.custom_patterns.items():
        for match in re.finditer(pattern, text):
            findings.append(
                Finding(
                    start=match.start(),
                    end=match.end(),
                    category=name,
                    value=match.group(0),
                    confidence=0.9,
                    detector="custom",
                )
            )
    for term, category in settings.known_terms.items():
        if not term:
            continue
        for match in re.finditer(re.escape(term), text):
            findings.append(
                Finding(
                    start=match.start(),
                    end=match.end(),
                    category=category,
                    value=term,
                    confidence=0.95,
                    detector="custom",
                )
            )
    return findings
