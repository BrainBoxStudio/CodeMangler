"""Turns raw tree-sitter occurrences into Finding objects ready for the
existing detection/anonymization pipeline (app/detection/findings.py,
app/anonymization/text_anonymizer.py) — no new replacement machinery needed;
identifier renames are "just another detector's findings" from that point on.

Safety principle (CLAUDE.md section 5): a name is only eligible for renaming
if at least one occurrence is a real *definition*, never on bare usage alone.
Concretely, in Test/Original/Include/ChannelListMgr.h: `class ChannelListMgr
: public ReferenceTarget` — `ChannelListMgr` has a definition occurrence
(class_specifier's name) so it's eligible; `ReferenceTarget` only ever
appears as a reference (base_class_clause) with no definition anywhere in
the scanned input, so it's correctly left untouched without needing an
SDK-specific allowlist.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from app.anonymization.fake_value_generator import FakeValueGenerator
from app.code import parser, scope_analyzer
from app.config import Settings
from app.detection.findings import Finding

# Maps an identifier category onto the MangleOptions sub-flag that gates it.
_CATEGORY_TO_OPTION: dict[str, str] = {
    "variable": "code_variables",
    "function": "code_functions",
    "method": "code_functions",
    "class": "code_classes",
    "struct": "code_classes",
    "typedef": "code_classes",  # typedef/using/type-alias: a type name, gated with classes
    "interface": "code_interfaces",
    "enum": "code_enums",
    "enum_member": "code_enums",  # gated together with the enum name itself
    "namespace": "code_namespaces",
    "constant": "code_constants",
}


@dataclass
class IdentifierCatalog:
    """Project-wide eligibility, built once across every file in a multi-file
    run (Folder mode) — see build_identifier_catalog()."""

    definitions: dict[str, str] = field(default_factory=dict)  # name -> category
    all_names: set[str] = field(default_factory=set)  # every identifier seen anywhere in the run


def build_identifier_catalog(files: list[tuple[str, str]]) -> IdentifierCatalog:
    """Pre-scans every file in a run (`files` = list of (language, text)) so
    a name defined in one file (e.g. a class in a header) is recognised as
    eligible everywhere it's used in any other file (e.g. via `Class::method`
    in the matching .cpp) — the per-file-only version of this check in
    collect_identifier_findings() would otherwise rename the class in the
    header but never touch it in a .cpp file that only references it.

    Same "first definition wins" trade-off as the existing whole-file
    name-based matching in scope_analyzer.py, just extended project-wide: if
    the same name is genuinely a different thing in two different files,
    the category from whichever file was scanned first sticks.
    """
    catalog = IdentifierCatalog()
    for language, text in files:
        root = parser.parse(language, text)
        if root is None:
            continue
        occurrences = scope_analyzer.collect_occurrences(language, root)
        if not occurrences:
            continue
        byte_map = parser.byte_to_char_map(text)
        for occ in occurrences:
            name = text[byte_map[occ.start_byte] : byte_map[occ.end_byte]]
            catalog.all_names.add(name)
            if occ.is_definition and name not in catalog.definitions:
                catalog.definitions[name] = occ.category
    return catalog


def collect_identifier_findings(
    text: str,
    language: str,
    settings: Settings,
    generator: FakeValueGenerator,
    catalog: IdentifierCatalog | None = None,
) -> list[Finding]:
    options = settings.mangle_options
    if not options.code_identifiers:
        return []

    root = parser.parse(language, text)
    if root is None:
        return []

    raw_occurrences = scope_analyzer.collect_occurrences(language, root)
    if not raw_occurrences:
        return []

    byte_map = parser.byte_to_char_map(text)

    # Dedup by exact span: the same byte range can be emitted twice (once by
    # the generic identifier-leaf walk, once by a definition-site special
    # case) — keep the definition-tagged version when both exist.
    best_by_span: dict[tuple[int, int], scope_analyzer.RawOccurrence] = {}
    for occ in raw_occurrences:
        key = (occ.start_byte, occ.end_byte)
        existing = best_by_span.get(key)
        if existing is None or (occ.is_definition and not existing.is_definition):
            best_by_span[key] = occ

    groups: dict[str, list[scope_analyzer.RawOccurrence]] = defaultdict(list)
    names_by_span: dict[tuple[int, int], str] = {}
    for span, occ in best_by_span.items():
        char_start, char_end = byte_map[span[0]], byte_map[span[1]]
        name = text[char_start:char_end]
        names_by_span[span] = name
        groups[name].append(occ)

    # With a project-wide catalog, fake-name collisions must be avoided
    # against every real name in the run, not just this file's own names —
    # otherwise a fake generated here could coincidentally collide with a
    # real name that only appears in some other file.
    collision_names = catalog.all_names if catalog is not None else set(groups.keys())
    findings: list[Finding] = []

    for name, occurrences in groups.items():
        if scope_analyzer.is_ignored_name(language, name):
            continue
        if name in settings.protected_identifiers:
            continue

        if catalog is not None:
            # Eligible if defined anywhere in the run, even if this file
            # only uses it (e.g. a class defined in a header, referenced via
            # `Class::method` in the matching .cpp).
            category = catalog.definitions.get(name)
            if category is None:
                continue
        else:
            definitions = [o for o in occurrences if o.is_definition]
            if not definitions:
                continue  # usage-only: never rename without a local definition
            category = definitions[0].category

        option_name = _CATEGORY_TO_OPTION.get(category)
        if option_name is None or not getattr(options, option_name):
            continue

        # CLAUDE.md section 9: if the natural fake collides with another
        # real name still present in the run, suffix until it doesn't.
        fake = generator.generate(category, name)
        if fake in collision_names and fake != name:
            suffix = 1
            candidate = f"{fake}_{suffix:03d}"
            while candidate in collision_names:
                suffix += 1
                candidate = f"{fake}_{suffix:03d}"
            generator.force(category, name, candidate)

        for occ in occurrences:
            char_start = byte_map[occ.start_byte]
            char_end = byte_map[occ.end_byte]
            findings.append(
                Finding(
                    start=char_start,
                    end=char_end,
                    category=category,
                    value=name,
                    confidence=1.0,
                    detector="tree-sitter",
                )
            )

    return findings
