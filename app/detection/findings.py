"""Shared Finding representation and span-merge/de-dup logic.

Every detector (regex, detect-secrets/entropy, presidio, custom) emits Finding
spans independently. Detectors can disagree about exact boundaries for the same
underlying value (e.g. a regex AWS-key match overlapping a high-entropy-string
match on the same token), so findings must be reconciled into a single
non-overlapping list before any replacement happens.
"""
from __future__ import annotations

from dataclasses import dataclass

# Higher number wins when spans overlap. Deterministic, specific detectors
# outrank generic entropy scanning, which outranks free-text NLP guesses
# (CLAUDE.md section 19: "Regex and AST rules must run first").
DETECTOR_PRIORITY: dict[str, int] = {
    "tree-sitter": 5,
    "custom": 4,
    "regex": 4,
    "detect-secrets": 3,
    "entropy": 2,
    "presidio": 1,
}


@dataclass(frozen=True)
class Finding:
    start: int
    end: int
    category: str
    value: str
    confidence: float
    detector: str

    @property
    def priority(self) -> tuple[int, int, float]:
        # Within the same detector tier, prefer the larger span: a full
        # hostname/URL match should win over a short literal term nested
        # inside it, so the complete sensitive value gets redacted rather
        # than leaving a partial, still-identifying remainder exposed.
        return (DETECTOR_PRIORITY.get(self.detector, 0), self.end - self.start, self.confidence)


def _overlaps(a: Finding, b: Finding) -> bool:
    return a.start < b.end and b.start < a.end


def merge_findings(findings: list[Finding]) -> list[Finding]:
    """Resolve overlapping spans, keeping the highest-priority finding per span."""
    ordered = sorted(findings, key=lambda f: f.start)
    resolved: list[Finding] = []
    for finding in ordered:
        overlapping_indices = [i for i, kept in enumerate(resolved) if _overlaps(kept, finding)]
        if not overlapping_indices:
            resolved.append(finding)
            continue
        max_kept_priority = max(resolved[i].priority for i in overlapping_indices)
        if finding.priority > max_kept_priority:
            for index in sorted(overlapping_indices, reverse=True):
                del resolved[index]
            resolved.append(finding)
    resolved.sort(key=lambda f: f.start)
    return resolved
