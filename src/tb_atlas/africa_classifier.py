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


# Lazy-built broad lookup map from iso3166 (name + apolitical_name +
# common short forms). Built once at first call.
_BROAD_LOOKUP: dict | None = None


def _build_broad_lookup() -> dict:
    """Build a comprehensive {lowercase-name: alpha2} map from iso3166 plus
    common short forms used by AACT facilities.country.
    """
    m: dict[str, str] = {}
    try:
        from iso3166 import countries
        for c in countries:
            m[c.name.lower()] = c.alpha2
            if hasattr(c, "apolitical_name") and c.apolitical_name:
                m[c.apolitical_name.lower()] = c.alpha2
    except ImportError:
        pass

    # Common AACT short forms not covered by iso3166's official names.
    short_forms = {
        "moldova": "MD",
        "russia": "RU",
        "russian federation": "RU",
        "czech republic": "CZ",
        "czechia": "CZ",
        "vietnam": "VN",
        "viet nam": "VN",
        "south korea": "KR",
        "korea, south": "KR",
        "north korea": "KP",
        "korea, north": "KP",
        "korea, democratic peoples republic of": "KP",
        "taiwan": "TW",
        "hong kong": "HK",
        "macao": "MO",
        "macau": "MO",
        "iran": "IR",
        "iran, islamic republic of": "IR",
        "syria": "SY",
        "syrian arab republic": "SY",
        "macedonia": "MK",
        "north macedonia": "MK",
        "the former yugoslav republic of macedonia": "MK",
        "bolivia": "BO",
        "bolivia, plurinational state of": "BO",
        "venezuela": "VE",
        "venezuela, bolivarian republic of": "VE",
        "tanzania": "TZ",
        "tanzania, united republic of": "TZ",
        "congo, the democratic republic of the": "CD",
        "congo, democratic republic of the": "CD",
        "democratic republic of the congo": "CD",
        "drc": "CD",
        "republic of the congo": "CG",
        "lao peoples democratic republic": "LA",
        "laos": "LA",
        "palestinian territory": "PS",
        "palestinian territory, occupied": "PS",
        "palestine": "PS",
        "brunei": "BN",
        "brunei darussalam": "BN",
        "east timor": "TL",
        "timor-leste": "TL",
        "micronesia": "FM",
        "micronesia, federated states of": "FM",
        "myanmar": "MM",
        "burma": "MM",
        "cape verde": "CV",
        "cabo verde": "CV",
        "swaziland": "SZ",
        "eswatini": "SZ",
    }
    m.update(short_forms)
    return m


def _to_alpha2(name: str) -> str:
    if not name or not isinstance(name, str):
        raise UnknownCountryError(f"empty country: {name!r}")
    key = name.strip().lower()
    # Strip parenthetical aliases (real AACT has e.g. "Turkey (Türkiye)").
    if "(" in key:
        import re
        key = re.sub(r"\s*\([^)]*\)\s*", " ", key).strip()
    # Normalise Unicode accented chars for the alias lookup.
    key_ascii = (
        key
        .replace("ô", "o")
        .replace("é", "e")
        .replace("è", "e")
        .replace("à", "a")
        .replace("â", "a")
        .replace("’", "'")
        .replace("ã", "a")
        .replace("ü", "u")
        .replace("ö", "o")
        .replace("ñ", "n")
        .replace("í", "i")
        .replace("á", "a")
        .replace("ó", "o")
        .replace("ç", "c")
    )
    if key_ascii in ALIAS:
        return ALIAS[key_ascii]
    if key in ALIAS:
        return ALIAS[key]
    # Broad fallback: iso3166 names + apolitical_names + common short forms.
    global _BROAD_LOOKUP
    if _BROAD_LOOKUP is None:
        _BROAD_LOOKUP = _build_broad_lookup()
    if key_ascii in _BROAD_LOOKUP:
        return _BROAD_LOOKUP[key_ascii]
    if key in _BROAD_LOOKUP:
        return _BROAD_LOOKUP[key]
    # Final attempt: iso3166's exact getter (covers a few edge cases).
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
