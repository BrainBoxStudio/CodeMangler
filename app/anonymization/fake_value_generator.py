"""Deterministic fake-value generation.

The "same original always maps to the same fake value" guarantee (CLAUDE.md
section 4) comes from a per-session cache keyed by (category, original), not
from reseeding Faker per call — Faker (where used) is only consulted on a
cache miss, exactly once per unique original value.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable

from faker import Faker

_TEMPLATE_FORMATTERS: dict[str, Callable[[int], str]] = {
    "email": lambda n: f"user{n:03d}@example.com",
    "hostname": lambda n: f"host{n:03d}.local",
    "ip_address": lambda n: f"10.0.0.{n}",
    "url": lambda n: f"https://fake-service{n:03d}.local",
    "file_path": lambda n: f"/fake/path{n:03d}",
    "aws_access_key": lambda n: f"FAKE_AWS_KEY_{n:03d}",
    "github_token": lambda n: f"FAKE_GITHUB_TOKEN_{n:03d}",
    "gitlab_token": lambda n: f"FAKE_GITLAB_TOKEN_{n:03d}",
    "slack_token": lambda n: f"FAKE_SLACK_TOKEN_{n:03d}",
    "google_api_key": lambda n: f"FAKE_GOOGLE_API_KEY_{n:03d}",
    "jwt": lambda n: f"FAKE_JWT_TOKEN_{n:03d}",
    "oauth_bearer_token": lambda n: f"FAKE_OAUTH_TOKEN_{n:03d}",
    "ssh_public_key": lambda n: f"ssh-rsa FAKE_SSH_KEY_{n:03d}",
    "private_key_block": lambda n: (
        f"-----BEGIN PRIVATE KEY-----\nFAKE_KEY_{n:03d}\n-----END PRIVATE KEY-----"
    ),
    "db_connection_string": lambda n: (
        f"postgres://user{n:03d}:fake_password_{n:03d}@host{n:03d}.local:5432/db{n:03d}"
    ),
    "azure_connection_string": lambda n: (
        f"DefaultEndpointsProtocol=https;AccountName=fakeacct{n:03d};"
        f"AccountKey=FAKE_AZURE_KEY_{n:03d}=="
    ),
    "generic_password_assignment": lambda n: f"fake_password_{n:03d}",
    "generic_secret_assignment": lambda n: f"fake_secret_{n:03d}",
    "high_entropy_string": lambda n: f"FAKE_SECRET_{n:03d}",
    "org": lambda n: f"Org{n:03d}",
    # Code-identifier categories (CLAUDE.md section 5/6) — short prefixes
    # matching the spec's own example (`Cls001`), produced by app/code/.
    "variable": lambda n: f"var{n:03d}",
    "function": lambda n: f"fn{n:03d}",
    "method": lambda n: f"fn{n:03d}",
    "class": lambda n: f"Cls{n:03d}",
    "struct": lambda n: f"Struct{n:03d}",
    "interface": lambda n: f"Iface{n:03d}",
    "enum": lambda n: f"Enum{n:03d}",
    "namespace": lambda n: f"Ns{n:03d}",
    "constant": lambda n: f"CONST{n:03d}",
}


class FakeValueGenerator:
    def __init__(self, faker: Faker | None = None) -> None:
        self._faker = faker or Faker()
        self._cache: dict[tuple[str, str], str] = {}
        self._issued: set[str] = set()
        self._counters: defaultdict[str, int] = defaultdict(int)

    def generate(self, category: str, original: str) -> str:
        key = (category, original)
        if key in self._cache:
            return self._cache[key]
        fake_value = self._make_unique(category)
        self._cache[key] = fake_value
        self._issued.add(fake_value)
        return fake_value

    def force(self, category: str, original: str, value: str) -> None:
        """Override the cached fake for (category, original) with an exact value.

        Used by app/code/identifier_extractor.py to apply CLAUDE.md section 9's
        conflict-suffixing (`make_con` -> `make_con_001`) when a generated fake
        identifier collides with a real name already present in the scanned file
        — a collision `generate()` alone can't see, since it only tracks fakes
        it has issued itself, not pre-existing identifiers in the source.
        """
        self._cache[(category, original)] = value
        self._issued.add(value)

    def _make_unique(self, category: str) -> str:
        candidate = self._next_candidate(category)
        # Same collision-avoidance principle as CLAUDE.md section 9's
        # identifier-conflict suffixing: never issue a fake value twice.
        while candidate in self._issued:
            candidate = self._next_candidate(category)
        return candidate

    def _next_candidate(self, category: str) -> str:
        self._counters[category] += 1
        n = self._counters[category]
        formatter = _TEMPLATE_FORMATTERS.get(category)
        if formatter:
            return formatter(n)
        if category == "person_name":
            return self._faker.name()
        if category == "username":
            return self._faker.user_name()
        return f"{category.capitalize()}{n:03d}"
