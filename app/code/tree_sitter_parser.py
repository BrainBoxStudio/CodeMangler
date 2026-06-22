"""tree-sitter-language-pack wrapper — lazy-imported, same optional-dependency
pattern as app/detection/pii_detector.py's Presidio handling: if `tree-sitter`/
`tree-sitter-language-pack` aren't installed (`pip install -e ".[code]"`),
identifier renaming is silently skipped rather than the app crashing.

Two API quirks of this binding worth documenting, since they're easy to get
wrong silently:
1. Every Node/Tree accessor (`root_node`, `kind`, `start_byte`, `child`, ...)
   is a bound *method*, not a property — must be called with `()`.
2. `start_byte`/`end_byte` are UTF-8 *byte* offsets, not Python `str` character
   offsets. They only coincide for pure-ASCII text. `byte_to_char_map()` below
   builds the conversion table once per file so the rest of the pipeline (which
   works in `str` character offsets, like every other detector) never has to
   know tree-sitter uses bytes internally.
"""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

# Our internal language names (app.detection.language_detector) that map
# directly onto tree-sitter-language-pack grammar names.
SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"python", "javascript", "typescript", "cpp", "java"})

_unavailable_logged = False


def _get_language_pack():
    global _unavailable_logged
    try:
        import tree_sitter_language_pack
    except ImportError:
        if not _unavailable_logged:
            logger.warning(
                "tree-sitter-language-pack not installed; skipping code-identifier "
                'renaming (install with `pip install -e ".[code]"`)'
            )
            _unavailable_logged = True
        return None
    return tree_sitter_language_pack


def is_available() -> bool:
    return _get_language_pack() is not None


_thread_local = threading.local()


def _get_parser(language: str):
    # tree-sitter-language-pack's Parser is a PyO3 "unsendable" Rust object:
    # it may only be touched (even dropped) by the thread that created it.
    # Each sanitize/restore run spawns a brand-new QThread, so a process-wide
    # cache (e.g. functools.lru_cache) would hand a thread-A-owned Parser to
    # thread B and panic. Caching per-thread keeps the reuse benefit within a
    # single run (many files, one thread) without ever crossing threads.
    cache = getattr(_thread_local, "parsers", None)
    if cache is None:
        cache = {}
        _thread_local.parsers = cache
    if language in cache:
        return cache[language]

    pack = _get_language_pack()
    if pack is None:
        cache[language] = None
        return None
    try:
        parser = pack.get_parser(language)
    except Exception:
        logger.warning("tree-sitter: no grammar available for language=%s", language, exc_info=True)
        parser = None
    cache[language] = parser
    return parser


def parse(language: str, text: str):
    """Returns the root Node for `text`, or None if parsing isn't possible
    (language unsupported, dependency missing, or a parser-level failure).
    Does not raise — callers treat None as "skip identifier renaming".
    """
    if language not in SUPPORTED_LANGUAGES:
        return None
    parser = _get_parser(language)
    if parser is None:
        return None
    try:
        tree = parser.parse(text)
        return tree.root_node()
    except Exception:
        logger.warning("tree-sitter: failed to parse language=%s", language, exc_info=True)
        return None


def has_syntax_errors(root_node) -> bool:
    """Post-rename safety net (CLAUDE.md section 17): re-parse the mangled
    output and check tree-sitter's own error flag before trusting the result.
    """
    return root_node.has_error()


def byte_to_char_map(text: str) -> list[int]:
    """byte_to_char_map(text)[byte_offset] -> character offset into `text`.

    One extra entry past the last byte covers end-of-span lookups (a span
    ending at end_byte == len(encoded) is common for the final identifier
    in a file).
    """
    encoded_len = len(text.encode("utf-8"))
    table = [0] * (encoded_len + 1)
    byte_idx = 0
    for char_idx, ch in enumerate(text):
        char_byte_len = len(ch.encode("utf-8"))
        for offset in range(char_byte_len):
            table[byte_idx + offset] = char_idx
        byte_idx += char_byte_len
    table[byte_idx] = len(text)
    return table
