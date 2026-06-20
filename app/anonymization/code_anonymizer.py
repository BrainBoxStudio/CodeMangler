"""Per-file anonymization pipeline: run all detectors, merge findings, and
apply replacements. Two independently toggleable groups (Settings.mangle_
options, CLAUDE.md section 21's Mangle Options checklist): sensitive-value
detection (secrets/PII/network/paths/org) and code-identifier renaming
(app/code/, CLAUDE.md sections 5/6/9) — both flow through the same
Finding -> merge_findings -> apply_findings pipeline regardless of source.
"""
from __future__ import annotations

from app.anonymization.fake_value_generator import FakeValueGenerator
from app.anonymization.text_anonymizer import TextChange, apply_findings
from app.code.identifier_extractor import IdentifierCatalog, collect_identifier_findings
from app.config import Settings
from app.detection.custom_patterns import detect_custom_patterns
from app.detection.entropy_detector import detect_high_entropy_strings
from app.detection.findings import Finding, merge_findings
from app.detection.pii_detector import detect_pii
from app.detection.secret_detector import detect_secrets_regex

# Maps a sensitive-value category onto the MangleOptions sub-flag that gates
# it. Categories not listed here (custom user patterns, unrecognised
# known_terms categories) are only gated by the top-level `sensitive_info`
# flag, since their semantics aren't known generically.
_VALUE_CATEGORY_TO_OPTION: dict[str, str] = {
    "aws_access_key": "sensitive_secrets",
    "github_token": "sensitive_secrets",
    "gitlab_token": "sensitive_secrets",
    "slack_token": "sensitive_secrets",
    "google_api_key": "sensitive_secrets",
    "jwt": "sensitive_secrets",
    "private_key_block": "sensitive_secrets",
    "ssh_public_key": "sensitive_secrets",
    "oauth_bearer_token": "sensitive_secrets",
    "db_connection_string": "sensitive_secrets",
    "azure_connection_string": "sensitive_secrets",
    "generic_password_assignment": "sensitive_secrets",
    "generic_secret_assignment": "sensitive_secrets",
    "high_entropy_string": "sensitive_secrets",
    "email": "sensitive_pii",
    "phone": "sensitive_pii",
    "person_name": "sensitive_pii",
    "username": "sensitive_pii",
    "url": "sensitive_network",
    "ip_address": "sensitive_network",
    "hostname": "sensitive_network",
    "file_path": "sensitive_paths",
    "org": "sensitive_org_project",
}


def collect_findings(
    text: str,
    settings: Settings,
    language: str | None = None,
    generator: FakeValueGenerator | None = None,
    catalog: IdentifierCatalog | None = None,
) -> list[Finding]:
    options = settings.mangle_options
    findings: list[Finding] = []

    if options.sensitive_info:
        value_findings: list[Finding] = []
        value_findings += detect_secrets_regex(text)
        value_findings += detect_high_entropy_strings(text, threshold=settings.entropy_threshold)
        value_findings += detect_pii(text, settings)
        value_findings += detect_custom_patterns(text, settings)
        findings += [
            f
            for f in value_findings
            if getattr(options, _VALUE_CATEGORY_TO_OPTION.get(f.category, ""), True)
        ]

    # Identifier renaming needs a language (to pick a grammar) and a
    # generator (to pre-warm conflict-checked fake names) — both are only
    # available when actually sanitizing, not in every collect_findings call.
    # `catalog`, when supplied by a multi-file caller, makes a name eligible
    # if it's defined anywhere in the run, not just in this file.
    if language is not None and generator is not None:
        findings += collect_identifier_findings(text, language, settings, generator, catalog=catalog)

    findings = [f for f in findings if f.confidence >= settings.min_confidence]
    return merge_findings(findings)


def anonymize_text(
    text: str,
    settings: Settings,
    generator: FakeValueGenerator,
    language: str | None = None,
    catalog: IdentifierCatalog | None = None,
) -> tuple[str, list[TextChange]]:
    findings = collect_findings(text, settings, language=language, generator=generator, catalog=catalog)
    return apply_findings(text, findings, generator)
