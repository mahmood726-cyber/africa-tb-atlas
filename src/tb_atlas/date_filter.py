"""Filter trials to start_date >= 2012-12-28 (bedaquiline FDA-EUA)."""
from __future__ import annotations
import pandas as pd

BEDAQUILINE_EUA_DATE = pd.Timestamp("2012-12-28")


def is_modern_era(start_date) -> bool:
    if pd.isna(start_date):
        return False
    return pd.Timestamp(start_date) >= BEDAQUILINE_EUA_DATE
