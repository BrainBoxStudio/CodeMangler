"""Runtime configuration for CodeMangler."""
from __future__ import annotations

from pydantic import BaseModel, Field

DEFAULT_IGNORED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "venv",
        ".venv",
        "__pycache__",
        "dist",
        "build",
        "target",
        "bin",
        "obj",
        ".idea",
        ".vscode",
    }
)

DEFAULT_IGNORED_FILE_GLOBS: tuple[str, ...] = (
    "*.exe",
    "*.dll",
    "*.so",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.7z",
    "*.class",
    "*.jar",
)


class MangleOptions(BaseModel):
    """Per-run toggles for the Mangler UI's checklist (and CLI flags).

    Two top-level groups, each with sub-toggles for one detection/rename
    category. Unchecking a sub-item disables exactly that category without
    touching its siblings — `code_anonymizer.collect_findings` checks these
    before running each detector/identifier-category pass.
    """

    sensitive_info: bool = True
    sensitive_secrets: bool = True
    sensitive_pii: bool = True
    sensitive_network: bool = True       # IPs, hostnames, URLs
    sensitive_paths: bool = True
    sensitive_org_project: bool = True   # known_terms

    code_identifiers: bool = True
    code_variables: bool = True
    code_functions: bool = True
    code_classes: bool = True
    code_interfaces: bool = True
    code_enums: bool = True
    code_namespaces: bool = True
    code_constants: bool = True


class Settings(BaseModel):
    """User-tunable detection/anonymization settings.

    Confidence threshold below which a finding is dropped rather than replaced,
    plus toggles for the optional (heavier) detection layers.
    """

    ignored_dirs: frozenset[str] = Field(default_factory=lambda: DEFAULT_IGNORED_DIRS)
    ignored_file_globs: tuple[str, ...] = DEFAULT_IGNORED_FILE_GLOBS
    # name -> regex pattern, merged into detection.
    custom_patterns: dict[str, str] = Field(default_factory=dict)
    # Literal org/project/server names that can't be regex-detected, e.g.
    # {"MyCompany": "org", "PaymentGatewayService": "project"}.
    known_terms: dict[str, str] = Field(default_factory=dict)
    # Identifier names that must never be renamed even if locally defined,
    # e.g. framework lifecycle methods / external API contract names that
    # tree-sitter's definition-based filtering can't distinguish on its own
    # (CLAUDE.md section 5).
    protected_identifiers: frozenset[str] = Field(default_factory=frozenset)
    enable_pii_nlp: bool = True
    min_confidence: float = 0.5
    entropy_threshold: float = 4.0
    mangle_options: MangleOptions = Field(default_factory=MangleOptions)
    llm_provider: str | None = None
    llm_endpoint: str | None = None


DEFAULT_SETTINGS = Settings()
