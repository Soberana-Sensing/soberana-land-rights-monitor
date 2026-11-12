"""Territory-name conventions, shared by every script and the notebook.

Reads config/ti_names.yaml for the name data; the normalisation rules live here.
Canonical labels are the normalised CIMI spellings (UPPERCASE, no accents).
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONVENTIONS_FILE = ROOT / "config" / "ti_names.yaml"


def norm_ti(value: object) -> object:
    """Normalise any TI spelling to a matching key. Non-strings pass through."""
    if not isinstance(value, str):
        return value
    s = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    s = s.upper()
    s = re.sub(r"[-'\u2019]", " ", s)   # hyphens and apostrophes become spaces
    s = re.sub(r"\s+", " ", s)
    return s.strip()


with CONVENTIONS_FILE.open(encoding="utf-8") as fh:
    _CONVENTIONS = yaml.safe_load(fh)

FOCUS_TERRITORIES: list[str] = _CONVENTIONS["focus_territories"]
CIMI_VARIANTS: dict[str, str] = _CONVENTIONS["cimi_variants"]
FUNAI_TO_CIMI: dict[str, str] = _CONVENTIONS["funai_to_cimi"]


def cimi_ti(series: pd.Series) -> pd.Series:
    """Canonical CIMI labels from the raw CIMI TI column."""
    return series.map(norm_ti).replace(CIMI_VARIANTS)


def funai_ti(series: pd.Series) -> pd.Series:
    """Canonical CIMI labels from FUNAI's terrai_nom."""
    return series.map(norm_ti).replace(FUNAI_TO_CIMI)
