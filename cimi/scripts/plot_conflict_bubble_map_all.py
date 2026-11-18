"""Figure: every CIMI Kaiowá-MS territory label as a bubble, sized by case count.

Input : data/derived/cimi_kaiowa_ms_conflicts.csv  (prepare_kaiowa_dataset.py)
        data/derived/funai_ms_territories_clipped.geojson
            (build_funai_inventory.py; all 46 MS territories, one per name)
        data/raw/gaul_ms_boundary_2025.geojson
Output: out/figures/cimi_kaiowa_conflict_bubble_map_all.png/.svg

The map companion of `cimi_kaiowa_conflict_heatmap.png`: same 46 territory labels,
same 209 cases, but placed on the ground. Bubble area is proportional to the count
and each bubble carries its number, keyed in the right-hand panel.

Not every label can be placed. Chapter I files cases under acampamentos (PYELITO
KUE, ACAMPAMENTO ITA POTY), municipalities (DOURADOS, AMAMBAI, CAARAPO hold
reserve cases), squatted farms (GUAPOY, SANTIAGO KUE) and catch-alls (VARIAS).
Only labels that match a FUNAI territory name get a bubble; the rest are listed
with their counts along the bottom, so the figure never silently drops cases.

The CIMI reserve rows (DOURADOS, AMAMBAI, CAARAPO) sit on the same-named FUNAI
polygon. Those labels name the reserve or the municipality around it, so treat
those three bubbles as "in or around".
"""

from __future__ import annotations

import textwrap

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

from ms_map_base import FIGS, add_base, anchor, load_all_territories, load_layers

ROOT = FIGS.parents[1]
CONFLICTS = ROOT / "data/derived/cimi_kaiowa_ms_conflicts.csv"
STEM = "cimi_kaiowa_conflict_bubble_map_all"

SCALE = 18
BUBBLE = "#c0392b"
BUBBLE_EDGE = "#7f1d1d"
LEGEND_COUNTS = (1, 5, 10, 20, 32)
PAD_X, PAD_Y = 0.55, 0.30

# Number offsets (points) where two anchors sit too close for the default above.
NUMBER_OFFSETS = {
    "DOURADOS": (-20, 6),
    "APIKAY": (8, -8),
    "PORTO LINDO": (-14, 5),
    "YVY KATU": (8, -10),
}


def main() -> None:
    if not CONFLICTS.exists():
        raise SystemExit(f"Missing input: {CONFLICTS} (run the earlier pipeline steps)")

    df = pd.read_csv(CONFLICTS)
    counts = df.groupby("TI_CLEAN").size().sort_values(ascending=False)
    state, _, _ = load_layers()
    territories = load_all_territories()

    placed = counts[counts.index.isin(set(territories["TI_CLEAN"]))]
    unplaced = counts[~counts.index.isin(set(territories["TI_CLEAN"]))]
    if int(placed.sum()) + int(unplaced.sum()) != len(df):
        raise SystemExit("Placed and unplaced counts do not add up to the case total")

    anchors = territories.loc[territories["TI_CLEAN"].isin(placed.index)].copy()
    anchors["cases"] = anchors["TI_CLEAN"].map(placed)
    anchors = anchors.sort_values(["cases", "TI_CLEAN"], ascending=[False, True])
    anchors["key"] = range(1, len(anchors) + 1)

    fig = plt.figure(figsize=(15, 9.6))
    gs = fig.add_gridspec(2, 2, height_ratios=(6.2, 1.5), width_ratios=(3.1, 1.25),
                          wspace=0.04, hspace=0.26)
    ax = fig.add_subplot(gs[0, 0])
    key = fig.add_subplot(gs[0, 1])
    foot = fig.add_subplot(gs[1, :])

    add_base(ax, state, territories, None, fill_state=True)

    for _, row in anchors.iterrows():
        x, y = anchor(row.geometry)
        ax.scatter([x], [y], s=SCALE * float(row["cases"]), color=BUBBLE, alpha=0.55,
                   edgecolor=BUBBLE_EDGE, linewidth=1.0, zorder=6)
        ax.annotate(f"#{int(row['key'])}", xy=(x, y),
                    xytext=NUMBER_OFFSETS.get(row["TI_CLEAN"], (0, 7)),
                    textcoords="offset points", fontsize=7.5, ha="center",
                    va="bottom", color="#3b3b3b", zorder=7)

    xmin, ymin, xmax, ymax = anchors.total_bounds
    ax.set_xlim(xmin - PAD_X, xmax + PAD_X)
    ax.set_ylim(ymin - PAD_Y, ymax + PAD_Y)
    ax.set_title(f"CIMI Kaiowá cases in Mato Grosso do Sul: {len(placed)} of the "
                 f"{len(counts)} territory labels sit on a FUNAI polygon\n"
                 f"bubble area proportional to the case count "
                 f"({int(placed.sum())} of {len(df)} cases placed)", fontsize=13)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    draw_overview(ax, state, territories, (xmin - PAD_X, xmax + PAD_X,
                                           ymin - PAD_Y, ymax + PAD_Y))

    # right-hand key
    key.set_axis_off()
    # spell the numbering out here: a reader takes "#1" for one case, and then
    # the bubble sizes look inverted
    key.set_title(f"Placed on the map ({len(placed)} labels)\n"
                  f"# = key index, count in brackets", fontsize=9, loc="left")
    lines = [f"#{int(r['key']):<2} {r['TI_CLEAN']}  ({int(r['cases'])})"
             for _, r in anchors.iterrows()]
    key.text(0.0, 1.0, "\n".join(lines), transform=key.transAxes,
             va="top", ha="left", fontsize=8, linespacing=1.45, family="monospace")
    handles = [key.scatter([], [], s=SCALE * n, color=BUBBLE, alpha=0.55,
                           edgecolor=BUBBLE_EDGE, linewidth=1.0, label=str(n))
               for n in LEGEND_COUNTS]
    key.legend(handles=handles, title="CIMI cases, 2009-2025", loc="lower left",
               frameon=False, labelspacing=1.4, borderpad=0.6, scatterpoints=1,
               handletextpad=1.2, title_fontsize=9, fontsize=9)

    # bottom strip: labels with no polygon
    foot.set_axis_off()
    foot.set_title(f"No FUNAI polygon to anchor them: {len(unplaced)} labels, "
                   f"{int(unplaced.sum())} cases (acampamentos, municipalities, "
                   f"squatted farms, catch-alls)", fontsize=9, loc="left")
    entries = [f"{ti} ({int(n)})" for ti, n in unplaced.items()]
    columns = 3
    per_col = -(-len(entries) // columns)
    blocks = [entries[i:i + per_col] for i in range(0, len(entries), per_col)]
    for i, block in enumerate(blocks):
        foot.text(i / columns, 0.88, "\n".join(block), transform=foot.transAxes,
                  va="top", ha="left", fontsize=8, linespacing=1.4,
                  family="monospace")

    FIGS.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(FIGS / f"{STEM}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(f"placed {len(placed)} labels / {int(placed.sum())} cases")
    print(f"unplaced {len(unplaced)} labels / {int(unplaced.sum())} cases")
    print(f"wrote {FIGS / f'{STEM}.png'} and .svg")


def draw_overview(ax, state, territories, zoom: tuple[float, float, float, float]) -> None:
    """Small state panel, lower left, with the zoom window boxed."""
    inset = ax.inset_axes([0.01, 0.02, 0.26, 0.26])
    state.plot(ax=inset, color="#eef0ee", edgecolor="#263746", linewidth=0.7)
    territories.boundary.plot(ax=inset, color="#a64b32", linewidth=0.35)
    xmin, xmax, ymin, ymax = zoom
    inset.add_patch(Rectangle((xmin, ymin), xmax - xmin, ymax - ymin,
                              fill=False, edgecolor=BUBBLE, linewidth=1.2))
    inset.set_xticks([])
    inset.set_yticks([])
    inset.set_xlabel("")
    inset.set_ylabel("")
    inset.set_title("Mato Grosso do Sul", fontsize=8, pad=3)


if __name__ == "__main__":
    main()
