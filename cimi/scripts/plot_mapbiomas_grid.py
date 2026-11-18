"""Figure: MapBiomas land-cover grid, all focus territories, 1985-2025.

Input : data/derived/mapbiomas_landcover_<ti>.csv  (cache from
        plot_mapbiomas_landcover.py; run that first for every territory)
        data/derived/funai_focus_territories_inventory.csv (legal-act dates)
Output: out/figures/mapbiomas_landcover_grid_5x2.png/.svg

5 rows x 2 cols, one stacked-area panel per focus territory, in the
FOCUS_TERRITORIES order from config/ti_names.yaml. Style matches
plot_mapbiomas_landcover.py: same groups, colors and white boundary lines,
plus one coloured dashed line per FUNAI legal act recorded for that territory
and the current stage in each panel title. One shared legend for the classes
and a second for the legal acts.

No Earth Engine call: everything comes from the cache CSVs.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import pandas as pd

import ti_names
from plot_mapbiomas_landcover import (COLORS, GIDS, GROUPS, LABELS, STAGE_LINES,
                                     YEARS, legal_acts, slug)

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived"
FIGS = ROOT / "out/figures"
NROWS, NCOLS = 5, 2


def panel(ax: plt.Axes, df: pd.DataFrame, ti_clean: str) -> None:
    wide = df.pivot(index="year", columns="group", values="ha").reindex(
        index=YEARS, columns=GIDS).fillna(0)
    ax.stackplot(YEARS, [wide[g].to_numpy() for g in GIDS],
                 colors=[COLORS[g] for g in GIDS])
    cumulative = wide.cumsum(axis=1)
    for g in GIDS:
        ax.plot(YEARS, cumulative[g], color="white", linewidth=1.0)
    ax.set_xlim(YEARS[0], YEARS[-1])
    ax.set_ylim(0, wide.sum(axis=1).max())
    ax.tick_params(labelsize=8)

    acts, phase = legal_acts(ti_clean)
    for _, colour, _, year in acts:
        ax.axvline(year, color=colour, linewidth=1.2, linestyle=(0, (6, 3)), zorder=5)

    stage_text = f" (current stage: {ti_names.stage_en(phase)})" if phase else ""
    ax.set_title(f"{ti_clean.title()}{stage_text}", fontsize=10, fontweight="bold")


def main() -> None:
    territories = ti_names.FOCUS_TERRITORIES
    if len(territories) != NROWS * NCOLS:
        raise SystemExit(f"{len(territories)} focus territories, grid is "
                         f"{NROWS}x{NCOLS}={NROWS * NCOLS}; update the script")

    fig, axes = plt.subplots(NROWS, NCOLS, figsize=(13, 17),
                             sharex=True, sharey=False)
    for ax, ti in zip(axes.flat, territories):
        csv = DERIVED / f"mapbiomas_landcover_{slug(ti).lower()}.csv"
        if not csv.exists():
            raise SystemExit(f"Missing cache {csv}; run "
                             f"plot_mapbiomas_landcover.py --ti {ti!r} first")
        df = pd.read_csv(csv)
        panel(ax, df, ti)

    # shared legend: one labeled Patch per group, from a proxy handle
    from matplotlib.patches import Patch
    legend = [Patch(facecolor=COLORS[g], label=LABELS[g]) for g in GIDS]
    fig.legend(handles=legend, loc="upper center", bbox_to_anchor=(0.5, 0.945),
               ncol=4, fontsize=10, title=f"Class ({YEARS[-1]})",
               title_fontsize=11, frameon=False)
    stage_legend = [mlines.Line2D([], [], color=colour, linewidth=1.8,
                                  linestyle=(0, (6, 3)), label=english)
                    for _, english, colour in STAGE_LINES]
    fig.legend(handles=stage_legend, loc="upper center", bbox_to_anchor=(0.5, 0.905),
               ncol=3, fontsize=10, title="FUNAI legal act", title_fontsize=10,
               frameon=False)
    fig.suptitle("Land cover in the focus Guarani and Kaiowá territories\n"
                 "MapBiomas Collection 11, 1985-2025 (hectares inside each territory); "
                 "dashed lines: FUNAI legal acts, coloured by stage",
                 fontsize=13, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.885))

    FIGS.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(FIGS / f"mapbiomas_landcover_grid_5x2.{ext}",
                    dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {FIGS / 'mapbiomas_landcover_grid_5x2.png'} and .svg")


if __name__ == "__main__":
    main()
