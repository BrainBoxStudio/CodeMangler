from app.mapping.restore_engine import restore_text
from app.mapping.schema import ChangeEntry


def _change(**kwargs) -> ChangeEntry:
    defaults = dict(
        id="chg_000001",
        file="sample.py",
        type="secret",
        category="github_token",
        language="python",
        scope="text",
        confidence=0.95,
        detector="regex",
        reversible=True,
    )
    defaults.update(kwargs)
    return ChangeEntry(**defaults)


def test_restore_position_anchored_round_trip():
    sanitized = 'token = "FAKE_GITHUB_TOKEN_001"\n'
    change = _change(
        original="ghp_1234567890abcdef1234567890abcdef1234",
        replacement="FAKE_GITHUB_TOKEN_001",
        start_line=1,
        start_col=10,
        end_line=1,
        end_col=32,
    )
    restored = restore_text(sanitized, [change])
    assert restored == 'token = "ghp_1234567890abcdef1234567890abcdef1234"\n'


def test_restore_falls_back_to_text_match_after_position_drift():
    change = _change(
        original="ghp_1234567890abcdef1234567890abcdef1234",
        replacement="FAKE_GITHUB_TOKEN_001",
        start_line=1,
        start_col=10,
        end_line=1,
        end_col=32,
    )
    # User prepended a line, shifting the token onto line 2 - the recorded
    # position no longer points at the right span, so this exercises the
    # whole-document fallback pass.
    edited = '# added by user\ntoken = "FAKE_GITHUB_TOKEN_001"\n'
    restored = restore_text(edited, [change])
    assert restored == '# added by user\ntoken = "ghp_1234567890abcdef1234567890abcdef1234"\n'


def test_restore_does_not_touch_unrelated_text_sharing_only_a_prefix():
    change = _change(
        original="ghp_1234567890abcdef1234567890abcdef1234",
        replacement="FAKE_GITHUB_TOKEN_001",
        start_line=2,  # intentionally wrong position: forces the fallback pass
        start_col=10,
        end_line=2,
        end_col=32,
    )
    edited = (
        "# user added a comment near the top\n"
        'legacy_constant = "FAKE_GITHUB_TOKEN_001_v2"\n'
    )
    restored = restore_text(edited, [change])
    # FAKE_GITHUB_TOKEN_001 is only a prefix of the unrelated identifier
    # FAKE_GITHUB_TOKEN_001_v2 - the word-boundary fallback must not touch it.
    assert restored == edited


def test_restore_multiple_changes_in_one_file_bottom_to_top():
    sanitized = 'a = "FAKE_ONE_001"\nb = "FAKE_TWO_001"\n'
    changes = [
        _change(
            id="chg_000001",
            category="generic_secret_assignment",
            original="original-one",
            replacement="FAKE_ONE_001",
            start_line=1,
            start_col=6,
            end_line=1,
            end_col=18,
        ),
        _change(
            id="chg_000002",
            category="generic_secret_assignment",
            original="original-two",
            replacement="FAKE_TWO_001",
            start_line=2,
            start_col=6,
            end_line=2,
            end_col=18,
        ),
    ]
    restored = restore_text(sanitized, changes)
    assert restored == 'a = "original-one"\nb = "original-two"\n'
