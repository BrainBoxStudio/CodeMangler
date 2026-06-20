"""Fuzz-style robustness sweep for the reserved-keyword denylist
(app/code/scope_analyzer.py).

Follow-up to the real `else if` bug (a fragment where `else` can't bind to a
preceding `if` gets misparsed by tree-sitter-cpp's error recovery as a
declaration, with `if` landing on a declared-name node) — see
test_identifier_rename.py::test_cpp_keywords_never_renamed_even_on_else_if_misparse
for that specific case. This file generalizes the check: any clause keyword
that's grammatically *dependent on a preceding clause* (else, catch, finally,
except, elif, case) is a structural candidate for the same class of
misparse when isolated as a fragment or following unbalanced/malformed code
upstream. Probed directly against the parser before writing these cases in;
every one of them is confirmed clean today because the denylist is a hard
guarantee independent of how the parser classifies a node — this test exists
to keep it that way as the grammars/bindings change.
"""
from __future__ import annotations

import pytest

from app.anonymization.code_anonymizer import anonymize_text
from app.anonymization.fake_value_generator import FakeValueGenerator
from app.code.scope_analyzer import (
    _CPP_RESERVED_KEYWORDS,
    _JAVA_RESERVED_KEYWORDS,
    _JS_TS_RESERVED_KEYWORDS,
    _PYTHON_RESERVED_KEYWORDS,
)
from app.config import Settings

CASES = [
    # ── C++: dependent clauses with no anchor, or following unbalanced code ──
    ("cpp", "catch (std::exception& e) {\n    Log(e);\n}\n"),
    ("cpp", "catch (std::exception& e)\n    Log(e);\n"),
    ("cpp", "else\n    DoB();\n"),
    (
        "cpp",
        "void f() {\n  if (a) {\n    g();\n  // missing close brace\n"
        "  catch (std::exception& e)\n  {\n    h(e);\n  }\n}\n",
    ),
    (
        "cpp",
        "void f() {\n  if (a) {\n    g();\n  // missing close brace\n"
        "  while (b)\n  {\n    h();\n  }\n}\n",
    ),
    (
        "cpp",
        "void f() {\n  if (a) {\n    g();\n  // missing close brace\n"
        "  switch (b)\n  {\n  case 1: h(); break;\n  }\n}\n",
    ),
    (
        "cpp",
        "void f() {\n  if (a) {\n    g();\n  // missing close brace\n"
        "  for (int i=0;i<n;i++)\n  {\n    h(i);\n  }\n}\n",
    ),
    # ── Python: dependent clauses with no anchor (indentation-based, no braces) ──
    ("python", "elif other_cond:\n    do_b()\n"),
    ("python", "else:\n    do_b()\n"),
    ("python", "except ValueError as e:\n    handle(e)\n"),
    ("python", "finally:\n    cleanup()\n"),
    # ── JavaScript: dependent clauses with no anchor, or after unbalanced code ──
    ("javascript", "else {\n    doB();\n}\n"),
    ("javascript", "catch (e) {\n    handle(e);\n}\n"),
    ("javascript", "finally {\n    cleanup();\n}\n"),
    ("javascript", "case 1:\n    doA();\n    break;\n"),
    (
        "javascript",
        "function f() {\n  if (a) {\n    g();\n  // missing close brace\n"
        "  else {\n    h();\n  }\n}\n",
    ),
    (
        "javascript",
        "function f() {\n  try {\n    g();\n  // missing close brace\n"
        "  catch (e) {\n    h(e);\n  }\n}\n",
    ),
    (
        "javascript",
        "function f() {\n  if (a) {\n    g();\n  // missing close brace\n"
        "  switch (x) {\n    case 1: h(); break;\n  }\n}\n",
    ),
    ("javascript", "const fn = (capture) => {\n    return capture"),  # truncated mid-body
    ("javascript", "const x = cond ? a :"),  # truncated ternary
    # ── Java: dependent clauses with no anchor, or after unbalanced code ──
    ("java", "else {\n    doB();\n}\n"),
    ("java", "catch (Exception e) {\n    handle(e);\n}\n"),
    ("java", "finally {\n    cleanup();\n}\n"),
    ("java", "case 1:\n    doA();\n    break;\n"),
    (
        "java",
        "void f() {\n  if (a) {\n    g();\n  // missing close brace\n"
        "  else {\n    h();\n  }\n}\n",
    ),
    (
        "java",
        "void f() {\n  try {\n    g();\n  // missing close brace\n"
        "  catch (Exception e) {\n    h(e);\n  }\n}\n",
    ),
    (
        "java",
        "void f() {\n  if (a) {\n    g();\n  // missing close brace\n"
        "  switch (x) {\n    case 1: h(); break;\n  }\n}\n",
    ),
]

_RESERVED_BY_LANGUAGE = {
    "cpp": _CPP_RESERVED_KEYWORDS,
    "python": _PYTHON_RESERVED_KEYWORDS,
    "javascript": _JS_TS_RESERVED_KEYWORDS,
    "java": _JAVA_RESERVED_KEYWORDS,
}


@pytest.mark.parametrize("language,fragment", CASES)
def test_no_reserved_keyword_is_ever_renamed(language: str, fragment: str) -> None:
    settings = Settings()
    generator = FakeValueGenerator()
    _sanitized, changes = anonymize_text(fragment, settings, generator, language=language)

    renamed = {c.original for c in changes}
    leaked = renamed & _RESERVED_BY_LANGUAGE[language]
    assert not leaked, f"reserved keyword(s) {leaked} were renamed for fragment: {fragment!r}"
