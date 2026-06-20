"""Default ignore rules and glob matching for individual files.

Directory names are pruned by the walker before it ever reaches pathspec (see
file_walker.py) — this module only matches file-level glob patterns such as
``*.png`` against files that survive directory pruning.
"""
from __future__ import annotations

import pathspec

from app.config import Settings


def build_ignore_spec(settings: Settings) -> pathspec.PathSpec:
    return pathspec.PathSpec.from_lines("gitignore", settings.ignored_file_globs)


def is_ignored_file(relative_posix_path: str, spec: pathspec.PathSpec) -> bool:
    return spec.match_file(relative_posix_path)
