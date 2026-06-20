"""Per-language tree-sitter walkers that collect every identifier-bearing
occurrence in a file, tagged with whether it sits in a *definition* position
(CLAUDE.md section 5's rename list) and what category it is.

Design choice: rather than building a true nested scope tree (module -> class
-> function -> block) and resolving each reference to its exact declaring
scope, this collects occurrences by *exact text* across the whole file. A
name is only ever renamed if at least one occurrence is a real definition
(never on bare usage) — this is what protects external/library symbols that
are only referenced, never defined, in the scanned input (see
identifier_extractor.py's docstring for the concrete example from
Test/Original's C++ SDK code). The trade-off: two unrelated same-named locals
in different functions get the same fake name, rather than independent ones.
This never breaks correctness (rename+restore is still exact), only scope
*precision* — flagged as a known limitation rather than hidden.

Each per-language collector emits possibly-duplicate occurrences for the same
byte span (a definition-site special case alongside the generic identifier-
leaf walk); identifier_extractor.py dedups by span, preferring the
definition-tagged version. This sidesteps relying on tree-sitter Node object
identity/equality, which this binding's wrapper objects don't guarantee
across separate `.parent()`/`.child()` calls.

identifier_extractor.py::build_identifier_catalog() extends this same
trade-off from whole-*file* to whole-*project*: for multi-file runs (Folder
mode), a name is eligible if it has a real definition anywhere in the run,
not just in the file currently being rewritten — this is what lets a class
defined in a header get renamed consistently in a .cpp file that only
references it via `Class::method`. The same caveat applies one level up: if
the same name is genuinely two different things in two different files, the
category from whichever file was scanned first wins.
"""
from __future__ import annotations

from dataclasses import dataclass

# Parameter names conventional enough that renaming them protects no IP and
# only makes diffs noisier (CLAUDE.md section 5's "do not rename" spirit).
_PYTHON_IGNORED_NAMES: frozenset[str] = frozenset({"self", "cls"})


@dataclass(frozen=True)
class RawOccurrence:
    start_byte: int
    end_byte: int
    is_definition: bool
    category: str | None  # set when is_definition is True


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__") and len(name) > 4


def _is_python_method(func_node) -> bool:
    """True if `func_node` (a function_definition) is directly nested in a
    class body, rather than a module-level or locally-nested function."""
    current = func_node.parent()
    while current is not None:
        kind = current.kind()
        if kind == "class_definition":
            return True
        if kind == "function_definition":
            return False
        current = current.parent()
    return False


def _collect_python_params(params_node, occurrences: list[RawOccurrence]) -> None:
    for i in range(params_node.child_count()):
        child = params_node.child(i)
        kind = child.kind()
        if kind == "identifier":
            occurrences.append(RawOccurrence(child.start_byte(), child.end_byte(), True, "variable"))
        elif kind in ("typed_parameter", "default_parameter", "typed_default_parameter"):
            if child.child_count() > 0:
                first = child.child(0)
                if first.kind() == "identifier":
                    occurrences.append(
                        RawOccurrence(first.start_byte(), first.end_byte(), True, "variable")
                    )
        elif kind in ("list_splat_pattern", "dictionary_splat_pattern"):
            # *args / **kwargs: the name is the last child, after */**.
            if child.child_count() > 0:
                last = child.child(child.child_count() - 1)
                if last.kind() == "identifier":
                    occurrences.append(
                        RawOccurrence(last.start_byte(), last.end_byte(), True, "variable")
                    )


def _collect_python(root, occurrences: list[RawOccurrence]) -> None:
    def walk(node) -> None:
        kind = node.kind()

        if kind == "identifier":
            occurrences.append(RawOccurrence(node.start_byte(), node.end_byte(), False, None))

        if kind == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                occurrences.append(
                    RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, "class")
                )
        elif kind == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                category = "method" if _is_python_method(node) else "function"
                occurrences.append(
                    RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, category)
                )
            params = node.child_by_field_name("parameters")
            if params is not None:
                _collect_python_params(params, occurrences)
        elif kind == "assignment":
            left = node.child_by_field_name("left")
            if left is not None and left.kind() == "identifier":
                occurrences.append(RawOccurrence(left.start_byte(), left.end_byte(), True, "variable"))
        elif kind == "named_expression":  # walrus: (x := ...)
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                occurrences.append(
                    RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, "variable")
                )
        elif kind == "for_statement":
            left = node.child_by_field_name("left")
            if left is not None and left.kind() == "identifier":
                occurrences.append(RawOccurrence(left.start_byte(), left.end_byte(), True, "variable"))

        for i in range(node.child_count()):
            walk(node.child(i))

    walk(root)


def _collect_js_params(params_node, occurrences: list[RawOccurrence]) -> None:
    for i in range(params_node.child_count()):
        child = params_node.child(i)
        kind = child.kind()
        if kind == "identifier":
            occurrences.append(RawOccurrence(child.start_byte(), child.end_byte(), True, "variable"))
        elif kind in ("required_parameter", "optional_parameter"):
            # TypeScript wraps the name (plain identifier or a rest_pattern)
            # alongside an optional type_annotation / default-value sibling.
            if child.child_count() == 0:
                continue
            first = child.child(0)
            if first.kind() == "identifier":
                occurrences.append(RawOccurrence(first.start_byte(), first.end_byte(), True, "variable"))
            elif first.kind() == "rest_pattern" and first.child_count() > 1:
                inner = first.child(1)
                if inner.kind() == "identifier":
                    occurrences.append(
                        RawOccurrence(inner.start_byte(), inner.end_byte(), True, "variable")
                    )
        elif kind == "rest_pattern":  # plain JS: ...args
            if child.child_count() > 1:
                inner = child.child(1)
                if inner.kind() == "identifier":
                    occurrences.append(
                        RawOccurrence(inner.start_byte(), inner.end_byte(), True, "variable")
                    )
        elif kind == "assignment_pattern":  # plain JS default value: x = 5
            left = child.child_by_field_name("left")
            if left is not None and left.kind() == "identifier":
                occurrences.append(RawOccurrence(left.start_byte(), left.end_byte(), True, "variable"))


def _collect_js_ts(root, occurrences: list[RawOccurrence]) -> None:
    """Shared by both "javascript" and "typescript": TS-only node kinds
    (interface_declaration, type_identifier, enum_declaration, ...) simply
    never occur when this walks a tree parsed with the plain JS grammar.
    """

    def walk(node) -> None:
        kind = node.kind()

        if kind in ("identifier", "property_identifier", "type_identifier"):
            occurrences.append(RawOccurrence(node.start_byte(), node.end_byte(), False, None))

        if kind == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                occurrences.append(
                    RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, "class")
                )
        elif kind == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                occurrences.append(
                    RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, "function")
                )
            params = node.child_by_field_name("parameters")
            if params is not None:
                _collect_js_params(params, occurrences)
        elif kind == "method_definition":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                occurrences.append(
                    RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, "method")
                )
            params = node.child_by_field_name("parameters")
            if params is not None:
                _collect_js_params(params, occurrences)
        elif kind == "variable_declarator":
            name_node = node.child_by_field_name("name")
            if name_node is not None and name_node.kind() == "identifier":
                occurrences.append(
                    RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, "variable")
                )
        elif kind in ("public_field_definition", "field_definition"):
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                occurrences.append(
                    RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, "variable")
                )
        elif kind == "interface_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                occurrences.append(
                    RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, "interface")
                )
        elif kind == "enum_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                occurrences.append(
                    RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, "enum")
                )

        for i in range(node.child_count()):
            walk(node.child(i))

    walk(root)


_CPP_DECLARATOR_WRAPPERS: frozenset[str] = frozenset(
    {"pointer_declarator", "reference_declarator", "array_declarator", "parenthesized_declarator"}
)


def _unwrap_cpp_declarator(node):
    """Peel pointer/reference/array/parenthesized wrappers down to the
    underlying identifier/field_identifier. A pointer declarator
    (`PolyObject *pobj`) nests the name one level deeper than a plain
    declarator (`int count`) — `pobj` sits inside a pointer_declarator, not as
    a direct child — so callers that only checked the immediate child's kind
    silently dropped every pointer/reference/array local, parameter, and
    member field (the real bug behind `pobj`/`normals`/`msh` never being
    renamed in a pasted SDK snippet)."""
    while node is not None and node.kind() in _CPP_DECLARATOR_WRAPPERS:
        node = node.child_by_field_name("declarator")
    return node


def _collect_cpp_params(params_node, occurrences: list[RawOccurrence]) -> None:
    for i in range(params_node.child_count()):
        child = params_node.child(i)
        if child.kind() != "parameter_declaration":
            continue
        name_node = _unwrap_cpp_declarator(child.child_by_field_name("declarator"))
        if name_node is not None and name_node.kind() == "identifier":
            occurrences.append(RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, "variable"))


def _cpp_function_name(declarator):
    """`declarator` is a function_declarator; resolve its name + category.

    Covers free functions (`identifier`), in-class methods (`field_identifier`),
    and out-of-class method definitions (`qualified_identifier` — e.g.
    `void ChannelListMgr::Update()`, the exact pattern in Test/Original's real
    SDK code) where the method name is the qualified_identifier's `name` field.
    """
    inner = declarator.child_by_field_name("declarator")
    if inner is None:
        return None, None
    kind = inner.kind()
    if kind == "identifier":
        return inner, "function"
    if kind == "field_identifier":
        return inner, "method"
    if kind == "qualified_identifier":
        name = inner.child_by_field_name("name")
        if name is not None and name.kind() in ("identifier", "field_identifier"):
            return name, "method"
    return None, None


def _collect_cpp(root, occurrences: list[RawOccurrence]) -> None:
    def walk(node) -> None:
        kind = node.kind()

        if kind in ("identifier", "type_identifier", "field_identifier", "namespace_identifier"):
            occurrences.append(RawOccurrence(node.start_byte(), node.end_byte(), False, None))

        if kind in ("class_specifier", "struct_specifier"):
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                category = "class" if kind == "class_specifier" else "struct"
                occurrences.append(
                    RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, category)
                )
        elif kind == "namespace_definition":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                occurrences.append(
                    RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, "namespace")
                )
        elif kind == "function_definition":
            declarator = node.child_by_field_name("declarator")
            if declarator is not None and declarator.kind() == "function_declarator":
                name_node, category = _cpp_function_name(declarator)
                if name_node is not None:
                    occurrences.append(
                        RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, category)
                    )
                params = declarator.child_by_field_name("parameters")
                if params is not None:
                    _collect_cpp_params(params, occurrences)
        elif kind == "field_declaration":
            # Iterate every child rather than child_by_field_name("declarator")
            # alone — that accessor only returns the *first* match, silently
            # missing every name after the first in a multi-declarator
            # statement (`int numButtons, maxButtons;` — a real pattern from
            # Test/Original's SDK code).
            for i in range(node.child_count()):
                declarator = node.child(i)
                if declarator.kind() == "function_declarator":
                    name_node, category = _cpp_function_name(declarator)
                    if name_node is not None:
                        occurrences.append(
                            RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, category)
                        )
                    params = declarator.child_by_field_name("parameters")
                    if params is not None:
                        _collect_cpp_params(params, occurrences)
                    continue
                inner = _unwrap_cpp_declarator(declarator)
                if inner is not None and inner.kind() == "field_identifier":
                    occurrences.append(
                        RawOccurrence(inner.start_byte(), inner.end_byte(), True, "variable")
                    )
        elif kind in ("declaration", "init_declarator"):
            for i in range(node.child_count()):
                declarator = node.child(i)
                if declarator.kind() == "init_declarator":
                    declarator = declarator.child_by_field_name("declarator")
                inner = _unwrap_cpp_declarator(declarator)
                if inner is not None and inner.kind() == "identifier":
                    occurrences.append(
                        RawOccurrence(inner.start_byte(), inner.end_byte(), True, "variable")
                    )

        for i in range(node.child_count()):
            walk(node.child(i))

    walk(root)


def _collect_java_params(params_node, occurrences: list[RawOccurrence]) -> None:
    for i in range(params_node.child_count()):
        child = params_node.child(i)
        if child.kind() == "formal_parameter":
            name_node = child.child_by_field_name("name")
            if name_node is not None and name_node.kind() == "identifier":
                occurrences.append(RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, "variable"))
        elif child.kind() == "spread_parameter" and child.child_count() > 0:  # varargs: Type... name
            last = child.child(child.child_count() - 1)
            if last.kind() == "identifier":
                occurrences.append(RawOccurrence(last.start_byte(), last.end_byte(), True, "variable"))


def _collect_java_variable_declarators(node, occurrences: list[RawOccurrence]) -> None:
    """Shared by field_declaration and local_variable_declaration — both wrap
    one or more variable_declarator children (`int a, b;`), so this iterates
    every child rather than using child_by_field_name (which only returns the
    first match, the same multi-declarator gap found and fixed for C++).
    """
    for i in range(node.child_count()):
        child = node.child(i)
        if child.kind() == "variable_declarator":
            name_node = child.child_by_field_name("name")
            if name_node is not None and name_node.kind() == "identifier":
                occurrences.append(RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, "variable"))


def _collect_java(root, occurrences: list[RawOccurrence]) -> None:
    def walk(node) -> None:
        kind = node.kind()

        if kind in ("identifier", "type_identifier"):
            occurrences.append(RawOccurrence(node.start_byte(), node.end_byte(), False, None))

        if kind == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                occurrences.append(
                    RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, "class")
                )
        elif kind == "interface_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                occurrences.append(
                    RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, "interface")
                )
        elif kind == "enum_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                occurrences.append(
                    RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, "enum")
                )
        elif kind in ("method_declaration", "constructor_declaration"):
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                occurrences.append(
                    RawOccurrence(name_node.start_byte(), name_node.end_byte(), True, "method")
                )
            params = node.child_by_field_name("parameters")
            if params is not None:
                _collect_java_params(params, occurrences)
        elif kind in ("field_declaration", "local_variable_declaration"):
            _collect_java_variable_declarators(node, occurrences)

        for i in range(node.child_count()):
            walk(node.child(i))

    walk(root)


# Java lifecycle/contract methods that must keep their exact name regardless
# of being locally defined (CLAUDE.md section 5: "framework lifecycle
# methods", "magic methods unless explicitly safe").
_JAVA_IGNORED_NAMES: frozenset[str] = frozenset(
    {"main", "toString", "equals", "hashCode", "clone", "finalize"}
)


# Hard reserved-keyword denylists (CLAUDE.md section 5: "do not rename
# language keywords"). This is a belt-and-suspenders guarantee independent of
# how the parser classifies a node — normally a keyword can never reach here
# at all, since tree-sitter grammars expose keywords as anonymous tokens, not
# identifier-kind nodes. But parser *error recovery* on malformed/incomplete
# input (e.g. a pasted fragment that starts mid `if`/`else if` chain, so the
# parser can't bind the `else` to a preceding `if`) can misclassify a keyword
# as an identifier: confirmed concretely — `else if (cond) { ... }` with no
# preceding `if` parses as a `declaration` where `else` becomes a fake
# `type_identifier` and `if` becomes the declared name inside an
# `init_declarator` (the same "TypeName varName(args);" shape as a real
# direct-initialization declaration). Without this denylist, that misparsed
# `if` looked like a genuine local variable definition and got renamed.
_CPP_RESERVED_KEYWORDS: frozenset[str] = frozenset(
    {
        "if", "else", "for", "while", "do", "switch", "case", "default",
        "break", "continue", "return", "goto", "try", "catch", "throw",
        "class", "struct", "enum", "union", "namespace", "using", "typedef",
        "public", "private", "protected", "virtual", "static", "const",
        "constexpr", "volatile", "mutable", "friend", "template", "typename",
        "new", "delete", "sizeof", "this", "operator", "void", "int", "char",
        "bool", "float", "double", "long", "short", "unsigned", "signed",
        "auto", "inline", "extern", "register", "true", "false", "nullptr",
    }
)
_PYTHON_RESERVED_KEYWORDS: frozenset[str] = frozenset(
    {
        "if", "elif", "else", "for", "while", "try", "except", "finally",
        "with", "as", "def", "class", "return", "yield", "import", "from",
        "pass", "break", "continue", "raise", "lambda", "global", "nonlocal",
        "assert", "del", "in", "is", "not", "and", "or", "True", "False",
        "None", "async", "await",
    }
)
_JS_TS_RESERVED_KEYWORDS: frozenset[str] = frozenset(
    {
        "if", "else", "for", "while", "do", "switch", "case", "default",
        "break", "continue", "return", "function", "class", "extends",
        "super", "this", "new", "delete", "typeof", "instanceof", "in", "of",
        "try", "catch", "finally", "throw", "var", "let", "const", "import",
        "export", "from", "as", "async", "await", "yield", "void", "true",
        "false", "null", "undefined", "interface", "type", "enum",
        "namespace", "implements",
    }
)
_JAVA_RESERVED_KEYWORDS: frozenset[str] = frozenset(
    {
        "if", "else", "for", "while", "do", "switch", "case", "default",
        "break", "continue", "return", "class", "interface", "enum",
        "extends", "implements", "public", "private", "protected", "static",
        "final", "abstract", "void", "int", "char", "boolean", "byte",
        "short", "long", "float", "double", "new", "this", "super", "try",
        "catch", "finally", "throw", "throws", "import", "package",
        "instanceof", "synchronized", "true", "false", "null",
    }
)


_COLLECTORS = {
    "python": _collect_python,
    "javascript": _collect_js_ts,
    "typescript": _collect_js_ts,
    "cpp": _collect_cpp,
    "java": _collect_java,
}

_IGNORED_NAMES_BY_LANGUAGE: dict[str, frozenset[str]] = {
    "python": _PYTHON_IGNORED_NAMES | _PYTHON_RESERVED_KEYWORDS,
    "java": _JAVA_IGNORED_NAMES | _JAVA_RESERVED_KEYWORDS,
    "cpp": _CPP_RESERVED_KEYWORDS,
    "javascript": _JS_TS_RESERVED_KEYWORDS,
    "typescript": _JS_TS_RESERVED_KEYWORDS,
}


def collect_occurrences(language: str, root) -> list[RawOccurrence]:
    collector = _COLLECTORS.get(language)
    if collector is None:
        return []
    occurrences: list[RawOccurrence] = []
    collector(root, occurrences)
    return occurrences


def is_ignored_name(language: str, name: str) -> bool:
    if _is_dunder(name):
        return True
    return name in _IGNORED_NAMES_BY_LANGUAGE.get(language, frozenset())
