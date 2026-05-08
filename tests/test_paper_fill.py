"""Smoke tests for paper fill + validators (Task 29)."""
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent


def _fill_body() -> None:
    """Run fill_paper_placeholders.py to produce body.md from fixture atlas."""
    subprocess.check_call(
        [
            sys.executable,
            "scripts/fill_paper_placeholders.py",
            "--template",
            "e156-submission/body.template.md",
            "--atlas",
            "tests/fixtures/atlas_baseline_micro.csv",
            "--out",
            "e156-submission/body.md",
        ],
        cwd=REPO,
    )


def test_fill_produces_body_md_with_no_unexpected_placeholders():
    """All known placeholders except the allowed pair are resolved."""
    out_path = REPO / "e156-submission/body.md"
    r = subprocess.run(
        [
            sys.executable,
            "scripts/fill_paper_placeholders.py",
            "--template",
            "e156-submission/body.template.md",
            "--atlas",
            "tests/fixtures/atlas_baseline_micro.csv",
            "--out",
            str(out_path),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, f"fill failed: {r.stderr}"
    text = out_path.read_text(encoding="utf-8")
    unresolved = set(re.findall(r"\{\{[A-Z0-9_]+\}\}", text))
    # SPOTCHECK and SNAPSHOT_DATE are intentionally unresolved in dev mode
    # (Task 27 fills SNAPSHOT_DATE via --snapshot-meta; Task 32 fills SPOTCHECK)
    allowed_unresolved = {"{{SPOTCHECK_AGREE_N}}", "{{SPOTCHECK_TOTAL}}"}
    leftover = unresolved - allowed_unresolved
    assert not leftover, f"unexpected unresolved placeholders: {leftover}"


def test_body_template_has_seven_sentences():
    """E156 protocol: exactly 7 sentences (one per line in this template)."""
    template = (REPO / "e156-submission/body.template.md").read_text(
        encoding="utf-8"
    )
    sentences = [s for s in template.strip().split("\n") if s.strip()]
    assert len(sentences) == 7, f"expected 7 sentences, got {len(sentences)}"


def test_body_filled_word_count_under_156():
    """Post-fill body must be ≤156 words (E156 hard ceiling)."""
    body_path = REPO / "e156-submission/body.md"
    if not body_path.exists():
        _fill_body()
    text = body_path.read_text(encoding="utf-8")
    # Strip unresolved placeholders before counting (they inflate by 1 word each)
    clean = re.sub(r"\{\{[A-Z0-9_]+\}\}", "TBD", text).strip()
    word_count = len(clean.split())
    assert word_count <= 156, (
        f"body.md has {word_count} words after placeholder-strip; target ≤156"
    )


def test_methods_note_template_under_400_words():
    """Synthesis methods note template must be ≤400 words."""
    template = (REPO / "e156-submission/synthesis-methods-note.md").read_text(
        encoding="utf-8"
    )
    word_count = len(template.split())
    assert word_count <= 400, (
        f"synthesis-methods-note.md has {word_count} words; target ≤400"
    )


def test_validate_e156_body_runs_without_crash():
    """validate_e156_body.py must execute without ImportError or SyntaxError."""
    body_path = REPO / "e156-submission/body.md"
    if not body_path.exists():
        _fill_body()
    r = subprocess.run(
        [sys.executable, "scripts/validate_e156_body.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    # Validator may return non-zero if unresolved placeholders remain (Task 32).
    # We only require it ran (no import crash) and produced diagnostic output.
    combined = (r.stdout + r.stderr).lower()
    assert "sentences" in combined or "words" in combined or "unfilled" in combined, (
        f"validator produced unexpected output (exit {r.returncode}):\n"
        f"stdout={r.stdout!r}\nstderr={r.stderr!r}"
    )


def test_fill_script_fails_on_missing_atlas():
    """fill_paper_placeholders.py must exit non-zero if atlas is missing."""
    r = subprocess.run(
        [
            sys.executable,
            "scripts/fill_paper_placeholders.py",
            "--template",
            "e156-submission/body.template.md",
            "--atlas",
            "tests/fixtures/NONEXISTENT_atlas.csv",
            "--out",
            "e156-submission/body_should_not_exist.md",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0, "expected non-zero exit for missing atlas"
    assert not (REPO / "e156-submission/body_should_not_exist.md").exists()


def test_fill_script_fails_on_missing_template():
    """fill_paper_placeholders.py must exit non-zero if template is missing."""
    r = subprocess.run(
        [
            sys.executable,
            "scripts/fill_paper_placeholders.py",
            "--template",
            "e156-submission/NONEXISTENT_template.md",
            "--atlas",
            "tests/fixtures/atlas_baseline_micro.csv",
            "--out",
            "e156-submission/body_should_not_exist2.md",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0, "expected non-zero exit for missing template"
