"""Figure: CIMI counts per focus territory, bubbles sized by the count.

Input : --source cases     data/derived/cimi_kaiowa_ms_conflicts_focus_territories.csv
                           (prepare_kaiowa_dataset.py) — Chapter I cases only
        --source mentions  data/derived/cimi_mentions_focus_territories.csv
                           (extract_territory_mentions.py) — every chapter
        data/derived/funai_kaiowa_ms_clipped.geojson   (build_funai_inventory.py)
        data/derived/funai_focus_territories.geojson   (prepare_kaiowa_dataset.py)
        data/raw/gaul_ms_boundary_2025.geojson
Output: --source cases     out/figures/cimi_kaiowa_conflict_bubble_map.png/.svg
        --source mentions  out/figures/cimi_kaiowa_mentions_bubble_map.png/.svg

Merges the state map of `plot_funai_map.py` with the counts of the heatmap or of
the mention scan. Bubble area is proportional to the count (radius ~ sqrt), so a
territory with four times the count covers four times the ink.

The two sources answer different questions and must not be mixed. `cases` is the
Chapter I conflict table: a case is one recorded conflict. `mentions` is the
whole-report scan: a mention is any place the territory is named, chapters I to
V plus front matter, prose included. The mention map therefore counts attention,
not conflict. Both cover only the ten focus territories, which is the only set
where every territory owns a polygon.

The main axes zoom to the southern cone; a left panel carries the whole state and
a box around the zoom. Label offsets belong to this zoom, not to the shared
full-state offsets in `ms_map_base.py`.
"""

from __future__ import annotations

import argparse
import textwrap

import matplotlib.pyplot as plt
import pandas as pd

from ms_map_base import FIGS, add_base, anchor, load_layers
from ti_names import FOCUS_TERRITORIES

ROOT = FIGS.parents[1]

SOURCES = {
    "cases": {
        "csv": ROOT / "data/derived/cimi_kaiowa_ms_conflicts_focus_territories.csv",
        "stem": "cimi_kaiowa_conflict_bubble_map",
        "noun": "case",
        "noun_plural": "cases",
        "period": "2009-2025",
        "scope": "Chapter I conflict cases",
        "scale": 30,
        "legend": (1, 5, 10, 16),
    },
    "mentions": {
        "csv": ROOT / "data/derived/cimi_mentions_focus_territories.csv",
        "stem": "cimi_kaiowa_mentions_bubble_map",
        "noun": "mention",
        "noun_plural": "mentions",
        "period": "2008-2025",
        "scope": "mentions in every chapter of the reports",
        "scale": 8,
        "legend": (10, 25, 50, 100),
    },
}

BUBBLE = "#c0392b"
BUBBLE_EDGE = "#7f1d1d"

# Zoom window around the focus territories, lon/lat degrees of padding.
PAD_X, PAD_Y = 0.60, 0.30

# Label placement for the zoomed layout: offset in points, horizontal alignment
# and wrap width. The shared OFFSETS in ms_map_base.py suit the full-state frame
# of plot_funai_map.py; at this zoom each label needs its own side of the bubble.
LABELS = {
    "GUYRAROKA": (14, 8, "left", 20),
    "PANAMBI (LAGOA RICA)": (14, 2, "left", 20),
    "DOURADOS AMAMBAIPEGUA I": (-16, 30, "right", 18),
    "ARROIO KORA": (-22, 20, "right", 20),
    "NHANDERU MARANGATU": (-14, 24, "right", 20),
    "IGUATEMIPEGUA I": (-14, -8, "right", 20),
    "TAQUARA": (12, -10, "left", 20),
    "SOMBRERITO": (14, 2, "left", 20),
    "JATAYVARY": (-10, 8, "right", 20),
    "POTRERO GUASU": (-12, -10, "right", 20),
}


def counts_by_territory(csv: str) -> pd.Series:
    if not csv.exists():
        raise SystemExit(f"Missing input: {csv} (run the earlier pipeline steps)")
    df = pd.read_csv(csv)
    counts = df.groupby("TI_CLEAN").size().sort_values(ascending=False)

    extra = sorted(set(counts.index) - set(FOCUS_TERRITORIES))
    if extra:
        raise SystemExit(f"Counts under territories outside the focus set: {extra}")
    return counts


def label_text(ti: str, n: int, width: int) -> str:
    return "\n".join(textwrap.wrap(f"{ti} ({n})", width))


def draw_overview(ax, state, territories, focus, zoom: tuple[float, float, float, float]) -> None:
    """Left panel: whole state, territory outlines and a box around the zoom window."""
    state.plot(ax=ax, color="#eef0ee", edgecolor="#263746", linewidth=0.8)
    territories.boundary.plot(ax=ax, color="#a64b32", linewidth=0.3)
    focus.boundary.plot(ax=ax, color="#1f77b4", linewidth=0.5)
    xmin, xmax, ymin, ymax = zoom
    ax.add_patch(plt.Rectangle((xmin, ymin), xmax - xmin, ymax - ymin,
                               fill=False, edgecolor=BUBBLE, linewidth=1.3))
    ax.set_xticks([])
    ax.set_yticks([])
    # geopandas labels geographic axes on every plot(); drop them, the main
    # axes carry the coordinate labels
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_title("Mato Grosso do Sul", fontsize=9)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=sorted(SOURCES), default="cases",
                    help="cases = Chapter I conflict table, mentions = all chapters")
    args = ap.parse_args()
    src = SOURCES[args.source]

    counts = counts_by_territory(src["csv"])
    state, territories, focus = load_layers()

    missing = sorted(set(focus["TI_CLEAN"]) - set(counts.index))
    if missing:
        # a focus territory with no count would silently vanish from the map
        print(f"warning: focus territories with no {src['noun']}: {missing}")

    fig = plt.figure(figsize=(13, 8.5))
    gs = fig.add_gridspec(1, 2, width_ratios=(1, 3.1), wspace=0.06)
    overview = fig.add_subplot(gs[0, 0])
    ax = fig.add_subplot(gs[0, 1])

    add_base(ax, state, territories, focus, fill_state=True)

    for _, row in focus.iterrows():
        ti = row["TI_CLEAN"]
        n = int(counts.get(ti, 0))
        x, y = anchor(row.geometry)
        if n:
            ax.scatter([x], [y], s=src["scale"] * n, color=BUBBLE, alpha=0.55,
                       edgecolor=BUBBLE_EDGE, linewidth=1.0, zorder=6)
        dx, dy, ha, width = LABELS.get(ti, (8, 4, "left", 20))
        ax.annotate(label_text(ti, n, width), xy=(x, y), xytext=(dx, dy),
                    textcoords="offset points", fontsize=8.5,
                    ha=ha, va="center", zorder=7)

    handles = [ax.scatter([], [], s=src["scale"] * n, color=BUBBLE, alpha=0.55,
                          edgecolor=BUBBLE_EDGE, linewidth=1.0, label=str(n))
               for n in src["legend"]]
    fig.legend(handles=handles,
               title=f"CIMI {src['noun_plural']}, {src['period']}", loc="lower center",
               bbox_to_anchor=(0.55, 0.0), ncol=len(src["legend"]), frameon=False,
               scatterpoints=1, handletextpad=1.0, columnspacing=2.4,
               title_fontsize=9, fontsize=9)

    xmin, ymin, xmax, ymax = focus.total_bounds
    zoom = (xmin - PAD_X, xmax + PAD_X, ymin - PAD_Y, ymax + PAD_Y)
    ax.set_xlim(zoom[0], zoom[1])
    ax.set_ylim(zoom[2], zoom[3])
    draw_overview(overview, state, territories, focus, zoom)

    ax.set_title(f"CIMI {src['noun_plural']} in the ten focus Guarani-Kaiowá "
                 f"territories,\nbubble area proportional to the count "
                 f"({int(counts.sum())} {src['noun_plural']}; {src['scope']})")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    fig.subplots_adjust(left=0.04, right=0.99, top=0.90, bottom=0.13, wspace=0.04)

    FIGS.mkdir(parents=True, exist_ok=True)
    stem = src["stem"]
    for ext in ("png", "svg"):
        fig.savefig(FIGS / f"{stem}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(counts.to_string())
    print(f"total {int(counts.sum())} {src['noun_plural']} -> {FIGS / f'{stem}.png'} and .svg")


if __name__ == "__main__":
    main()
