"""Generic parsing facade. Currently delegates entirely to tree-sitter, but
keeps the tree-sitter-specific module separate so a different engine could be
swapped in per-language later without touching scope_analyzer.py's callers.
"""
from __future__ import annotations

from app.code.tree_sitter_parser import (
    SUPPORTED_LANGUAGES,
    byte_to_char_map,
    has_syntax_errors,
    is_available,
    parse,
)

__all__ = [
    "SUPPORTED_LANGUAGES",
    "byte_to_char_map",
    "has_syntax_errors",
    "is_available",
    "parse",
]
