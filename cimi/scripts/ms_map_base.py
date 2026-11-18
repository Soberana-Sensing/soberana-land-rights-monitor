"""Shared base layers for the Mato Grosso do Sul territory maps.

Input : data/derived/funai_kaiowa_ms_clipped.geojson   (build_funai_inventory.py)
        data/derived/funai_focus_territories.geojson   (prepare_kaiowa_dataset.py)
        data/derived/funai_ms_territories_clipped.geojson (build_funai_inventory.py)
        data/raw/gaul_ms_boundary_2025.geojson

Used by `plot_funai_map.py` and `plot_conflict_bubble_map.py`. No figure here:
the state backdrop, the polygon colours and the label offsets live in one place
so the two maps cannot drift apart.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
CLIPPED = ROOT / "data/derived/funai_kaiowa_ms_clipped.geojson"
FOCUS = ROOT / "data/derived/funai_focus_territories.geojson"
ALL_TERRITORIES = ROOT / "data/derived/funai_ms_territories_clipped.geojson"
BOUNDARY = ROOT / "data/raw/gaul_ms_boundary_2025.geojson"
FIGS = ROOT / "out/figures"

STATE_EDGE = "#263746"
STATE_FILL = "#eef0ee"
TERRITORY_EDGE = "#a64b32"
FOCUS_EDGE = "#1f77b4"

# Equal-area projection for centroids and areas; the maps themselves stay in 4326.
EQUAL_AREA = "EPSG:5880"

# Per-territory label offsets (points), so the dense southern cluster stays readable.
OFFSETS = {
    "DOURADOS AMAMBAIPEGUA I": (-118, -16),
    "POTRERO GUASU": (-64, -10),
    "SOMBRERITO": (8, 2),
    "ARROIO KORA": (-58, -6),
    "JATAYVARY": (6, -10),
}


def load_layers() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Return the state boundary, the 28 clipped territories and the 10 focus ones."""
    for path in (CLIPPED, FOCUS, BOUNDARY):
        if not path.exists():
            raise SystemExit(f"Missing input: {path} (run the earlier pipeline steps)")
    return (
        gpd.read_file(BOUNDARY),
        gpd.read_file(CLIPPED),
        gpd.read_file(FOCUS),
    )


def load_all_territories() -> gpd.GeoDataFrame:
    """Every FUNAI territory in the MS download, 46 distinct names."""
    if not ALL_TERRITORIES.exists():
        raise SystemExit(f"Missing input: {ALL_TERRITORIES} (run the earlier pipeline steps)")
    return gpd.read_file(ALL_TERRITORIES)


def add_base(
    ax,
    state: gpd.GeoDataFrame,
    territories: gpd.GeoDataFrame,
    focus: gpd.GeoDataFrame | None,
    fill_state: bool = False,
) -> None:
    """Draw the state, the territory outlines and, when given, the focus outlines."""
    if fill_state:
        state.plot(ax=ax, color=STATE_FILL, edgecolor=STATE_EDGE, linewidth=1.4, zorder=0)
    else:
        state.boundary.plot(ax=ax, color=STATE_EDGE, linewidth=1.4)
    territories.boundary.plot(ax=ax, color=TERRITORY_EDGE, linewidth=0.8)
    if focus is not None:
        focus.boundary.plot(ax=ax, color=FOCUS_EDGE, linewidth=1.4, zorder=5)


def anchor(geometry) -> tuple[float, float]:
    """Point inside a polygon for a label or a symbol, in lon/lat.

    `representative_point` instead of `centroid`: the territories are concave, so
    a centroid can fall outside the polygon it belongs to.
    """
    point = (
        gpd.GeoSeries([geometry], crs="EPSG:4326")
        .to_crs(EQUAL_AREA)
        .representative_point()
        .to_crs("EPSG:4326")
        .iloc[0]
    )
    return point.x, point.y
