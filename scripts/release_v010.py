"""Portable v0.1.0 dry-run gate; skipped research prerequisites remain pending."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]


def run_python(*args):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(REPO / "src"), env.get("PYTHONPATH", "")])
    return subprocess.run([sys.executable, *map(str, args)], cwd=REPO, env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120)


def main():
    counts = {"PASS": 0, "SKIP": 0, "FAIL": 0}

    def step(label, command=None, skip=None, check=None):
        if skip is not None:
            status, detail = "SKIP", skip
        else:
            try:
                if command is not None:
                    result = run_python(*command)
                    if result.returncode:
                        raise RuntimeError(result.stdout + result.stderr)
                else:
                    check()
                status, detail = "PASS", ""
            except (OSError, ValueError, KeyError, AssertionError, RuntimeError, subprocess.TimeoutExpired) as exc:
                status, detail = "FAIL", str(exc)
        counts[status] += 1
        print(f"[{status}] {label}" + (f": {detail}" if detail else ""), flush=True)

    print("africa-tb-atlas v0.1.0 dry-run preconditions")
    with tempfile.TemporaryDirectory() as temporary:
        temp = Path(temporary)
        config = REPO / "paths.toml"
        if not config.exists():
            config = temp / "paths.toml"
            paths = {
                "aact_snapshot_dir": REPO / "tests/fixtures/aact_50trial",
                "ictrp_snapshot": REPO / "tests/fixtures/ictrp_30trial.csv",
                "pairwise70_index": REPO / "tests/fixtures/pairwise70_micro.parquet",
                "cdsr_string_index": REPO / "tests/fixtures/cdsr_string_micro.sqlite",
                "europe_pmc_cache_dir": temp / "cache",
            }
            config.write_text("\n".join(f'{k} = {json.dumps(v.as_posix())}' for k, v in paths.items()), encoding="utf-8")
        step("(a) preflight", ["-m", "pilots.preflight", "--paths-toml", config, "--micro"])
        step("(b) verify_prereg", ["scripts/verify_prereg.py", "--manifest", "data/snapshots/prereg_manifest.json", "--root", "."])

        atlas = REPO / "atlas.csv"
        baseline = REPO / "data/snapshots/output_baselines.json"
        def check_baseline():
            expected = json.loads(baseline.read_text(encoding="utf-8"))["atlas.csv"]
            if hashlib.sha256(atlas.read_bytes()).hexdigest() != expected:
                raise ValueError("atlas.csv differs from its recorded baseline")
        step("(c) atlas.csv sha256 baseline match", check=check_baseline,
             skip="atlas.csv absent" if not atlas.exists() else None)

        trials = REPO / "data/output/trials.parquet"
        spotcheck = REPO / "data/processed/spotcheck_v0.1.0.csv"
        step("(d) validation_gates", ["scripts/validation_gates.py", "--trials", trials, "--spotcheck", spotcheck],
             skip="trials.parquet and/or spotcheck absent" if not (trials.exists() and spotcheck.exists()) else None)

        body = REPO / "e156-submission/body.md"
        body_pending = not body.exists() or "{{" in body.read_text(encoding="utf-8")
        step("(e) validate_e156_body", ["scripts/validate_e156_body.py"],
             skip="body absent or contains unfilled placeholders" if body_pending else None)

        template = REPO / "e156-submission/synthesis-methods-note.md"
        filled = REPO / "e156-submission/synthesis-methods-note.filled.md"
        fill_atlas = atlas if atlas.exists() else REPO / "tests/fixtures/atlas_baseline_micro.csv"
        def check_note():
            nonlocal filled
            if not filled.exists():
                filled = temp / "synthesis-methods-note.md"
                result = run_python("scripts/fill_paper_placeholders.py", "--template", template,
                                    "--atlas", fill_atlas, "--out", filled)
                if result.returncode:
                    raise RuntimeError(result.stdout + result.stderr)
            clean = re.sub(r"<!--.*?-->", "", filled.read_text(encoding="utf-8"), flags=re.S).strip()
            if "{{" in clean or "}}" in clean:
                return False
            if len(clean.split()) > 400:
                raise ValueError("synthesis note exceeds 400 words")
            return True
        if not template.exists() or not fill_atlas.exists():
            step("(f) validate_synthesis_note", skip="template or atlas absent")
        else:
            try:
                ready = check_note()
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
                counts["FAIL"] += 1
                print(f"[FAIL] (f) validate_synthesis_note: {exc}")
            else:
                step("(f) validate_synthesis_note", check=lambda: None,
                     skip="unfilled placeholders remain" if not ready else None)

        step("(g) dashboard tests", ["-m", "pytest", "tests/test_dashboard_static.py", "-q"])
        step("(h) Sentinel BLOCK=0", ["-m", "sentinel", "scan", "--repo", "."])

    print("\nSummary")
    for status, count in counts.items():
        print(f"  {status}: {count}")
    if counts["FAIL"]:
        print("Release is BLOCKED until failed preconditions pass.")
        return 1
    if counts["SKIP"]:
        print("Dry-run OK so far; release remains pending skipped prerequisites.")
    else:
        print("All preconditions PASS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
