import pytest

from app.anonymization.code_anonymizer import collect_findings
from app.anonymization.fake_value_generator import FakeValueGenerator
from app.config import Settings
from app.detection.entropy_detector import detect_high_entropy_strings
from app.detection.findings import Finding, merge_findings
from app.detection.pii_detector import detect_pii
from app.detection.secret_detector import detect_secrets_regex


@pytest.mark.parametrize(
    "text,category,expected_value",
    [
        ("key = AKIAABCDEFGHIJKLMNOP", "aws_access_key", "AKIAABCDEFGHIJKLMNOP"),
        (
            "token = ghp_1234567890abcdef1234567890abcdef1234",
            "github_token",
            "ghp_1234567890abcdef1234567890abcdef1234",
        ),
        (
            "Authorization: Bearer abcDEF123456token",
            "oauth_bearer_token",
            "abcDEF123456token",
        ),
        (
            "db_url = postgres://user:pass@db.example.com:5432/app",
            "db_connection_string",
            "postgres://user:pass@db.example.com:5432/app",
        ),
        ("password = supersecret1", "generic_password_assignment", "supersecret1"),
    ],
)
def test_regex_secret_detection(text, category, expected_value):
    findings = detect_secrets_regex(text)
    matches = [f for f in findings if f.category == category]
    assert matches, f"expected category {category!r} in {findings!r}"
    assert matches[0].value == expected_value


def test_private_key_block_detected_as_single_span():
    text = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIBVQIBADANBgkqhkiG9w0BAQEFAASCAT8wggE7AgEAAkEA\n"
        "-----END RSA PRIVATE KEY-----\n"
    )
    findings = detect_secrets_regex(text)
    matches = [f for f in findings if f.category == "private_key_block"]
    assert len(matches) == 1
    assert matches[0].value.startswith("-----BEGIN")
    assert matches[0].value.endswith("-----END RSA PRIVATE KEY-----")


@pytest.mark.parametrize(
    "text,category,expected_value",
    [
        ("contact john.doe@company.com for access", "email", "john.doe@company.com"),
        ("see https://example.com/path?x=1 for docs", "url", "https://example.com/path?x=1"),
        ("server at 192.168.10.25 is down", "ip_address", "192.168.10.25"),
        (
            "host is prod-db.internal.company.com today",
            "hostname",
            "prod-db.internal.company.com",
        ),
    ],
)
def test_regex_pii_detection(text, category, expected_value):
    settings = Settings(enable_pii_nlp=False)
    findings = detect_pii(text, settings)
    matches = [f for f in findings if f.category == category]
    assert matches, f"expected category {category!r} in {findings!r}"
    assert matches[0].value == expected_value


def test_entropy_detector_flags_unrecognized_high_entropy_token():
    text = 'config_value = "Zk9pQ2x3WmJ2dE1hUjdYbnE4S2pMcFI1"'
    findings = detect_high_entropy_strings(text, threshold=4.0)
    assert any(f.value == "Zk9pQ2x3WmJ2dE1hUjdYbnE4S2pMcFI1" for f in findings)


def test_entropy_detector_ignores_low_entropy_token():
    text = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    findings = detect_high_entropy_strings(text, threshold=4.0)
    assert findings == []


def test_merge_findings_prefers_specific_regex_over_entropy_on_same_span():
    value = "AKIAABCDEFGHIJKLMNOP"
    findings = [
        Finding(start=4, end=4 + len(value), category="aws_access_key", value=value, confidence=0.95, detector="regex"),
        Finding(start=4, end=4 + len(value), category="high_entropy_string", value=value, confidence=0.7, detector="entropy"),
    ]
    merged = merge_findings(findings)
    assert len(merged) == 1
    assert merged[0].detector == "regex"
    assert merged[0].category == "aws_access_key"


def test_merge_findings_prefers_larger_span_over_nested_literal_term():
    # A known_term substring nested inside a fully-matched URL should not
    # suppress the (more complete) URL finding.
    url = "https://prod.payment.mycompany.internal/api"
    nested_start = url.index("mycompany")
    findings = [
        Finding(start=0, end=len(url), category="url", value=url, confidence=0.8, detector="regex"),
        Finding(
            start=nested_start,
            end=nested_start + len("mycompany"),
            category="org",
            value="mycompany",
            confidence=0.95,
            detector="custom",
        ),
    ]
    merged = merge_findings(findings)
    assert len(merged) == 1
    assert merged[0].category == "url"


def test_collect_findings_matches_section_18_example(sample_python_source):
    settings = Settings(enable_pii_nlp=False)
    findings = collect_findings(sample_python_source, settings)
    categories = {f.category for f in findings}
    assert "url" in categories
    assert "github_token" in categories


def test_fake_value_generator_is_deterministic_within_session():
    generator = FakeValueGenerator()
    first = generator.generate("email", "john.doe@company.com")
    second = generator.generate("email", "john.doe@company.com")
    assert first == second


def test_fake_value_generator_never_issues_duplicate_fakes():
    generator = FakeValueGenerator()
    fakes = {generator.generate("org", f"Company{i}") for i in range(50)}
    assert len(fakes) == 50
