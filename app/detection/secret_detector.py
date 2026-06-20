"""Regex-based secret detection.

Explicit, version-stable regexes rather than detect-secrets' line-oriented
plugin API (which is built around its own scan/baseline pipeline, not ad hoc
string scanning) — see entropy_detector.py for the one piece of detect-secrets
reused directly (Shannon entropy calculation).
"""
from __future__ import annotations

import re

from app.detection.findings import Finding

_PATTERNS: tuple[tuple[str, re.Pattern[str], float], ...] = (
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), 0.95),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), 0.95),
    ("gitlab_token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"), 0.9),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), 0.9),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), 0.9),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
        0.85,
    ),
    (
        "private_key_block",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----"
        ),
        0.99,
    ),
    (
        "ssh_public_key",
        re.compile(r"\bssh-(?:rsa|ed25519|dss|ecdsa-[a-z0-9-]+) [A-Za-z0-9+/]+=*(?: \S+)?"),
        0.85,
    ),
    (
        "oauth_bearer_token",
        re.compile(r"\bBearer\s+([A-Za-z0-9\-_.]{10,})\b"),
        0.7,
    ),
    (
        "db_connection_string",
        re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s'\"]+"),
        0.9,
    ),
    (
        "azure_connection_string",
        re.compile(r"DefaultEndpointsProtocol=https?;[^\s'\"]*AccountKey=[^\s'\";]+"),
        0.9,
    ),
    (
        "generic_password_assignment",
        re.compile(
            r"(?i)\b(?:password|passwd|pwd)\s*[:=]\s*['\"]?([^\s'\";]{3,})['\"]?"
        ),
        0.6,
    ),
    (
        "generic_secret_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|access[_-]?key|auth[_-]?token)\s*[:=]\s*['\"]?([^\s'\";]{6,})['\"]?"
        ),
        0.6,
    ),
)


def detect_secrets_regex(text: str) -> list[Finding]:
    findings: list[Finding] = []
    for category, pattern, confidence in _PATTERNS:
        for match in pattern.finditer(text):
            group_index = 1 if match.re.groups else 0
            start, end = match.span(group_index)
            findings.append(
                Finding(
                    start=start,
                    end=end,
                    category=category,
                    value=match.group(group_index),
                    confidence=confidence,
                    detector="regex",
                )
            )
    return findings
