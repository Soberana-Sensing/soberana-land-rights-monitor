"""Figure: FUNAI Kaiowá territories in Mato Grosso do Sul, focus five highlighted.

Input : data/derived/funai_kaiowa_ms_clipped.geojson (build_funai_inventory.py)
        data/derived/funai_focus5_territories.geojson (prepare_kaiowa_dataset.py)
        data/raw/gaul_ms_boundary_2025.geojson
Output: out/figs/funai_kaiowa_ms_map.png/.svg

The clipped polygons come from the inventory script; this plot never touches the
raw shapefile, so no other place re-clips FUNAI's polygons.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt

import ti_names
from ti_names import FOCUS_TERRITORIES

ROOT = Path(__file__).resolve().parents[1]
CLIPPED = ROOT / "data/derived/funai_kaiowa_ms_clipped.geojson"
FOCUS = ROOT / "data/derived/funai_focus5_territories.geojson"
BOUNDARY = ROOT / "data/raw/gaul_ms_boundary_2025.geojson"
FIGS = ROOT / "out/figs"
STEM = "funai_kaiowa_ms_map"


def main() -> None:
    for path in (CLIPPED, FOCUS, BOUNDARY):
        if not path.exists():
            raise SystemExit(f"Missing input: {path} (run the earlier pipeline steps)")

    state = gpd.read_file(BOUNDARY)
    territories = gpd.read_file(CLIPPED)
    focus = gpd.read_file(FOCUS)

    fig, ax = plt.subplots(figsize=(9, 10))
    state.boundary.plot(ax=ax, color="#263746", linewidth=1.4)
    territories.boundary.plot(ax=ax, color="#a64b32", linewidth=0.8)
    focus.boundary.plot(ax=ax, color="#1f77b4", linewidth=1.4, zorder=5)
    for _, row in focus.iterrows():
        ax.annotate(row["TI_CLEAN"], xy=row.geometry.centroid.coords[0],
                    xytext=(1, 2), textcoords="offset points",
                    fontsize=8, ha="left", va="bottom")

    ax.set_title("FUNAI Kaiowá territories intersecting Mato Grosso do Sul\n"
                 "clipped to the state boundary; blue = the five focus territories")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    fig.tight_layout()

    FIGS.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(FIGS / f"{STEM}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {FIGS / f'{STEM}.png'} and .svg")


if __name__ == "__main__":
    main()
