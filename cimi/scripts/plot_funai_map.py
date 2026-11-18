"""Figure: FUNAI Kaiowá territories in Mato Grosso do Sul, focus territories highlighted.

Input : data/derived/funai_kaiowa_ms_clipped.geojson (build_funai_inventory.py)
        data/derived/funai_focus_territories.geojson (prepare_kaiowa_dataset.py)
        data/raw/gaul_ms_boundary_2025.geojson
Output: out/figures/funai_kaiowa_ms_map.png/.svg

The base layers and the label offsets come from `ms_map_base.py`, shared with
`plot_conflict_bubble_map.py`. The clipped polygons come from the inventory
script; this plot never touches the raw shapefile.
"""

from __future__ import annotations

import matplotlib.pyplot as plt

from ms_map_base import FIGS, OFFSETS, add_base, anchor, load_layers

STEM = "funai_kaiowa_ms_map"


def main() -> None:
    state, territories, focus = load_layers()

    fig, ax = plt.subplots(figsize=(9, 10))
    add_base(ax, state, territories, focus)
    for _, row in focus.iterrows():
        ax.annotate(row["TI_CLEAN"], xy=anchor(row.geometry),
                    xytext=OFFSETS.get(row["TI_CLEAN"], (1, 2)),
                    textcoords="offset points",
                    fontsize=8, ha="left", va="bottom")

    ax.set_title("FUNAI Kaiowá territories intersecting Mato Grosso do Sul\n"
                 f"clipped to the state boundary; blue = the {len(focus)} focus territories")
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
