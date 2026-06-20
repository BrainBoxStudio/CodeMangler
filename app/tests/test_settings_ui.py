"""Settings tab: theming (app/ui/styles.py), persistence
(app/ui/user_settings.py), and Mangle Keywords threading into SanitizeWorker
(app/ui/workers.py) — pure-logic checks only, no QApplication/widgets
required (this project's established practice: unit-test the logic, smoke-
test the widgets themselves manually via run_ui.bat).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.anonymization.code_anonymizer import anonymize_text
from app.anonymization.fake_value_generator import FakeValueGenerator
from app.ui.styles import (
    PALETTE_LIGHT_BLUE,
    PREDEFINED_PALETTES,
    THEME,
    build_stylesheet,
    derive_palette_from_base_color,
)
from app.ui.user_settings import UserSettings, load_user_settings, save_user_settings
from app.ui.workers import SanitizeWorker


def test_default_theme_matches_light_blue_palette():
    assert THEME == build_stylesheet(PALETTE_LIGHT_BLUE)


@pytest.mark.parametrize("name", list(PREDEFINED_PALETTES.keys()))
def test_predefined_palettes_render_nonempty_stylesheet(name: str):
    css = build_stylesheet(PREDEFINED_PALETTES[name])
    assert "QMainWindow" in css
    assert "background-color" in css


def test_derive_palette_picks_light_text_on_dark_base():
    palette = derive_palette_from_base_color("#1A1A2E")  # near-black base
    assert palette.text_on_primary == "#FFFFFF"


def test_derive_palette_picks_dark_text_on_light_base():
    palette = derive_palette_from_base_color("#F5D76E")  # light yellow base
    assert palette.text_on_primary == "#1A1A1A"


def test_user_settings_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = UserSettings(theme_name="Dark", keywords=["MyCompany", "PaymentGatewayService"])
    save_user_settings(settings)

    reloaded = load_user_settings()
    assert reloaded == settings


def test_load_user_settings_returns_defaults_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert load_user_settings() == UserSettings()


def test_load_user_settings_returns_defaults_when_corrupt(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings_dir = tmp_path / "CodeMangler"
    settings_dir.mkdir()
    (settings_dir / "settings.json").write_text("{not valid json", encoding="utf-8")

    assert load_user_settings() == UserSettings()


def test_sanitize_worker_threads_known_terms_into_settings():
    worker = SanitizeWorker(mode="text", input_text="x", known_terms={"MyCompany": "org"})
    settings = worker._build_settings()
    assert settings.known_terms == {"MyCompany": "org"}


def test_known_term_gets_replaced_consistently():
    settings = SanitizeWorker(
        mode="text", input_text="x", known_terms={"MyCompany": "org"}
    )._build_settings()
    generator = FakeValueGenerator()

    sanitized, changes = anonymize_text(
        "contact us at MyCompany for details", settings, generator, language="text"
    )

    assert "MyCompany" not in sanitized
    assert any(c.original == "MyCompany" and c.replacement == "Org001" for c in changes)
