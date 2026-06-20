"""Entropy-based secret detection: catches high-entropy tokens that don't match
any known secret pattern (e.g. an unrecognized API key format).

Candidate-token extraction is ours; the actual Shannon-entropy math is borrowed
from detect-secrets (its plugin classes expose `calculate_shannon_entropy`
directly, independent of its own line/baseline scanning pipeline).
"""
from __future__ import annotations

import re

from detect_secrets.plugins.high_entropy_strings import Base64HighEntropyString

from app.detection.findings import Finding

_CANDIDATE_TOKEN = re.compile(r"\b[A-Za-z0-9+/_=-]{20,}\b")


def detect_high_entropy_strings(text: str, threshold: float = 4.0) -> list[Finding]:
    scorer = Base64HighEntropyString(limit=threshold)
    findings: list[Finding] = []
    for match in _CANDIDATE_TOKEN.finditer(text):
        token = match.group(0)
        entropy = scorer.calculate_shannon_entropy(token)
        if entropy < threshold:
            continue
        # Normalize entropy (roughly 0-6 bits/char for base64-ish charsets) into
        # a 0-1 confidence band, capped so entropy alone never outranks a
        # specific regex/detect-secrets match on the same span.
        confidence = min(0.3 + (entropy - threshold) * 0.1, 0.75)
        findings.append(
            Finding(
                start=match.start(),
                end=match.end(),
                category="high_entropy_string",
                value=token,
                confidence=confidence,
                detector="entropy",
            )
        )
    return findings
