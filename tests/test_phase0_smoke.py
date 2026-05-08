"""Phase 0 sanity: scaffolding + prereg discipline + snapshot integrity in place."""
from pathlib import Path
import json
import subprocess

REPO = Path(__file__).parent.parent


def test_scaffold_files_exist():
    """Task 1 + 2 deliverables present."""
    for f in [
        "README.md", "LICENSE", "pyproject.toml", ".gitignore",
        "paths.toml.example",
        "docs/spec.md", "docs/protocol.md",
        "docs/AMENDMENTS.md", "docs/extraction_audit.md",
    ]:
        assert (REPO / f).exists(), f"missing {f}"


def test_prereg_manifest_present_and_pure():
    """prereg_manifest.json must be {relpath: sha256} only — no metadata keys
    (metadata lives in prereg_meta.json so verify_prereg.py treats every
    manifest key as a relpath without special-casing)."""
    m = REPO / "data/snapshots/prereg_manifest.json"
    assert m.exists()
    data = json.loads(m.read_text(encoding="utf-8"))
    expected = {"docs/spec.md", "docs/protocol.md", "docs/AMENDMENTS.md"}
    assert set(data.keys()) == expected, f"manifest keys drifted: {set(data.keys())}"
    for sha in data.values():
        assert isinstance(sha, str) and len(sha) == 64, f"bad sha256: {sha!r}"


def test_prereg_meta_present():
    """Task 4 prereg metadata: GitHub tag + IA URLs."""
    m = REPO / "data/snapshots/prereg_meta.json"
    assert m.exists()
    data = json.loads(m.read_text(encoding="utf-8"))
    for key in ["tag", "tag_target_commit", "github_repo", "created_at", "mechanism"]:
        assert key in data, f"prereg_meta.json missing {key}"
    assert data["tag"] == "prereg-v0.0.1"
    assert "GitHub" in data["mechanism"]
    assert "Internet Archive" in data["mechanism"]


def test_ia_snapshots_recorded():
    """5 Internet Archive Wayback URLs must be recorded."""
    m = REPO / "data/snapshots/internet_archive_prereg.json"
    assert m.exists()
    data = json.loads(m.read_text(encoding="utf-8"))
    assert "snapshots" in data
    snaps = data["snapshots"]
    expected = {"github_repo_root", "github_tag_tree", "spec_md", "protocol_md", "amendments_md"}
    assert set(snaps.keys()) == expected, f"IA snapshot keys drifted: {set(snaps.keys())}"
    for name, info in snaps.items():
        assert info["wayback_url"].startswith("https://web.archive.org/web/")
        assert "wayback_timestamp" in info


def test_verify_prereg_passes():
    """scripts/verify_prereg.py must report OK."""
    result = subprocess.run(
        ["python", "scripts/verify_prereg.py",
         "--manifest", "data/snapshots/prereg_manifest.json",
         "--root", "."],
        cwd=REPO, capture_output=True, text=True
    )
    assert result.returncode == 0, f"verify_prereg failed: {result.stderr}"
    assert "OK:" in result.stdout


def test_snapshot_metadata_complete():
    """Each of {aact, ictrp, pairwise70, cdsr} has a metadata JSON
    with sha256 + source + path + n_rows."""
    for src in ["aact", "ictrp", "pairwise70", "cdsr"]:
        meta = REPO / f"data/snapshots/{src}_metadata.json"
        assert meta.exists(), f"missing {src} metadata"
        m = json.loads(meta.read_text(encoding="utf-8"))
        for key in ["source", "snapshot_path", "sha256", "fetched_at", "n_rows"]:
            assert key in m, f"{src} missing {key}"
        assert m["source"] == src
        assert len(m["sha256"]) == 64


def test_ictrp_placeholder_warning_present():
    """ictrp_metadata.json must explicitly flag that this is a PACTR-scoped
    placeholder, not the full WHO ICTRP weekly export — to be replaced
    before Task 27 real run."""
    m = json.loads((REPO / "data/snapshots/ictrp_metadata.json").read_text(encoding="utf-8"))
    notes = m.get("notes", "").lower()
    assert "pactr" in notes or "placeholder" in notes or "not the full" in notes, \
        f"ictrp_metadata.json must warn about the placeholder; got: {m.get('notes', '')!r}"


def test_install_sentinel_hook_default_warn():
    """Task 5 install script must default to warn mode (not block)."""
    sh = (REPO / "scripts/install_sentinel_hook.sh").read_text(encoding="utf-8")
    # The line that picks the mode default — should resolve to "warn" with no override.
    # Look for the Bash parameter-expansion default.
    assert "${SENTINEL_MODE:-warn}" in sh, \
        f"install script default should be warn (line: SENTINEL_MODE:-warn). Got:\n{sh}"


def test_prereregistration_commit_anchor_present():
    """The .preregistration_commit.txt anchor must exist (Task 5)."""
    anchor = REPO / ".preregistration_commit.txt"
    assert anchor.exists()
    text = anchor.read_text(encoding="utf-8")
    assert "prereg-v0.0.1" in text
    assert "GitHub" in text and "Internet Archive" in text  # mechanism documented
