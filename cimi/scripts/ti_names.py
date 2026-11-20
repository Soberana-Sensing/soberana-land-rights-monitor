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
    # dashes and apostrophes become spaces BEFORE the ASCII fold, which would
    # otherwise drop an en dash and glue the two words together (Panambi–Lagoa)
    s = re.sub(r"[-'\u2019\u2013\u2014]", " ", value)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.upper()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


with CONVENTIONS_FILE.open(encoding="utf-8") as fh:
    _CONVENTIONS = yaml.safe_load(fh)

FOCUS_TERRITORIES: list[str] = _CONVENTIONS["focus_territories"]
CIMI_VARIANTS: dict[str, str] = _CONVENTIONS["cimi_variants"]
CIMI_MULTI: dict[str, list[str]] = _CONVENTIONS.get("cimi_multi", {}) or {}
FUNAI_TO_CIMI: dict[str, str] = _CONVENTIONS["funai_to_cimi"]
MENTION_PATTERNS: dict[str, dict] = _CONVENTIONS.get("mention_patterns", {})
MS_CUES: str = _CONVENTIONS.get("ms_cues", r"\bms\b")


def cimi_ti(series: pd.Series) -> pd.Series:
    """Canonical CIMI labels from the raw CIMI TI column."""
    return series.map(norm_ti).replace(CIMI_VARIANTS)


def split_multi_labels(df: pd.DataFrame, col: str = "TI_CLEAN") -> pd.DataFrame:
    """Expand a label naming two territories into one row per territory.

    CIMI prints a single Chapter I record when one article covers two
    territories. The record is real in both, so each gets a row; the raw `TI`
    column keeps the printed spelling. See `cimi_multi` in the YAML.
    """
    if not CIMI_MULTI or col not in df.columns:
        return df
    df = df.copy()
    df["_labels"] = df[col].map(lambda v: CIMI_MULTI.get(v, [v]))
    df = df.explode("_labels", ignore_index=True)
    df[col] = df.pop("_labels")
    return df


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
