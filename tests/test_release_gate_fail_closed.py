"""A failed executable check must prevent a successful release dry-run."""
import importlib.util
from pathlib import Path
import subprocess


def test_failed_check_propagates_nonzero_exit(tmp_path, monkeypatch, capsys):
    path = Path(__file__).resolve().parents[1] / "scripts/release_v010.py"
    spec = importlib.util.spec_from_file_location("release_gate", path)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    monkeypatch.setattr(gate, "REPO", tmp_path)
    monkeypatch.setattr(gate, "run_python", lambda *args: subprocess.CompletedProcess(args, 1, "", "fixture failure"))
    assert gate.main() == 1
    output = capsys.readouterr().out
    assert "[FAIL] (h)" in output
    assert "Release is BLOCKED" in output
