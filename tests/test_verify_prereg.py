import json
import subprocess
import hashlib
from pathlib import Path

def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def test_verify_prereg_matches_stamped_sha(tmp_path: Path):
    # Setup: a "spec" file + a "prereg manifest" recording its sha256
    spec = tmp_path / "spec.md"
    spec.write_text("# locked content\n", encoding="utf-8")
    manifest = tmp_path / "prereg_manifest.json"
    manifest.write_text(json.dumps({"spec.md": _sha256(spec)}), encoding="utf-8")

    repo_root = Path(__file__).parent.parent
    result = subprocess.run(
        ["python", str(repo_root / "scripts/verify_prereg.py"),
         "--manifest", str(manifest), "--root", str(tmp_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout

def test_verify_prereg_fails_on_drift(tmp_path: Path):
    spec = tmp_path / "spec.md"
    spec.write_text("# locked content\n", encoding="utf-8")
    manifest = tmp_path / "prereg_manifest.json"
    manifest.write_text(json.dumps({"spec.md": _sha256(spec)}), encoding="utf-8")
    # Drift: modify spec AFTER manifest
    spec.write_text("# modified content\n", encoding="utf-8")
    repo_root = Path(__file__).parent.parent
    result = subprocess.run(
        ["python", str(repo_root / "scripts/verify_prereg.py"),
         "--manifest", str(manifest), "--root", str(tmp_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "DRIFT" in result.stdout or "DRIFT" in result.stderr
