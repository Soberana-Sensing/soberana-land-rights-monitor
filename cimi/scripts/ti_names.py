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
    s = re.sub(r"[-'\u2019\u2013\u2014]", " ", s)   # hyphens, en/em dashes, apostrophes become spaces
    s = re.sub(r"\s+", " ", s)
    return s.strip()


with CONVENTIONS_FILE.open(encoding="utf-8") as fh:
    _CONVENTIONS = yaml.safe_load(fh)

FOCUS_TERRITORIES: list[str] = _CONVENTIONS["focus_territories"]
CIMI_VARIANTS: dict[str, str] = _CONVENTIONS["cimi_variants"]
FUNAI_TO_CIMI: dict[str, str] = _CONVENTIONS["funai_to_cimi"]
MENTION_PATTERNS: dict[str, dict] = _CONVENTIONS.get("mention_patterns", {})
MS_CUES: str = _CONVENTIONS.get("ms_cues", r"\bms\b")


def cimi_ti(series: pd.Series) -> pd.Series:
    """Canonical CIMI labels from the raw CIMI TI column."""
    return series.map(norm_ti).replace(CIMI_VARIANTS)


def funai_ti(series: pd.Series) -> pd.Series:
    """Canonical CIMI labels from FUNAI's terrai_nome."""
    return series.map(norm_ti).replace(FUNAI_TO_CIMI)


# FUNAI legal stages are Portuguese in the download; figures read in English.
STAGE_LABELS = {
    "em estudo": "under study",
    "delimitada": "delimitation",
    "declarada": "declaration",
    "homologada": "ratification",
    "regularizada": "regularisation",
}


def stage_en(stage: object) -> str:
    """English label for a FUNAI stage; unknown values pass through unchanged."""
    if not isinstance(stage, str) or not stage.strip():
        return ""
    return STAGE_LABELS.get(stage.strip().lower(), stage.strip())
