"""Figure: MapBiomas land cover inside one focus territory, 1985-2025.

Input : data/derived/funai_focus_territories.geojson (prepare_kaiowa_dataset.py)
Output: data/derived/mapbiomas_landcover_<TI>.csv   (ha per group per year, cache)
        out/figures/<TI>/mapbiomas_landcover_1985_2025.png/.svg

MapBiomas Brasil Collection 11, 30 m annual, 1985-2025, asset
`projects/mapbiomas-public/assets/brazil/lulc/collection11/
mapbiomas_brazil_collection11_coverage_v3` (C11 released 2026-08). The 33
classes collapse into 6 groups (plus a non-observed bucket so percentages sum
to 100); the grouping lives in GROUPS below, and phase1 of
~/soberana-sensing/indigenous-territory-ms uses the same asset and method.

One territory per run; pass a different --ti to repeat for another territory.
The derived CSV caches the GEE result, so re-plotting costs no Earth Engine
call; use --refresh to requery.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import ee
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import numpy as np
import pandas as pd

import ti_names
from ti_names import norm_ti

ROOT = Path(__file__).resolve().parents[1]
FOCUS_GEOJSON = ROOT / "data/derived/funai_focus_territories.geojson"
DERIVED = ROOT / "data/derived"
FIGS = ROOT / "out/figures"

GEE_PROJECT = "345965002834"
MBC11 = ("projects/mapbiomas-public/assets/brazil/lulc/collection11/"
         "mapbiomas_brazil_collection11_coverage_v3")
YEARS = list(range(1985, 2026))

GROUPS = {
    "native_veg": [3, 4, 5, 6, 7, 49, 12, 77, 11, 84, 50, 32, 29],
    "pasture": [15],
    "agriculture": [39, 20, 40, 62, 47, 46, 35, 41, 48],
    "mosaic": [21],
    "plantation": [9],
    "other_nonveg": [23, 24, 25, 30, 75, 91],
    "water": [33, 31],
    "nonobserved": [0],
}
COLORS = {
    "native_veg": "#1b7837",
    "pasture": "#f5b915",
    "agriculture": "#cc1f8e",
    "mosaic": "#e9e2c9",
    "plantation": "#4a2c0f",
    "other_nonveg": "#b33127",
    "water": "#2166ac",
    "nonobserved": "#cccccc",
}
LABELS = {
    "native_veg": "Native vegetation",
    "pasture": "Pasture",
    "agriculture": "Agriculture",
    "mosaic": "Mosaic of uses",
    "plantation": "Forest plantation",
    "other_nonveg": "Other non-vegetated",
    "water": "Water",
    "nonobserved": "Not observed",
}
GIDS = list(GROUPS)

# FUNAI legal acts drawn as vertical lines, one per stage and colour.
# (stage key in the inventory column `data_<key>`, English label, colour). The
# colours are dark and none matches a stack fill above. Ratification is the
# final act, so it gets a solid line; the earlier stages are dashed with an
# even on/off pattern.
STAGE_LINES = [
    ("delimitada", "delimitation", "#24479b"),
    ("declarada", "declaration", "#e07b00"),
    ("homologada", "ratification", "#8e2ba2"),
]
DASHED = (0, (4, 2.5))

# matplotlib rescales dash patterns by linewidth, which leaves one long and
# one short dash in a short legend sample. Keep the pattern as written.
plt.rcParams["lines.scale_dashes"] = False


def stage_linestyle(stage: str):
    """Ratification is solid; delimitation and declaration are evenly dashed."""
    return "solid" if stage == "homologada" else DASHED


def stage_handles() -> list[mlines.Line2D]:
    """Legend proxies for the legal-act lines, matching what the axes draw."""
    return [mlines.Line2D([], [], color=colour, linewidth=1.8,
                          linestyle=stage_linestyle(stage), label=english)
            for stage, english, colour in STAGE_LINES]


def slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def pick_territory(name: str) -> tuple[str, object]:
    territories = gpd.read_file(FOCUS_GEOJSON).to_crs(4326)
    key = norm_ti(name)
    hit = territories.loc[territories["TI_CLEAN"].map(norm_ti) == key]
    if hit.empty:
        raise SystemExit(f"{name!r} not in {FOCUS_GEOJSON.name}. Options: "
                         f"{sorted(territories['TI_CLEAN'])}")
    row = hit.iloc[0]
    return row["TI_CLEAN"], row.geometry


def fetch_ha(ti_clean: str, geometry) -> pd.DataFrame:
    """GEE call: ha per year per group inside the polygon. One server round-trip."""
    ee.Initialize(project=GEE_PROJECT)
    mb = ee.Image(MBC11)
    area = ee.Image.pixelArea().divide(1e4)

    bands = []
    for y in YEARS:
        src, dst = [], []
        for gid, classes in enumerate(GROUPS.values()):
            for cid in classes:
                src.append(cid)
                dst.append(gid)
        remapped = (mb.select(f"classification_{y}")
                      .remap(ee.List(src), ee.List(dst)))
        for gid in range(len(GROUPS)):
            bands.append(area.multiply(remapped.eq(gid)).rename(f"y{y}g{gid}"))

    stack = ee.Image.cat(bands).unmask(0)
    fc = ee.FeatureCollection([ee.Feature(ee.Geometry(geometry.__geo_interface__),
                                          {"ti": ti_clean})])
    result = stack.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.sum().repeat(len(YEARS) * len(GROUPS)),
        scale=30, crs="EPSG:4326", tileScale=4,
    ).getInfo()

    sums = result["features"][0]["properties"]["sum"]
    rows, idx = [], 0
    for y in YEARS:
        for g in GIDS:
            rows.append({"year": y, "group": g, "ha": sums[idx] or 0.0})
            idx += 1
    return pd.DataFrame(rows)


def cimi_occupied(ti_clean: str) -> tuple[float, float, float, str] | None:
    """Occupied ha, total area, share % and year from the CIMI occupation shares."""
    shares = ROOT / "data/derived/cimi_ms_occupation_shares.csv"
    if not shares.exists():
        return None
    occ = pd.read_csv(shares)
    key = ti_names.CIMI_VARIANTS.get(norm_ti(ti_clean), norm_ti(ti_clean))
    hit = occ.loc[occ["territory"].map(norm_ti)
                  .replace(ti_names.CIMI_VARIANTS).str.startswith(key)]
    if hit.empty:
        return None
    r = hit.sort_values("year").iloc[0]
    return float(r["occupied_ha"]), float(r["area_ha"]), float(r["share_pct"]), str(r["year"])


def legal_acts(ti_clean: str) -> tuple[list[tuple[str, str, str, str, int]], str]:
    """Recorded FUNAI legal acts and the current stage, from the focus inventory.

    Returns ([(stage key, english label, colour, act document, year), ...],
    fase_ti). One entry per stage that has a date; a stage with no date has no
    line. The current stage comes from `fase_ti`, never from the dates.
    """
    inventory = ROOT / "data/derived/funai_focus_territories_inventory.csv"
    if not inventory.exists():
        print("no focus inventory; no legal-act lines")
        return [], ""
    row = pd.read_csv(inventory).loc[lambda d: d["TI_CLEAN"] == ti_clean]
    if row.empty:
        print(f"{ti_clean} not in the focus inventory; no legal-act lines")
        return [], ""
    r = row.iloc[0]
    acts = []
    for stage, english, colour in STAGE_LINES:
        date = pd.to_datetime(r.get(f"data_{stage}"), errors="coerce")
        if pd.isna(date):
            continue
        document = r.get(f"tit_{stage}")
        document = document if isinstance(document, str) else ""
        acts.append((stage, english, colour, document, int(date.year)))
    phase = r.get("fase_ti", "")
    return acts, phase if isinstance(phase, str) else ""


def add_stage_lines(ax: plt.Axes, ti_clean: str) -> tuple[list, str]:
    """One coloured line per recorded legal act. Returns legend handles."""
    acts, phase = legal_acts(ti_clean)
    handles = []
    for stage, english, colour, document, year in acts:
        ax.axvline(year, color=colour, linewidth=1.8,
                   linestyle=stage_linestyle(stage), zorder=5)
        handles.append(mlines.Line2D([], [], color=colour, linewidth=1.8,
                                     linestyle=stage_linestyle(stage),
                                     label=english))
        print(f"legal act: {english} {year} ({document})")
    if not acts:
        print(f"no FUNAI legal-act date for {ti_clean}; no lines")
    return handles, phase


def plot(df: pd.DataFrame, ti_clean: str, out_dir: Path) -> None:
    wide = df.pivot(index="year", columns="group", values="ha").reindex(
        index=YEARS, columns=GIDS).fillna(0)
    total = wide.sum(axis=1)

    subtitle = ""
    cimi = cimi_occupied(ti_clean)
    if cimi:
        occupied, area, share, year = cimi
        subtitle = (f"\nTerritory area: {area:,.0f} ha; the community effectively "
                    f"occupies {occupied:,.0f} ha ({share:.2f}%) "
                    f"according to CIMI ({year})")

    fig, ax = plt.subplots(figsize=(11, 6))
    final_ha = {g: wide[g].iloc[-1] for g in GIDS}
    ax.stackplot(YEARS, [wide[g].to_numpy() for g in GIDS],
                 labels=[f"{LABELS[g]} ({final_ha[g]:,.0f} ha)" for g in GIDS],
                 colors=[COLORS[g] for g in GIDS])
    # thick black line at every boundary between two groups
    cumulative = wide.cumsum(axis=1)
    for g in GIDS:
        ax.plot(YEARS, cumulative[g], color="white", linewidth=1.4)
    ax.set_xlim(YEARS[0], YEARS[-1])
    ax.set_ylim(0, total.max())
    ax.set_ylabel("Hectares (ha)")
    ax.set_xlabel("Year")

    stage_handles, phase = add_stage_lines(ax, ti_clean)
    stage_text = f" (current stage: {ti_names.stage_en(phase)})" if phase else ""
    ax.set_title(f"Land cover in {ti_clean.title()}{stage_text}\n"
                 "MapBiomas Collection 11, 1985-2025 (hectares inside the territory)"
                 + subtitle)

    handles, labels_ = ax.get_legend_handles_labels()
    leg_class = ax.legend(handles[::-1], labels_[::-1], loc="upper left",
                          bbox_to_anchor=(1.02, 1.0), title="Legend",
                          fontsize=9)
    leg_stage = None
    if stage_handles:
        ax.add_artist(leg_class)
        leg_stage = ax.legend(handles=stage_handles, loc="lower left",
                              bbox_to_anchor=(1.02, 0.0), title="Legal status",
                              fontsize=9)
    ax.set_axisbelow(True)
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    extra = [leg for leg in (leg_class, leg_stage) if leg is not None]
    for ext in ("png", "svg"):
        fig.savefig(out_dir / f"mapbiomas_landcover_1985_2025.{ext}",
                    dpi=300, bbox_inches="tight", bbox_extra_artists=extra)
    plt.close(fig)
    print(f"wrote {out_dir / 'mapbiomas_landcover_1985_2025.png'} and .svg")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ti", required=True,
                        help="territory name as TI_CLEAN, e.g. 'ARROIO KORA'")
    parser.add_argument("--refresh", action="store_true",
                        help="requery Earth Engine even if the cache CSV exists")
    args = parser.parse_args()

    if not FOCUS_GEOJSON.exists():
        raise SystemExit(f"Missing input: {FOCUS_GEOJSON}")

    ti_clean, geometry = pick_territory(args.ti)
    csv_cache = DERIVED / f"mapbiomas_landcover_{slug(ti_clean).lower()}.csv"

    if csv_cache.exists() and not args.refresh:
        df = pd.read_csv(csv_cache)
        print(f"loaded cache {csv_cache} (--refresh to requery)")
    else:
        df = fetch_ha(ti_clean, geometry)
        DERIVED.mkdir(parents=True, exist_ok=True)
        df.to_csv(csv_cache, index=False)
        print(f"wrote {csv_cache}")

    plot(df, ti_clean, FIGS / slug(ti_clean))

    pivot = df.pivot(index="year", columns="group", values="ha").reindex(columns=GIDS).fillna(0)
    first, last = pivot.iloc[0], pivot.iloc[-1]
    print(f"native veg: {first['native_veg']:,.0f} ha (1985) -> "
          f"{last['native_veg']:,.0f} ha (2025)")


if __name__ == "__main__":
    main()
