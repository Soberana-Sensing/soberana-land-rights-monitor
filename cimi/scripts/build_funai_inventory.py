"""Build the FUNAI territory inventory for Mato Grosso do Sul.

Input : data/raw/FUNAI_tis_portarias_poligonais_MS_2026-11-12.geojson
        WFS layer Funai:tis_poligonais_portarias, geoserver.funai.gov.br,
        filtered to uf_sigla = 'MS', retrieved 2026-11-12. One file carries the
        polygons and every legal-stage date and document reference.
Output: data/derived/funai_territorial_inventory_ms.csv
        data/derived/funai_kaiowa_ms_clipped.geojson   (same rows, with geometry)
        data/derived/funai_ms_territories_clipped.geojson (every MS territory, with
            geometry; the anchor layer for the all-territory bubble map)

Keeps the Kaiowá territories, one row per normalised name, with the official
area, the stage reached and its date. Territories FUNAI attributes to another
people stay out of this file; the CIMI name table decides whether they matter
case by case.

The GeoJSON feeds the map plot and the later MapBiomas / Sentinel-1 analyses
on the focus territories. The GAUL boundary is only the map backdrop; no
clipping happens here (the download is already MS-only).
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import geopandas as gpd
import pandas as pd

import ti_names

ROOT = Path(__file__).resolve().parents[1]
FUNAI = ROOT / "data/raw/FUNAI_tis_portarias_poligonais_MS_2026-11-12.geojson"
OUT = ROOT / "data/derived/funai_territorial_inventory_ms.csv"
GEOJSON = ROOT / "data/derived/funai_kaiowa_ms_clipped.geojson"
GEOJSON_ALL = ROOT / "data/derived/funai_ms_territories_clipped.geojson"

STAGES = ["data_delimitada", "data_declarada", "data_homologada", "data_regularizada"]

def normalise_territory_name(value: object) -> str:
    """Conservative key for de-duplication; never used to merge boundaries."""
    value = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    value = re.sub(r"^t[ií]\s+", "", value)
    return re.sub(r"\s+", " ", value)


def main() -> None:
    if not FUNAI.exists():
        raise SystemExit(f"Missing input: {FUNAI}")

    funai = gpd.read_file(FUNAI)
    if funai.crs is None:
        raise SystemExit(f"{FUNAI.name} has no CRS.")
    missing = {"terrai_codigo", "terrai_nome", "etnia_nome", "geometry"} - set(funai.columns)
    if missing:
        raise SystemExit(f"{FUNAI.name} is missing fields {sorted(missing)}.")

    if funai["terrai_codigo"].duplicated().any():
        raise SystemExit("Duplicate terrai_codigo in the FUNAI download; refusing to guess.")

    funai["territory_id"] = funai["terrai_codigo"].astype("string").str.strip()
    funai["nome_ti"] = funai["terrai_nome"].astype("string")
    funai["povo"] = funai["etnia_nome"].astype("string")
    funai["funai_area_official_ha"] = pd.to_numeric(
        funai.get("superficie_perimetro_ha"), errors="coerce")

    for col in STAGES:
        funai[col] = pd.to_datetime(funai[col].astype("string").str[:10], errors="coerce")
    funai["defined_date"] = funai[STAGES].min(axis=1)
    funai["defined_stage"] = funai[STAGES].notna().idxmax(axis=1).str.replace("data_", "", regex=False)
    funai.loc[funai[STAGES].notna().sum(axis=1).eq(0), "defined_stage"] = pd.NA
    funai["defined_document"] = pd.NA
    for stage in ("delimitada", "declarada", "homologada", "regularizada"):
        mask = funai["defined_stage"].eq(stage)
        funai.loc[mask, "defined_document"] = funai.loc[mask, f"tit_{stage}"]

    outside = funai.loc[funai["uf_sigla"].astype("string").str.strip().ne("MS"), "terrai_nome"]
    if len(outside):
        raise SystemExit(f"{FUNAI.name} holds non-MS features: {outside.tolist()}")

    work = funai.copy()
    try:
        work["geometry"] = work.geometry.make_valid()
    except AttributeError:
        from shapely import make_valid
        work["geometry"] = work.geometry.apply(make_valid)
    work = work.loc[work.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    work = work.loc[work.geometry.notna() & ~work.geometry.is_empty].reset_index(drop=True)
    if work.empty:
        raise SystemExit("No valid FUNAI polygons; check the download.")

    work["name_normalised"] = work["nome_ti"].map(normalise_territory_name)
    work["TI_CLEAN"] = ti_names.funai_ti(work["nome_ti"])
    work = work.sort_values("territory_id").drop_duplicates("name_normalised", keep="last")
    work = work.reset_index(drop=True)

    work["source_category"] = "Other / verify"
    work.loc[work["modalidade_ti"].eq("Tradicionalmente ocupada"), "source_category"] = \
        "TI (Tradicionalmente ocupada)"
    work.loc[work["modalidade_ti"].eq("Reserva Indígena"), "source_category"] = \
        "RI (Reserva Indígena)"

    work["area_inside_ms_ha"] = work.to_crs("EPSG:6933").geometry.area / 10_000

    kaiowa = work.loc[work["povo"].astype("string").str.contains("Kaiow", na=False)
                      | work["TI_CLEAN"].isin(ti_names.FOCUS_TERRITORIES)].copy()
    if kaiowa["territory_id"].duplicated().any():
        dup = kaiowa.loc[kaiowa["territory_id"].duplicated(False), "territory_id"].tolist()
        raise SystemExit(f"Duplicate FUNAI feature ids after de-duplication: {dup}")

    cols = ["territory_id", "terrai_nome", "nome_ti", "etnia_nome", "povo",
            "uf_sigla", "municipio_nome", "funai_area_official_ha",
            "fase_ti", "modalidade_ti", "reestudo_ti", "source_category",
            "cr", "faixa_fronteira", "undadm_codigo", "undadm_nome", "undadm_sigla",
            "data_delimitada", "tit_delimitada",
            "defined_date", "defined_stage", "defined_document",
            "name_normalised", "TI_CLEAN", "area_inside_ms_ha"]
    kaiowa = kaiowa[cols + ["geometry"]]
    all_territories = work[cols + ["geometry"]]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    kaiowa.drop(columns="geometry").to_csv(OUT, index=False)
    kaiowa.to_file(GEOJSON, driver="GeoJSON")
    all_territories.to_file(GEOJSON_ALL, driver="GeoJSON")
    print(f"wrote {OUT}")
    print(f"wrote {GEOJSON}")
    print(f"wrote {GEOJSON_ALL}")
    print(f"FUNAI supplies {len(funai)} polygons in Mato Grosso do Sul, "
          f"which collapse to {len(work)} distinct territory names once repeated "
          f"records for the same place are merged.")
    print(f"Of those {len(work)} territories, {len(kaiowa)} are kept: those FUNAI "
          f"attributes to the Guarani Kaiowá plus the focus territories listed "
          f"in config/ti_names.yaml (some attributed to the Nhandeva or the "
          f"Guaraní, tracked in the CIMI analysis).")


if __name__ == "__main__":
    main()
