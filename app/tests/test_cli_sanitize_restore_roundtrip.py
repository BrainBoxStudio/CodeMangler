from typer.testing import CliRunner

from app.cli import app

runner = CliRunner()


def test_sanitize_then_restore_recovers_original_byte_for_byte(tmp_path, sample_python_source):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "db.py").write_text(sample_python_source, encoding="utf-8", newline="")

    sanitized_dir = tmp_path / "sanitized"
    map_path = tmp_path / "sanitization_map.json"
    result = runner.invoke(
        app,
        ["sanitize", "--input", str(src_dir), "--output", str(sanitized_dir), "--map", str(map_path)],
    )
    assert result.exit_code == 0, result.output

    sanitized_content = (sanitized_dir / "db.py").read_text(encoding="utf-8", newline="")
    assert "ghp_1234567890abcdef1234567890abcdef1234" not in sanitized_content

    restored_dir = tmp_path / "restored"
    result = runner.invoke(
        app,
        ["restore", "--input", str(sanitized_dir), "--output", str(restored_dir), "--map", str(map_path)],
    )
    assert result.exit_code == 0, result.output

    restored_content = (restored_dir / "db.py").read_text(encoding="utf-8", newline="")
    assert restored_content == sample_python_source


def test_sanitize_then_restore_with_encrypted_map(tmp_path, sample_python_source):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "db.py").write_text(sample_python_source, encoding="utf-8", newline="")

    sanitized_dir = tmp_path / "sanitized"
    map_path = tmp_path / "sanitization_map.json"
    result = runner.invoke(
        app,
        [
            "sanitize",
            "--input",
            str(src_dir),
            "--output",
            str(sanitized_dir),
            "--map",
            str(map_path),
            "--encrypt-map",
            "--password",
            "s3cr3t-pw",
        ],
    )
    assert result.exit_code == 0, result.output

    raw = map_path.read_bytes()
    assert not raw.lstrip().startswith(b"{")  # not plain JSON when encrypted

    restored_dir = tmp_path / "restored"

    failed = runner.invoke(
        app,
        ["restore", "--input", str(sanitized_dir), "--output", str(restored_dir), "--map", str(map_path)],
    )
    assert failed.exit_code != 0  # missing password fails cleanly

    result = runner.invoke(
        app,
        [
            "restore",
            "--input",
            str(sanitized_dir),
            "--output",
            str(restored_dir),
            "--map",
            str(map_path),
            "--password",
            "s3cr3t-pw",
        ],
    )
    assert result.exit_code == 0, result.output
    restored_content = (restored_dir / "db.py").read_text(encoding="utf-8", newline="")
    assert restored_content == sample_python_source


def test_sanitize_text_mode_dry_run_prints_sanitized_text():
    result = runner.invoke(app, ["sanitize", "--text", "password=abc123", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "abc123" not in result.output
    assert "fake_password_001" in result.output


def test_scan_reports_findings_without_printing_original_values(tmp_path, sample_python_source):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "db.py").write_text(sample_python_source, encoding="utf-8", newline="")

    result = runner.invoke(app, ["scan", "--input", str(src_dir)])
    assert result.exit_code == 0, result.output
    assert "ghp_1234567890abcdef1234567890abcdef1234" not in result.output
    assert "github_token" in result.output
