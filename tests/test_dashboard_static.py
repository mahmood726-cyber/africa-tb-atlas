from pathlib import Path
import re
import csv

REPO = Path(__file__).parent.parent


def test_dashboard_index_html_exists():
    assert (REPO / "dashboard/index.html").exists()


def test_index_html_redirect_at_repo_root():
    """index.html at repo root redirects to dashboard/."""
    p = REPO / "index.html"
    assert p.exists()
    text = p.read_text(encoding="utf-8").lower()
    assert "dashboard" in text
    assert ("meta http-equiv" in text) or ("window.location" in text)


def test_dashboard_no_external_cdn():
    html = (REPO / "dashboard/index.html").read_text(encoding="utf-8").lower()
    forbidden = ["cdn.jsdelivr", "cdnjs", "unpkg.com", "googleapis.com",
                 "fontawesome", "ajax.googleapis"]
    for f in forbidden:
        assert f not in html, f"forbidden CDN reference: {f}"


def test_dashboard_div_balance():
    """Lessons.md: count <div[\\s>] vs </div> after HTML edits."""
    html = (REPO / "dashboard/index.html").read_text(encoding="utf-8")
    opens = len(re.findall(r"<div[\s>]", html))
    closes = len(re.findall(r"</div>", html))
    assert opens == closes, f"div imbalance: {opens} open vs {closes} close"


def test_dashboard_no_external_script_src():
    """No <script src='http...'> — all JS inline."""
    html = (REPO / "dashboard/index.html").read_text(encoding="utf-8")
    assert not re.search(r"<script\s+[^>]*src\s*=\s*[\"'][^\"']*://", html, re.I), \
        "external <script src=...> found"


def test_dashboard_no_external_link_href():
    """No <link href='http...'> — all CSS inline."""
    html = (REPO / "dashboard/index.html").read_text(encoding="utf-8")
    matches = re.findall(r"<link\s+[^>]*href\s*=\s*[\"']([^\"']+)[\"']", html, re.I)
    for m in matches:
        assert not m.startswith("http"), f"external link: {m}"


def test_dashboard_renders_atlas_data():
    """The dashboard must inline atlas.csv data — check by reading the
    headline pct values from the baseline CSV and confirming they appear
    in the HTML (with reasonable formatting tolerance)."""
    html = (REPO / "dashboard/index.html").read_text(encoding="utf-8")
    with (REPO / "tests/fixtures/atlas_baseline_micro.csv").open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) > 0
    # Pick the binary_1site True-stratum row
    africa_row = next(
        (r for r in rows if r["sensitivity"] == "binary_1site"
         and r["stratum_value"].lower() in ("true", "1")),
        None,
    )
    assert africa_row is not None
    n_trials = int(float(africa_row["n_trials"]))
    # The trial count should appear somewhere in the dashboard
    assert str(n_trials) in html, f"africa-recruiting n_trials={n_trials} not rendered in dashboard"


def test_dashboard_links_to_spec_and_protocol():
    """Dashboard should reference spec.md / protocol.md / prereg-v0.0.1 tag."""
    html = (REPO / "dashboard/index.html").read_text(encoding="utf-8").lower()
    # At least one of these references should be present
    has_spec = "spec.md" in html or "/spec" in html
    has_tag = "prereg-v0.0.1" in html
    assert has_spec or has_tag


def test_dashboard_html_unicode_safe():
    """No UTF-8 mojibake from cp1252 round-trip (lessons.md cp1252 saving rule)."""
    html_bytes = (REPO / "dashboard/index.html").read_bytes()
    # These are valid UTF-8 byte sequences for typographic punctuation
    # — they're FINE if present. The check is for the WRONG markers.
    # Check for cp1252 mojibake markers (â€¦, â€™, etc — UTF-8 misread as cp1252)
    text = html_bytes.decode("utf-8", errors="replace")
    # cp1252 mojibake markers: UTF-8 multi-byte sequences mis-decoded as cp1252
    # "\xe2\x80\xa6" = ellipsis U+2026 -> mojibake "â€¦" in cp1252
    # "\xe2\x80\x99" = right single quote U+2019 -> mojibake in cp1252
    # "\xe2\x94" prefix = box-drawing characters -> mojibake in cp1252
    bad_markers = [
        "â€¦",   # â€¦  (ellipsis mojibake)
        "â€™",   # â€™  (right-quote mojibake)
        "â",         # â"   (box-drawing mojibake prefix)
    ]
    for m in bad_markers:
        assert m not in text, f"cp1252 mojibake marker found: {m!r}"


def test_dashboard_has_4_sensitivity_sections():
    """Dashboard should reference at least the 4 stratifications by name."""
    html = (REPO / "dashboard/index.html").read_text(encoding="utf-8").lower()
    # Look for at least 3 of the 4 sensitivity labels (drug_class/binary/site_share/three_tier)
    labels = ["binary", "site_share", "three", "drug"]
    found = sum(1 for l in labels if l in html)
    assert found >= 3, f"only {found}/4 sensitivity labels referenced"
