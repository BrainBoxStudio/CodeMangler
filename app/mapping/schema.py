"""Pydantic models for sanitization_map.json (CLAUDE.md section 7).

`type` is the coarse category from the spec's example enum; `category` is the
finer-grained detector category (e.g. "aws_access_key") and is an additive
field beyond the spec's minimum schema, kept because restore and reporting
both want it. Neither field is a strict enum — custom/user-defined categories
(known_terms, custom_patterns) pass their own label straight through.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChangeEntry(BaseModel):
    id: str
    file: str
    type: str
    category: str
    language: str
    original: str
    replacement: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    scope: str
    confidence: float
    detector: str
    reversible: bool = True


class FileEntry(BaseModel):
    path: str
    language: str


class SanitizationMap(BaseModel):
    version: str = "1.0"
    created_at: str
    session_id: str
    mode: str = "sanitize"
    files: list[FileEntry] = Field(default_factory=list)
    changes: list[ChangeEntry] = Field(default_factory=list)
