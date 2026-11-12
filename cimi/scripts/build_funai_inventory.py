"""Build the FUNAI territory inventory for Mato Grosso do Sul.

Input : data/raw/tis_poligonais_FUNAI/tis_poligonais.shp    (FUNAI polygons, gid)
        data/raw/funai_tis_poligonais_portarias_MS_2026-11-04.geojson  (stage dates)
        data/raw/gaul_ms_boundary_2025.geojson              (FAO GAUL 2025 state line)
Output: data/derived/funai_territorial_inventory_ms.csv
        data/derived/funai_kaiowa_ms_clipped.geojson   (same rows, with geometry)

Keeps the Kaiowá territories that intersect Mato Grosso do Sul, one row per
normalised name, with the official area, the stage reached and the area clipped
to the state. Territories FUNAI attributes to another people stay out of this
file; the CIMI name table decides whether they matter case by case.

The clipped GeoJSON feeds the map plot and the later MapBiomas / Sentinel-1
analyses on the focus territories, so nothing else re-clips the shapefile.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import geopandas as gpd
import pandas as pd

import ti_names

ROOT = Path(__file__).resolve().parents[1]
SHP = ROOT / "data/raw/tis_poligonais_FUNAI/tis_poligonais.shp"
ACTS = ROOT / "data/raw/funai_tis_poligonais_portarias_MS_2026-11-04.geojson"
BOUNDARY = ROOT / "data/raw/gaul_ms_boundary_2025.geojson"
OUT = ROOT / "data/derived/funai_territorial_inventory_ms.csv"
GEOJSON = ROOT / "data/derived/funai_kaiowa_ms_clipped.geojson"

STAGES = ["data_delimitada", "data_declarada", "data_homologada", "data_regularizada"]


def normalise_territory_name(value: object) -> str:
    """Conservative key for de-duplication; never used to merge boundaries."""
    value = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    value = re.sub(r"^t[ií]\s+", "", value)
    return re.sub(r"\s+", " ", value)


def main() -> None:
    for path in (SHP, ACTS, BOUNDARY):
        if not path.exists():
            raise SystemExit(f"Missing raw input: {path}")

    funai = gpd.read_file(SHP, encoding="latin1")
    if funai.crs is None:
        raise SystemExit(f"{SHP.name} has no CRS; check that its .prj file is present.")
    missing = {"terrai_nom", "etnia_nome", "geometry"} - set(funai.columns)
    if missing:
        raise SystemExit(f"{SHP.name} is missing fields {sorted(missing)}.")

    id_field = next(
        (c for c in ("gid", "terrai_cod")
         if c in funai.columns and funai[c].notna().all() and not funai[c].duplicated().any()),
        None,
    )
    if id_field is None:
        raise SystemExit("No unique FUNAI feature id in the shapefile; refusing to guess.")
    funai["territory_id"] = funai[id_field].astype(str)
    funai["nome_ti"] = funai["terrai_nom"].astype("string")
    funai["povo"] = funai["etnia_nome"].astype("string")
    funai["funai_area_official_ha"] = pd.to_numeric(
        funai.get("superficie"), errors="coerce")

    acts = gpd.read_file(ACTS)
    for col in STAGES:
        acts[col] = pd.to_datetime(acts[col].astype("string").str[:10], errors="coerce")
    acts["defined_date"] = acts[STAGES].min(axis=1)
    acts["defined_stage"] = acts[STAGES].notna().idxmax(axis=1).str.replace("data_", "", regex=False)
    acts.loc[acts[STAGES].notna().sum(axis=1).eq(0), "defined_stage"] = pd.NA
    acts["defined_document"] = pd.NA
    for stage in ("delimitada", "declarada", "homologada", "regularizada"):
        mask = acts["defined_stage"].eq(stage)
        acts.loc[mask, "defined_document"] = acts.loc[mask, f"tit_{stage}"]

    funai["_code"] = funai["terrai_cod"].astype("string").str.strip()
    acts["_code"] = acts["terrai_codigo"].astype("string").str.strip()
    funai = funai.merge(
        acts[["_code", "data_delimitada", "tit_delimitada",
              "defined_date", "defined_stage", "defined_document"]],
        on="_code", how="left",
    ).drop(columns="_code")

    state_ms = gpd.read_file(BOUNDARY)
    state_geom = state_ms.to_crs(funai.crs).geometry.union_all()
    work = funai.copy()
    try:
        work["geometry"] = work.geometry.make_valid()
    except AttributeError:
        from shapely import make_valid
        work["geometry"] = work.geometry.apply(make_valid)
    work = work.loc[work.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    work = work.to_crs(state_ms.crs)
    work = work.loc[work.geometry.intersects(state_geom)].copy()
    work["geometry"] = work.geometry.intersection(state_geom)
    work = work.loc[work.geometry.notna() & ~work.geometry.is_empty].reset_index(drop=True)
    if work.empty:
        raise SystemExit("No FUNAI polygon intersects the state boundary; check the inputs.")

    work["name_normalised"] = work["nome_ti"].map(normalise_territory_name)
    work["TI_CLEAN"] = ti_names.funai_ti(work["nome_ti"])
    if "data_atual" in work.columns:
        work["_record_update"] = pd.to_datetime(work["data_atual"], errors="coerce", dayfirst=True)
        work = (work.sort_values(["_record_update", "territory_id"], na_position="first")
                    .drop_duplicates("name_normalised", keep="last")
                    .drop(columns="_record_update"))
    else:
        work = work.sort_values("territory_id").drop_duplicates("name_normalised", keep="last")
    work = work.reset_index(drop=True)

    work["source_category"] = "Other / verify"
    work.loc[work["modalidade"].eq("Tradicionalmente ocupada"), "source_category"] = \
        "TI (Tradicionalmente ocupada)"
    work.loc[work["modalidade"].eq("Reserva Indígena"), "source_category"] = \
        "RI (Reserva Indígena)"

    work["area_inside_ms_ha"] = work.to_crs("EPSG:6933").geometry.area / 10_000

    kaiowa = work.loc[work["povo"].astype("string").str.contains("Kaiow", na=False)].copy()
    if kaiowa["territory_id"].duplicated().any():
        dup = kaiowa.loc[kaiowa["territory_id"].duplicated(False), "territory_id"].tolist()
        raise SystemExit(f"Duplicate FUNAI feature ids after clipping: {dup}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    kaiowa.drop(columns="geometry").to_csv(OUT, index=False)
    kaiowa.to_file(GEOJSON, driver="GeoJSON")
    print(f"wrote {OUT}")
    print(f"wrote {GEOJSON}")
    print(f"FUNAI supplies {len(funai)} polygons touching Mato Grosso do Sul, "
          f"which collapse to {len(work)} distinct territory names once repeated "
          f"records for the same place are merged.")
    print(f"Of those {len(work)} territories, {len(kaiowa)} are Guarani Kaiowá by "
          f"FUNAI's own people field; only those are kept in this inventory.")


if __name__ == "__main__":
    main()
