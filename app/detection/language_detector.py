"""Language detection: extension -> shebang -> heuristic, in that order.

Tree-sitter-based confirmation and optional local-LLM classification (CLAUDE.md
section 2, steps 3 and 5) are Phase 2/3 hooks and are not implemented here —
extension/shebang/heuristic already cover the large majority of real files.
"""
from __future__ import annotations

import re
from pathlib import Path

EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".java": "java",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".sql": "sql",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".xml": "xml",
    ".md": "markdown",
    ".markdown": "markdown",
}

SHEBANG_LANGUAGE_MAP: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"python"), "python"),
    (re.compile(r"\b(bash|sh|zsh)\b"), "shell"),
    (re.compile(r"\bnode\b"), "javascript"),
)

# `.h` is ambiguous between C and C++ (CLAUDE.md only lists `.hpp`/`.hh` as
# unambiguously C++) — a `.h` file containing clear C++-only constructs is
# reclassified so code-identifier renaming (Python/JS/TS/C++/Java only) can
# actually run on it. Plain C `.h` files are unaffected since none of these
# patterns are valid C.
_CPP_ONLY_MARKERS = re.compile(
    r"^\s*(class|namespace|template\s*<)\b|^\s*(public|private|protected)\s*:", re.MULTILINE
)


def _looks_like_cpp_header(content: str) -> bool:
    return bool(_CPP_ONLY_MARKERS.search(content))


_HEURISTICS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^\s*def\s+\w+\s*\(.*\)\s*:", re.MULTILINE), "python"),
    (re.compile(r"^\s*(import|class)\s+[\w.]+.*;\s*$", re.MULTILINE), "java"),
    (re.compile(r"^\s*package\s+\w+", re.MULTILINE), "go"),
    (re.compile(r"\bfn\s+\w+\s*\("), "rust"),
    (re.compile(r"\bfunction\s+\w+\s*\(|=>\s*\{"), "javascript"),
    (re.compile(r"^\s*SELECT\s+.+\s+FROM\s+", re.IGNORECASE | re.MULTILINE), "sql"),
    (re.compile(r"^\s*[\w.-]+:\s+\S", re.MULTILINE), "yaml"),
    (re.compile(r"^#{1,6}\s+\S", re.MULTILINE), "markdown"),
)


def detect_by_extension(relative_path: Path) -> str | None:
    return EXTENSION_LANGUAGE_MAP.get(relative_path.suffix.lower())


def detect_by_shebang(content: str) -> str | None:
    first_line = content.splitlines()[0] if content else ""
    if not first_line.startswith("#!"):
        return None
    for pattern, language in SHEBANG_LANGUAGE_MAP:
        if pattern.search(first_line):
            return language
    return None


def detect_by_heuristic(content: str) -> str:
    stripped = content.strip()
    if not stripped:
        return "text"
    if stripped[0] in "{[" and stripped[-1] in "}]":
        return "json"
    if stripped.startswith("<"):
        return "xml"
    for pattern, language in _HEURISTICS:
        if pattern.search(content):
            return language
    return "text"


def detect_language(relative_path: Path, content: str) -> str:
    by_extension = detect_by_extension(relative_path)
    if by_extension:
        if by_extension == "c" and relative_path.suffix.lower() == ".h" and _looks_like_cpp_header(content):
            return "cpp"
        return by_extension
    by_shebang = detect_by_shebang(content)
    if by_shebang:
        return by_shebang
    return detect_by_heuristic(content)
