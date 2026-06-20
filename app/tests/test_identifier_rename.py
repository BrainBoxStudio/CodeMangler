"""Code-identifier renaming (CLAUDE.md sections 5/6/9) — Python via tree-sitter."""
import ast

import pytest

from app.anonymization.code_anonymizer import anonymize_text
from app.anonymization.fake_value_generator import FakeValueGenerator
from app.code import parser as ts_parser
from app.code.identifier_extractor import collect_identifier_findings
from app.config import MangleOptions, Settings
from app.mapping.map_writer import build_map
from app.mapping.restore_engine import restore_text

pytestmark = pytest.mark.skipif(
    not ts_parser.is_available(), reason='tree-sitter not installed (pip install -e ".[code]")'
)


def test_renames_class_method_and_parameters(sample_python_source):
    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, changes = anonymize_text(sample_python_source, settings, generator, language="python")

    by_category = {c.category: c.original for c in changes}
    assert by_category["class"] == "PaymentGatewayClient"
    assert by_category["method"] == "establish_connection"
    assert "UserName" in [c.original for c in changes if c.category == "variable"]
    assert "Password" in [c.original for c in changes if c.category == "variable"]

    # Renamed consistently everywhere it's used, not just at the definition.
    assert "PaymentGatewayClient" not in sanitized
    assert "establish_connection" not in sanitized
    assert "UserName" not in sanitized

    # Library/stdlib symbols are only ever referenced, never defined in this
    # snippet, so the safety principle leaves them untouched.
    assert "requests" in sanitized
    assert ".post(" in sanitized


def test_sanitized_output_is_syntactically_valid(sample_python_source):
    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, _ = anonymize_text(sample_python_source, settings, generator, language="python")
    ast.parse(sanitized)  # raises SyntaxError if renaming broke anything


def test_rename_and_restore_round_trip_byte_for_byte(sample_python_source):
    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, changes = anonymize_text(sample_python_source, settings, generator, language="python")

    sanitization_map = build_map({"sample.py": ("python", changes)})
    file_changes = [c for c in sanitization_map.changes if c.file == "sample.py"]
    restored = restore_text(sanitized, file_changes)

    assert restored == sample_python_source


def test_self_and_cls_are_never_renamed():
    src = (
        "class Foo:\n"
        "    def bar(self, x):\n"
        "        return self.x + x\n"
        "    @classmethod\n"
        "    def make(cls):\n"
        "        return cls()\n"
    )
    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, changes = anonymize_text(src, settings, generator, language="python")
    assert "self" not in [c.original for c in changes]
    assert "cls" not in [c.original for c in changes]
    assert ".self" not in sanitized  # sanity: self itself still reads as "self"


def test_dunder_methods_are_never_renamed():
    src = "class Foo:\n    def __init__(self, x):\n        self.x = x\n"
    settings = Settings()
    generator = FakeValueGenerator()
    _, changes = anonymize_text(src, settings, generator, language="python")
    assert "__init__" not in [c.original for c in changes]


def test_usage_only_symbol_is_never_renamed_without_a_local_definition():
    # `ExternalBase` is referenced (as a base class) but never defined in this
    # snippet — mirrors Test/Original's real C++ SDK case (ChannelListMgr
    # locally defined and safe to rename; ReferenceTarget only referenced,
    # excluded) using Python syntax for a fast, dependency-free unit test.
    src = "class Derived(ExternalBase):\n    def run(self):\n        return ExternalBase.run(self)\n"
    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, changes = anonymize_text(src, settings, generator, language="python")
    renamed = {c.original for c in changes}
    assert "Derived" in renamed
    assert "ExternalBase" not in renamed
    assert "ExternalBase" in sanitized


def test_protected_identifiers_setting_is_respected(sample_python_source):
    settings = Settings(protected_identifiers=frozenset({"establish_connection"}))
    generator = FakeValueGenerator()
    _, changes = anonymize_text(sample_python_source, settings, generator, language="python")
    assert "establish_connection" not in [c.original for c in changes]
    assert "PaymentGatewayClient" in [c.original for c in changes]  # other names unaffected


def test_code_identifiers_flag_disables_renaming_entirely(sample_python_source):
    settings = Settings(mangle_options=MangleOptions(code_identifiers=False))
    generator = FakeValueGenerator()
    sanitized, changes = anonymize_text(sample_python_source, settings, generator, language="python")
    assert all(c.category not in ("class", "method", "function", "variable") for c in changes)
    assert "PaymentGatewayClient" in sanitized
    # Sensitive-value mangling still runs independently of the identifier flag.
    assert "ghp_1234567890abcdef1234567890abcdef1234" not in sanitized


def test_code_variables_subflag_disables_only_variables(sample_python_source):
    options = MangleOptions(code_variables=False)
    settings = Settings(mangle_options=options)
    generator = FakeValueGenerator()
    _, changes = anonymize_text(sample_python_source, settings, generator, language="python")
    categories = {c.category for c in changes}
    assert "variable" not in categories
    assert "class" in categories
    assert "method" in categories


def test_conflicting_fake_name_gets_suffixed():
    # RealClass is encountered first, so FakeValueGenerator's per-session
    # counter naturally assigns it "Cls001" — but a second class is already
    # *literally* named "Cls001" in this file. CLAUDE.md section 9 requires
    # detecting that collision and suffixing rather than silently clobbering
    # the real name into an ambiguous duplicate.
    src = "class RealClass:\n    pass\n\nclass Cls001:\n    pass\n"
    settings = Settings()
    generator = FakeValueGenerator()
    _, changes = anonymize_text(src, settings, generator, language="python")

    real_class_change = next(c for c in changes if c.original == "RealClass")
    cls001_change = next(c for c in changes if c.original == "Cls001")

    assert real_class_change.replacement == "Cls001_001"
    assert cls001_change.replacement == "Cls002"
    assert real_class_change.replacement != cls001_change.replacement


def test_identifier_findings_are_empty_for_unsupported_language():
    settings = Settings()
    generator = FakeValueGenerator()
    findings = collect_identifier_findings("SELECT * FROM users;", "sql", settings, generator)
    assert findings == []


# ── JavaScript / TypeScript ──────────────────────────────────────────────────


def test_javascript_renames_variable_consistently_across_usages():
    src = (
        "const apiConfig = { apiKey: \"AKIAQWERTYUIOPASDFGH\" };\n"
        "module.exports = apiConfig;\n"
    )
    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, changes = anonymize_text(src, settings, generator, language="javascript")

    renamed = {c.original: c.replacement for c in changes if c.category == "variable"}
    assert renamed["apiConfig"] == "var001"
    assert sanitized.count("var001") == 2  # declaration + module.exports usage
    assert "apiConfig" not in sanitized
    # Object literal keys are never definitions -> never renamed.
    assert "apiKey" in sanitized


def test_typescript_interface_class_and_method_renamed_consistently():
    src = (
        "interface Shape {\n"
        "  area(): number;\n"
        "}\n"
        "class Circle implements Shape {\n"
        "  radius: number;\n"
        "  area(): number { return this.radius * this.radius; }\n"
        "}\n"
    )
    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, changes = anonymize_text(src, settings, generator, language="typescript")

    categories = {c.category for c in changes}
    assert {"interface", "class", "method", "variable"} <= categories
    assert "Shape" not in sanitized
    assert "Circle" not in sanitized
    assert "implements Iface001" in sanitized  # interface contract stays in sync


def test_typescript_output_has_no_syntax_errors():
    from app.code import parser as ts_parser

    src = (
        "function makeCircle(r: number): number {\n"
        "  const c = r * 2;\n"
        "  return c;\n"
        "}\n"
    )
    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, _ = anonymize_text(src, settings, generator, language="typescript")
    root = ts_parser.parse("typescript", sanitized)
    assert root is not None
    assert not ts_parser.has_syntax_errors(root)


def test_javascript_and_typescript_restore_round_trip():
    src = (
        "interface Shape { area(): number; }\n"
        "class Circle implements Shape {\n"
        "  radius: number;\n"
        "  area(): number { return this.radius * this.radius; }\n"
        "}\n"
    )
    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, changes = anonymize_text(src, settings, generator, language="typescript")

    sanitization_map = build_map({"shape.ts": ("typescript", changes)})
    file_changes = [c for c in sanitization_map.changes if c.file == "shape.ts"]
    restored = restore_text(sanitized, file_changes)
    assert restored == src


# ── C++ ───────────────────────────────────────────────────────────────────
#
# This is the highest-risk language (no type/semantic resolution from
# tree-sitter alone) — these tests exercise the exact pattern proven real by
# Test/Original/Include/ChannelListMgr.h: a locally-defined class deriving
# from an externally-defined SDK base class that's only ever referenced.

_SDK_LIKE_CPP_SOURCE = (
    "class ChannelListMgr : public ReferenceTarget {\n"
    "public:\n"
    "    int count;\n"
    "    void Update();\n"
    "};\n"
    "\n"
    "void ChannelListMgr::Update() {\n"
    "    count = count + 1;\n"
    "}\n"
)


def test_cpp_renames_locally_defined_class_consistently_including_out_of_line_method():
    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, changes = anonymize_text(_SDK_LIKE_CPP_SOURCE, settings, generator, language="cpp")

    renamed = {c.original for c in changes}
    assert "ChannelListMgr" in renamed
    assert "Update" in renamed
    assert "ChannelListMgr" not in sanitized
    # Out-of-line definition (`ChannelListMgr::Update`) renamed in sync with
    # the in-class declaration — both spellings of the class name match.
    assert sanitized.count("Cls001") >= 2


def test_cpp_never_renames_a_base_class_that_is_only_referenced():
    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, changes = anonymize_text(_SDK_LIKE_CPP_SOURCE, settings, generator, language="cpp")

    renamed = {c.original for c in changes}
    assert "ReferenceTarget" not in renamed
    assert "ReferenceTarget" in sanitized  # left exactly as-is


def test_cpp_namespace_and_struct_renamed():
    src = "namespace MyNs {\n    struct Point { int x; int y; };\n}\n"
    settings = Settings()
    generator = FakeValueGenerator()
    _, changes = anonymize_text(src, settings, generator, language="cpp")
    categories = {c.category for c in changes}
    assert "namespace" in categories
    assert "struct" in categories


def test_cpp_pointer_locals_and_params_are_renamed():
    # Regression for a real bug found via a pasted SDK snippet: pointer
    # declarators (`PolyObject *pobj`) nest the identifier one level deeper
    # than a plain declarator (`int count`), inside a pointer_declarator
    # node — collectors that only checked the immediate child's kind
    # silently skipped every pointer local/param (`pobj`, `normals`, `msh`,
    # and pointer parameters `d`/`obj`), while non-pointer locals like
    # `count`/`i` were renamed fine.
    src = (
        "void COMMod::GetPolyNormals(int numPoints, COMData* d, Object *obj) {\n"
        "    PolyObject *pobj = (PolyObject*)obj;\n"
        "    MNMesh * msh = &(pobj->GetMesh());\n"
        "    Point3* normals = d->normals.Addr(0);\n"
        "    int count = 0;\n"
        "}\n"
    )
    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, changes = anonymize_text(src, settings, generator, language="cpp")

    renamed = {c.original for c in changes}
    for name in ("pobj", "msh", "normals", "d", "obj", "count"):
        assert name in renamed, f"{name!r} was not renamed"
    for name in ("pobj", "msh"):
        assert name not in sanitized


def test_cpp_keywords_never_renamed_even_on_else_if_misparse():
    # Regression: when tree-sitter-cpp can't bind an `else` to a preceding
    # `if` (here: a pasted fragment that starts mid chain, with no `if`
    # above it at all), it falls back to parsing `else if (cond) {...}` as a
    # declaration statement — `else` becomes a fake type_identifier and `if`
    # becomes the declared variable name inside an init_declarator (the same
    # shape as `TypeName varName(args);`). Without a hard keyword denylist,
    # that misparsed `if` looked like a genuine local variable definition
    # and got renamed to a fake name.
    src = (
        "else if ( obj->IsSubClassOf(patchObjectClassID) )\n"
        "{\n"
        "    DoB();\n"
        "}\n"
    )
    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, changes = anonymize_text(src, settings, generator, language="cpp")

    renamed = {c.original for c in changes}
    assert "if" not in renamed
    assert "else" not in renamed
    assert sanitized.startswith("else if")
    # External/library symbols never locally defined stay untouched.
    assert "COMMod" not in renamed
    assert "PolyObject" not in renamed
    assert "Addr" not in renamed


def test_cpp_output_has_no_syntax_errors():
    from app.code import parser as ts_parser

    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, _ = anonymize_text(_SDK_LIKE_CPP_SOURCE, settings, generator, language="cpp")
    root = ts_parser.parse("cpp", sanitized)
    assert root is not None
    assert not ts_parser.has_syntax_errors(root)


def test_cpp_restore_round_trip():
    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, changes = anonymize_text(_SDK_LIKE_CPP_SOURCE, settings, generator, language="cpp")

    sanitization_map = build_map({"mgr.cpp": ("cpp", changes)})
    file_changes = [c for c in sanitization_map.changes if c.file == "mgr.cpp"]
    restored = restore_text(sanitized, file_changes)
    assert restored == _SDK_LIKE_CPP_SOURCE


def test_cpp_protected_identifiers_setting_protects_an_sdk_lifecycle_method():
    # Simulates a case the definition-based filter alone can't catch: a
    # virtual override that must keep its exact name to satisfy an SDK
    # vtable contract (CLAUDE.md section 5's "framework lifecycle methods").
    settings = Settings(protected_identifiers=frozenset({"Update"}))
    generator = FakeValueGenerator()
    _, changes = anonymize_text(_SDK_LIKE_CPP_SOURCE, settings, generator, language="cpp")
    renamed = {c.original for c in changes}
    assert "Update" not in renamed
    assert "ChannelListMgr" in renamed  # unrelated names unaffected


@pytest.mark.parametrize(
    "relative_path",
    [
        "Include/ChannelListMgr.h",
        "Source/ChannelListMgr.cpp",
        "Include/ClassDesc.h",
    ],
)
def test_cpp_real_sdk_fixture_renames_safely_and_stays_valid(relative_path):
    """Runs identifier renaming against the real 3ds Max SDK plugin code in
    Test/Original (not a synthetic sample). Some of these files already fail
    to fully parse even before any renaming — tree-sitter-cpp parses without
    running the preprocessor first, and this codebase has #ifdef/#else blocks
    it can't fully resolve — so the meaningful invariant is "renaming doesn't
    make things worse", not "zero errors unconditionally". Either way, the
    well-known SDK base type referenced throughout this codebase must never
    be renamed (it's never defined in the scanned input, only referenced)."""
    from pathlib import Path

    from app.code import parser as ts_parser

    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / "Test" / "Original" / relative_path
    if not source_path.exists():
        pytest.skip(f"{relative_path} not present in Test/Original")

    text = source_path.read_text(encoding="utf-8", newline="")
    original_root = ts_parser.parse("cpp", text)
    original_had_errors = ts_parser.has_syntax_errors(original_root)

    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, changes = anonymize_text(text, settings, generator, language="cpp")

    sanitized_root = ts_parser.parse("cpp", sanitized)
    assert sanitized_root is not None
    if not original_had_errors:
        assert not ts_parser.has_syntax_errors(sanitized_root)

    renamed = {c.original for c in changes}
    assert "ReferenceTarget" not in renamed


# ── Java ──────────────────────────────────────────────────────────────────

_JAVA_SOURCE = (
    "public interface Shape {\n"
    "    double area();\n"
    "}\n"
    "public class Circle implements Shape {\n"
    "    private double radius;\n"
    "    public Circle(double radius) { this.radius = radius; }\n"
    "    public double area() { return radius * radius; }\n"
    "    public static void main(String[] args) {\n"
    "        Circle c = new Circle(5.0);\n"
    "    }\n"
    "}\n"
)


def test_java_renames_interface_class_constructor_and_field_consistently():
    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, changes = anonymize_text(_JAVA_SOURCE, settings, generator, language="java")

    categories = {c.category for c in changes}
    assert {"interface", "class", "method", "variable"} <= categories
    assert "Shape" not in sanitized
    assert "Circle" not in sanitized
    assert "implements Iface001" in sanitized
    # Constructor renamed in sync with the class (same text, no special-casing
    # needed — same mechanism that handles C++ constructors/destructors).
    assert sanitized.count("Cls001") >= 3


def test_java_main_method_is_never_renamed():
    settings = Settings()
    generator = FakeValueGenerator()
    _, changes = anonymize_text(_JAVA_SOURCE, settings, generator, language="java")
    assert "main" not in [c.original for c in changes]


def test_java_output_has_no_syntax_errors():
    from app.code import parser as ts_parser

    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, _ = anonymize_text(_JAVA_SOURCE, settings, generator, language="java")
    root = ts_parser.parse("java", sanitized)
    assert root is not None
    assert not ts_parser.has_syntax_errors(root)


def test_java_restore_round_trip():
    settings = Settings()
    generator = FakeValueGenerator()
    sanitized, changes = anonymize_text(_JAVA_SOURCE, settings, generator, language="java")

    sanitization_map = build_map({"Circle.java": ("java", changes)})
    file_changes = [c for c in sanitization_map.changes if c.file == "Circle.java"]
    restored = restore_text(sanitized, file_changes)
    assert restored == _JAVA_SOURCE


def test_java_multi_declarator_field_renames_all_names():
    src = "class Foo {\n    private double radius, scale;\n}\n"
    settings = Settings()
    generator = FakeValueGenerator()
    _, changes = anonymize_text(src, settings, generator, language="java")
    renamed = {c.original for c in changes}
    assert "radius" in renamed
    assert "scale" in renamed
