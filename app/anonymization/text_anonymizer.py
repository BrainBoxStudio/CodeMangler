"""Applies merged Findings to a text blob: splices in fake values and emits
position-tracked TextChange records consumed by mapping.map_writer.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.anonymization.fake_value_generator import FakeValueGenerator
from app.detection.findings import Finding

# Coarse classification for the mapping schema's `type` field (CLAUDE.md
# section 7). Categories not listed here (e.g. a user's own known_terms
# category, or a custom pattern name) pass through unchanged as `type`.
_CATEGORY_TO_TYPE: dict[str, str] = {
    "email": "pii",
    "phone": "pii",
    "person_name": "pii",
    "username": "pii",
    "ip_address": "pii",
    "url": "url",
    "hostname": "hostname",
    "file_path": "path",
    "org": "org",
    "aws_access_key": "secret",
    "github_token": "secret",
    "gitlab_token": "secret",
    "slack_token": "secret",
    "google_api_key": "secret",
    "jwt": "secret",
    "oauth_bearer_token": "secret",
    "ssh_public_key": "secret",
    "private_key_block": "secret",
    "db_connection_string": "secret",
    "azure_connection_string": "secret",
    "generic_password_assignment": "secret",
    "generic_secret_assignment": "secret",
    "high_entropy_string": "secret",
}


@dataclass
class TextChange:
    type: str
    category: str
    original: str
    replacement: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    confidence: float
    detector: str


def _offset_to_line_col(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    last_newline = text.rfind("\n", 0, offset)
    col = offset - last_newline
    return line, col


def apply_findings(
    text: str, findings: list[Finding], generator: FakeValueGenerator
) -> tuple[str, list[TextChange]]:
    # Positions are recorded against the *output* (sanitized) text, not the
    # input: restore_engine's position-anchored pass runs against whatever
    # sanitized file it's handed back, so that's the coordinate space that
    # has to match.
    ordered = sorted(findings, key=lambda f: f.start)
    pieces: list[str] = []
    pending: list[tuple[Finding, str, int, int]] = []
    cursor = 0
    output_offset = 0
    for finding in ordered:
        if finding.start < cursor:
            continue  # defensive: merge_findings should already be non-overlapping
        prefix = text[cursor : finding.start]
        pieces.append(prefix)
        output_offset += len(prefix)
        replacement = generator.generate(finding.category, finding.value)
        output_start = output_offset
        pieces.append(replacement)
        output_offset += len(replacement)
        pending.append((finding, replacement, output_start, output_offset))
        cursor = finding.end
    pieces.append(text[cursor:])
    output_text = "".join(pieces)

    changes: list[TextChange] = []
    for finding, replacement, output_start, output_end in pending:
        start_line, start_col = _offset_to_line_col(output_text, output_start)
        end_line, end_col = _offset_to_line_col(output_text, output_end)
        changes.append(
            TextChange(
                type=_CATEGORY_TO_TYPE.get(finding.category, finding.category),
                category=finding.category,
                original=finding.value,
                replacement=replacement,
                start_line=start_line,
                start_col=start_col,
                end_line=end_line,
                end_col=end_col,
                confidence=finding.confidence,
                detector=finding.detector,
            )
        )
    return output_text, changes
