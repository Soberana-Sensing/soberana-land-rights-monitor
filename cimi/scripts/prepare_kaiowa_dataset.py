"""Build the CIMI Kaiowá analysis datasets and the focus-territory extracts.

Input : data/derived/chapter1_conflicts.csv           (chapter1_txt_to_csv.py)
        data/derived/funai_territorial_inventory_ms.csv (build_funai_inventory.py)
        data/derived/funai_kaiowa_ms_clipped.geojson    (build_funai_inventory.py)
Output: data/derived/cimi_kaiowa_ms_conflicts.csv
        data/derived/cimi_kaiowa_ms_conflicts_focus5.csv
        data/derived/funai_focus5_inventory.csv
        data/derived/funai_focus5_territories.geojson

Adds TI_CLEAN to both sides using the conventions in config/ti_names.yaml, then
reports which territory names exist on only one side. The focus-5 outputs are
the inputs for the later MapBiomas and Sentinel-1 analyses; they carry the
territory polygons, the FUNAI attributes and the CIMI conflict cases.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

import ti_names
from ti_names import FOCUS_TERRITORIES, cimi_ti, funai_ti

ROOT = Path(__file__).resolve().parents[1]
CONFLICTS = ROOT / "data/derived/chapter1_conflicts.csv"
INVENTORY = ROOT / "data/derived/funai_territorial_inventory_ms.csv"
CLIPPED = ROOT / "data/derived/funai_kaiowa_ms_clipped.geojson"

OUT_ALL = ROOT / "data/derived/cimi_kaiowa_ms_conflicts.csv"
OUT_FOCUS = ROOT / "data/derived/cimi_kaiowa_ms_conflicts_focus5.csv"
OUT_INV_FOCUS = ROOT / "data/derived/funai_focus5_inventory.csv"
OUT_GEO_FOCUS = ROOT / "data/derived/funai_focus5_territories.geojson"


def main() -> None:
    for path in (CONFLICTS, INVENTORY, CLIPPED):
        if not path.exists():
            raise SystemExit(f"Missing input: {path} (run the earlier pipeline steps)")

    df = pd.read_csv(CONFLICTS)
    kaiowa = df.loc[df["povo"].astype("string").str.contains("kaio", case=False, na=False)]
    kaiowa_ms = kaiowa.loc[kaiowa["state"].astype("string").str.contains("MS", case=False, na=False)].copy()
    kaiowa_ms["TI_CLEAN"] = cimi_ti(kaiowa_ms["TI"])

    inventory = pd.read_csv(INVENTORY)
    inventory["TI_CLEAN"] = funai_ti(inventory["nome_ti"])

    in_both = set(inventory["TI_CLEAN"]) & set(kaiowa_ms["TI_CLEAN"])
    only_funai = set(inventory["TI_CLEAN"]) - set(kaiowa_ms["TI_CLEAN"])
    only_cimi = set(kaiowa_ms["TI_CLEAN"]) - set(inventory["TI_CLEAN"])
    print(f"TIs in FUNAI and CIMI ({len(in_both)}):", sorted(in_both))
    print(f"TIs in FUNAI only ({len(only_funai)}):", sorted(only_funai))
    print(f"TIs in CIMI only ({len(only_cimi)}):", sorted(only_cimi))

    missing = set(FOCUS_TERRITORIES) - in_both
    if missing:
        raise SystemExit(f"Focus territories without a polygon in the inventory: {sorted(missing)}")

    OUT_ALL.parent.mkdir(parents=True, exist_ok=True)
    kaiowa_ms.to_csv(OUT_ALL, index=False)
    focus_conflicts = kaiowa_ms.loc[kaiowa_ms["TI_CLEAN"].isin(FOCUS_TERRITORIES)]
    focus_conflicts.to_csv(OUT_FOCUS, index=False)

    focus_inv = inventory.loc[inventory["TI_CLEAN"].isin(FOCUS_TERRITORIES)].sort_values("TI_CLEAN")
    focus_inv.to_csv(OUT_INV_FOCUS, index=False)

    clipped = gpd.read_file(CLIPPED)
    focus_geo = clipped.loc[clipped["TI_CLEAN"].isin(FOCUS_TERRITORIES)].copy()
    focus_geo.to_file(OUT_GEO_FOCUS, driver="GeoJSON")

    print(f"wrote {OUT_ALL} ({len(kaiowa_ms)} rows)")
    print(f"wrote {OUT_FOCUS} ({len(focus_conflicts)} rows)")
    print(f"wrote {OUT_INV_FOCUS} ({len(focus_inv)} rows)")
    print(f"wrote {OUT_GEO_FOCUS} ({len(focus_geo)} features)")


if __name__ == "__main__":
    main()
