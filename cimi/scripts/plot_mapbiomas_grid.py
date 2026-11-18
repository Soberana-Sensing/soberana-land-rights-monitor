"""Figure: MapBiomas land-cover grid, all focus territories, 1985-2025.

Input : data/derived/mapbiomas_landcover_<ti>.csv  (cache from
        plot_mapbiomas_landcover.py; run that first for every territory)
        data/derived/funai_focus_territories_inventory.csv (demarcation dates)
Output: out/figures/mapbiomas_landcover_grid_5x2.png/.svg

5 rows x 2 cols, one stacked-area panel per focus territory, in the
FOCUS_TERRITORIES order from config/ti_names.yaml. Style matches
plot_mapbiomas_landcover.py: same groups, colors and white boundary lines,
plus a dashed line at the FUNAI demarcation date. One shared legend.

No Earth Engine call: everything comes from the cache CSVs.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

import ti_names
from plot_mapbiomas_landcover import COLORS, GIDS, GROUPS, LABELS, YEARS, slug

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived"
FIGS = ROOT / "out/figures"
NROWS, NCOLS = 5, 2


def demarcation_year(ti_clean: str) -> tuple[int | None, str]:
    """FUNAI first legal act year from the focus inventory."""
    inventory = DERIVED / "funai_focus_territories_inventory.csv"
    if not inventory.exists():
        return None, ""
    row = pd.read_csv(inventory).loc[lambda d: d["TI_CLEAN"] == ti_clean]
    if row.empty or pd.isna(row["defined_date"].iloc[0]):
        return None, ""
    r = row.iloc[0]
    label = f"FUNAI {ti_names.stage_en(r['defined_stage'])}"
    phase = r.get("fase_ti", "")
    if isinstance(phase, str) and phase:
        label += f" · current stage: {ti_names.stage_en(phase)}"
    return int(pd.to_datetime(r["defined_date"]).year), label


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
    ax.set_title(ti_clean.title(), fontsize=11, fontweight="bold")
    ax.tick_params(labelsize=8)

    year, label = demarcation_year(ti_clean)
    if year:
        ax.axvline(year, color="black", linewidth=1.2, linestyle="--", zorder=5)
        ax.text(year + 0.4, ax.get_ylim()[1] * 0.95, label, color="black",
                fontsize=6.5, ha="left", va="top")


def main() -> None:
    territories = ti_names.FOCUS_TERRITORIES
    if len(territories) != NROWS * NCOLS:
        raise SystemExit(f"{len(territories)} focus territories, grid is "
                         f"{NROWS}x{NCOLS}={NROWS * NCOLS}; update the script")

    fig, axes = plt.subplots(NROWS, NCOLS, figsize=(13, 17),
                             sharex=True, sharey=False)
    handles = None
    for ax, ti in zip(axes.flat, territories):
        csv = DERIVED / f"mapbiomas_landcover_{slug(ti).lower()}.csv"
        if not csv.exists():
            raise SystemExit(f"Missing cache {csv}; run "
                             f"plot_mapbiomas_landcover.py --ti {ti!r} first")
        df = pd.read_csv(csv)
        panel(ax, df, ti)
        if handles is None:
            handles, _ = ax.get_legend_handles_labels()

    # shared legend: one labeled Patch per group, from a proxy handle
    from matplotlib.patches import Patch
    legend = [Patch(facecolor=COLORS[g], label=LABELS[g]) for g in GIDS]
    fig.legend(handles=legend, loc="upper center", bbox_to_anchor=(0.5, 0.94),
               ncol=4, fontsize=10, title=f"Class ({YEARS[-1]})",
               title_fontsize=11, frameon=False)
    fig.suptitle("Land cover in the focus Guarani and Kaiowá territories\n"
                 "MapBiomas Collection 11, 1985-2025 (hectares inside each territory); "
                 "dashed line: FUNAI demarcation",
                 fontsize=13, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.915))

    FIGS.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(FIGS / f"mapbiomas_landcover_grid_5x2.{ext}",
                    dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {FIGS / 'mapbiomas_landcover_grid_5x2.png'} and .svg")


if __name__ == "__main__":
    main()
