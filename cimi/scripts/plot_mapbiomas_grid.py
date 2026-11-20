"""Figure: MapBiomas land-cover grid, all focus territories, 1985-2025.

Input : data/derived/mapbiomas_landcover_<ti>.csv  (cache from
        plot_mapbiomas_landcover.py; run that first for every territory)
        data/derived/funai_focus_territories_inventory.csv (legal-act dates)
Output: out/figures/mapbiomas_landcover_grid_5x2.png/.svg

5 rows x 2 cols, one stacked-area panel per focus territory, in the
FOCUS_TERRITORIES order from config/ti_names.yaml. Style matches
plot_mapbiomas_landcover.py: same groups, colors and white boundary lines,
plus one coloured line per FUNAI legal act recorded for that territory
(ratification solid, the earlier stages dashed) and the share of the territory
the community occupies according to CIMI (2020) in each panel title. Every
panel carries year ticks (every 5 years). One shared legend for the classes,
one for the legal status.

No Earth Engine call: everything comes from the cache CSVs.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch

import ti_names
from plot_mapbiomas_landcover import (COLORS, GIDS, LABELS, YEARS, cimi_occupied,
                                     legal_acts, slug, stage_handles,
                                     stage_linestyle)

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
    ax.set_xticks(range(YEARS[0], YEARS[-1] + 1, 5))
    ax.tick_params(labelsize=8, labelbottom=True)
    ax.set_xlabel("Year", fontsize=8)
    ax.set_ylabel("Hectares (ha)", fontsize=8)

    acts, _phase = legal_acts(ti_clean)
    for stage, _, colour, _, year in acts:
        ax.axvline(year, color=colour, linewidth=1.2,
                   linestyle=stage_linestyle(stage), zorder=5)

    cimi = cimi_occupied(ti_clean)
    occupied_text = (f" — occupied {cimi[2]:.2f}% (CIMI {cimi[3]})"
                     if cimi else "")
    ax.set_title(f"{ti_clean.title()}{occupied_text}", fontsize=10,
                 fontweight="bold")


def main() -> None:
    territories = ti_names.FOCUS_TERRITORIES
    if len(territories) != NROWS * NCOLS:
        raise SystemExit(f"{len(territories)} focus territories, grid is "
                         f"{NROWS}x{NCOLS}={NROWS * NCOLS}; update the script")

    fig, axes = plt.subplots(NROWS, NCOLS, figsize=(13, 18),
                             sharex=True, sharey=False)
    for ax, ti in zip(axes.flat, territories):
        csv = DERIVED / f"mapbiomas_landcover_{slug(ti).lower()}.csv"
        if not csv.exists():
            raise SystemExit(f"Missing cache {csv}; run "
                             f"plot_mapbiomas_landcover.py --ti {ti!r} first")
        df = pd.read_csv(csv)
        panel(ax, df, ti)

    # shared legends: one labelled Patch per land-cover group, then the legal
    # status lines. The second legend sits a line below the first.
    legend = [Patch(facecolor=COLORS[g], label=LABELS[g]) for g in GIDS]
    fig.legend(handles=legend, loc="upper center", bbox_to_anchor=(0.5, 0.948),
               ncol=4, fontsize=10, title="Legend", title_fontsize=11,
               frameon=False)
    fig.legend(handles=stage_handles(), loc="upper center",
               bbox_to_anchor=(0.5, 0.888), ncol=3, fontsize=10,
               title="Legal status", title_fontsize=10, frameon=False)
    fig.suptitle("LULC per delimited territory\n"
                 "MapBiomas Collection 11, 1985-2025 (hectares inside each territory)\n"
                 "solid line: ratification; dashed lines: delimitation and declaration",
                 fontsize=12, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.875))

    FIGS.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(FIGS / f"mapbiomas_landcover_grid_5x2.{ext}",
                    dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {FIGS / 'mapbiomas_landcover_grid_5x2.png'} and .svg")


if __name__ == "__main__":
    main()
