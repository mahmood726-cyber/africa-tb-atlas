"""Classify a trial's country list into Africa-recruiting status.

Three outputs per trial (per spec §1.6 #5-7):
- africa_recruiting (bool, >=1 African site) -- HEADLINE
- site_share_30pct (bool, >=30% African sites) -- pre-registered SENSITIVITY
- africa_tier (3-tier enum) -- Section-3 SUB-ANALYSIS

ISO-3166 alpha-2 only. No fuzzy matching. Unknown country -> fail closed.
"""
from __future__ import annotations
from enum import Enum

# 54 African countries (ISO-3166 alpha-2). Hardcoded for reproducibility
# and so the test suite can verify exact-set membership.
AFRICAN_ALPHA2 = frozenset({
    "DZ", "AO", "BJ", "BW", "BF", "BI", "CM", "CV", "CF", "TD",
    "KM", "CG", "CD", "CI", "DJ", "EG", "GQ", "ER", "ET", "GA",
    "GM", "GH", "GN", "GW", "KE", "LS", "LR", "LY", "MG", "MW",
    "ML", "MR", "MU", "MA", "MZ", "NA", "NE", "NG", "RW", "ST",
    "SN", "SC", "SL", "SO", "ZA", "SS", "SD", "SZ", "TZ", "TG",
    "TN", "UG", "ZM", "ZW",
})

# Curated alias map (free-text country strings -> ISO alpha-2). Build out as
# real data exposes new spellings. Lower-case keys for case-insensitive lookup.
ALIAS = {
    # African countries
    "south africa": "ZA",
    "kenya": "KE",
    "uganda": "UG",
    "tanzania": "TZ",
    "ethiopia": "ET",
    "nigeria": "NG",
    "ghana": "GH",
    "egypt": "EG",
    "democratic republic of the congo": "CD",
    "drc": "CD",
    "republic of the congo": "CG",
    "congo": "CG",
    "eswatini": "SZ",
    "swaziland": "SZ",
    "cote d'ivoire": "CI",
    "ivory coast": "CI",
    "morocco": "MA",
    "tunisia": "TN",
    "zambia": "ZM",
    "zimbabwe": "ZW",
    "malawi": "MW",
    "mozambique": "MZ",
    "namibia": "NA",
    "lesotho": "LS",
    "botswana": "BW",
    "rwanda": "RW",
    "burundi": "BI",
    "senegal": "SN",
    "mali": "ML",
    "burkina faso": "BF",
    "niger": "NE",
    "south sudan": "SS",
    "sudan": "SD",
    "somalia": "SO",
    "djibouti": "DJ",
    "eritrea": "ER",
    "cameroon": "CM",
    "gabon": "GA",
    "central african republic": "CF",
    "chad": "TD",
    "angola": "AO",
    "madagascar": "MG",
    "mauritius": "MU",
    "seychelles": "SC",
    "comoros": "KM",
    "cape verde": "CV",
    "cabo verde": "CV",
    "guinea": "GN",
    "guinea-bissau": "GW",
    "equatorial guinea": "GQ",
    "liberia": "LR",
    "sierra leone": "SL",
    "togo": "TG",
    "benin": "BJ",
    "gambia": "GM",
    "mauritania": "MR",
    "libya": "LY",
    "algeria": "DZ",
    "western sahara": "EH",
    "sao tome and principe": "ST",
    # Common non-African (subset, for tests; extend as data demands)
    "united states": "US",
    "united kingdom": "GB",
    "germany": "DE",
    "france": "FR",
    "russia": "RU",
    "russian federation": "RU",
    "belarus": "BY",
    "uzbekistan": "UZ",
    "china": "CN",
    "india": "IN",
    "brazil": "BR",
    "japan": "JP",
    "south korea": "KR",
    "korea, republic of": "KR",
    "spain": "ES",
    "italy": "IT",
    "canada": "CA",
    "australia": "AU",
    "argentina": "AR",
    "mexico": "MX",
    "thailand": "TH",
    "vietnam": "VN",
    "philippines": "PH",
    "indonesia": "ID",
    "pakistan": "PK",
    "bangladesh": "BD",
    "turkey": "TR",
    "ukraine": "UA",
    "poland": "PL",
}


class AfricaTier(str, Enum):
    AFRICAN_LED = "African-led"
    AFRICAN_RECRUITING = "African-recruiting"
    NON_AFRICA = "non-Africa"


class UnknownCountryError(Exception):
    """Raised when a country string cannot be resolved to ISO-3166 alpha-2."""


def _to_alpha2(name: str) -> str:
    if not name or not isinstance(name, str):
        raise UnknownCountryError(f"empty country: {name!r}")
    key = name.strip().lower()
    # Normalise Unicode accented chars for the alias lookup (e.g. Cote d'Ivoire
    # with macron over the e -> plain ascii for dict key comparison).
    # We keep it simple: strip the macron variant via a targeted replacement so
    # the alias dict only needs one key per entry.
    key_ascii = (
        key
        .replace("ô", "o")   # o with circumflex: Cote
        .replace("é", "e")   # e with acute
        .replace("è", "e")   # e with grave
        .replace("à", "a")   # a with grave
        .replace("â", "a")   # a with circumflex
        .replace("’", "'")   # right single quotation mark
        .replace("ã", "a")   # a with tilde (Sao Tome)
    )
    if key_ascii in ALIAS:
        return ALIAS[key_ascii]
    if key in ALIAS:
        return ALIAS[key]
    # Fall through to iso3166 package
    try:
        from iso3166 import countries
        c = countries.get(name.strip())
        return c.alpha2
    except (KeyError, ImportError, AttributeError):
        raise UnknownCountryError(f"unrecognised country: {name!r}")


def classify_africa(country_list) -> dict:
    """Classify a list of country strings into Africa-recruiting status.

    Args:
        country_list: list[str] of country names.

    Returns:
        dict with keys: africa_recruiting (bool), africa_site_share (float
        in [0,1]), site_share_30pct (bool), africa_tier (AfricaTier),
        n_african_sites (int), n_total_sites (int).
    """
    if not country_list:
        return {
            "africa_recruiting": False,
            "africa_site_share": 0.0,
            "site_share_30pct": False,
            "africa_tier": AfricaTier.NON_AFRICA,
            "n_african_sites": 0,
            "n_total_sites": 0,
        }

    codes = [_to_alpha2(c) for c in country_list]
    african = [c for c in codes if c in AFRICAN_ALPHA2]
    n_a, n_t = len(african), len(codes)
    share = float(n_a) / float(n_t) if n_t > 0 else 0.0

    if n_a == 0:
        tier = AfricaTier.NON_AFRICA
    elif share >= 0.5:
        tier = AfricaTier.AFRICAN_LED
    else:
        tier = AfricaTier.AFRICAN_RECRUITING

    return {
        "africa_recruiting": n_a >= 1,
        "africa_site_share": share,
        "site_share_30pct": share >= 0.30,
        "africa_tier": tier,
        "n_african_sites": n_a,
        "n_total_sites": n_t,
    }
