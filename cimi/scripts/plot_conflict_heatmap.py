"""Figure: CIMI conflict cases per territory and year, Kaiowá in Mato Grosso do Sul.

Input : data/derived/cimi_kaiowa_ms_conflicts.csv
        data/derived/cimi_kaiowa_ms_conflicts_focus_territories.csv
Output: out/figures/cimi_kaiowa_conflict_heatmap.png/.svg        (all Kaiowá TIs)
        out/figures/cimi_kaiowa_conflict_heatmap_focus_territories.png/.svg (focus territories)

Cell colour = the conflict-type-major that appears most in that cell; a
single-case cell takes that case's own colour; empty cells stay grey.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm

ROOT = Path(__file__).resolve().parents[1]
FIGS = ROOT / "out/figures"

GREY = "#d9d9d9"


def heatmap_cases(df: pd.DataFrame, title: str, stem: str,
                  year_col: str = "year", ti_col: str = "TI_CLEAN",
                  color_col: str = "conflict-type-major",
                  legend_side: str = "bottom",
                  years: list[int] | None = None) -> None:
    counts = df.groupby([ti_col, year_col]).size()
    modal = (df.groupby([ti_col, year_col])[color_col]
               .agg(lambda s: s.mode().iat[0] if len(s.mode()) else np.nan))

    if years is None:
        years = list(range(int(df[year_col].min()), int(df[year_col].max()) + 1))
    tis = sorted(counts.index.get_level_values(ti_col).unique(), key=str.lower)

    count_mat = np.zeros((len(tis), len(years)))
    type_mat = np.full((len(tis), len(years)), np.nan, dtype=float)

    types = sorted(df[color_col].dropna().unique(), key=str.lower)
    t2i = {t: i for i, t in enumerate(types)}

    for (ti, yr), n in counts.items():
        i, j = tis.index(ti), years.index(yr)
        count_mat[i, j] = n
        m = modal.loc[(ti, yr)]
        if pd.notna(m):
            type_mat[i, j] = t2i[m]

    cmap = plt.get_cmap("tab10", len(types)).copy()
    cmap.set_bad(GREY)
    norm = BoundaryNorm(np.arange(-0.5, len(types) + 0.5, 1), len(types))

    fig, ax = plt.subplots(figsize=(1.0 + 0.8 * len(years), 0.5 + 0.5 * len(tis)))
    ax.tick_params(labelsize=15)
    ax.pcolormesh(np.arange(len(years) + 1), np.arange(len(tis) + 1),
                  np.ma.masked_invalid(type_mat),
                  cmap=cmap, norm=norm, edgecolors="white")

    for i in range(len(tis)):
        for j in range(len(years)):
            n = int(count_mat[i, j])
            if n:
                ax.text(j + 0.5, i + 0.5, str(n), ha="center", va="center",
                        fontsize=13, fontweight="bold")

    ax.set_xticks(np.arange(len(years)) + 0.5, years, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(tis)) + 0.5, tis)
    ax.invert_yaxis()
    ax.set_xlabel("Year", fontsize=16)
    ax.set_ylabel("Territory", fontsize=16)
    ax.set_title(title, pad=12, fontsize=18)

    # CIMI writes the categories in Portuguese; the figure reads in English but
    # the underlying data column keeps CIMI's own strings
    def legend_label(t: str) -> str:
        if t == "invasões possessórias, exploração ilegal de recursos naturais e danos diversos ao patrimônio":
            return ("possessory invasions, illegal resource\n"
                    "extraction, damage to property")
        if t == "conflitos relativos a direitos territoriais":
            return "land-rights conflicts"
        if t == "omissão e morosidade na regularização de terras":
            return "state omission and delay in land regularisation"
        return t

    handles = [mpatches.Patch(color=cmap(i), label=legend_label(t)) for i, t in enumerate(types)]
    handles.append(mpatches.Patch(color=GREY, label="no cases"))
    if legend_side == "right":
        ax.legend(handles=handles, title="Legend", fontsize=15, title_fontsize=16,
                  bbox_to_anchor=(1.02, 1), loc="upper left")
    else:
        ax.legend(handles=handles, title="Legend", fontsize=15, title_fontsize=16,
                  ncol=1, loc="upper center", bbox_to_anchor=(0.5, -0.28),
                  alignment="left")

    FIGS.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(FIGS / f"{stem}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {FIGS / f'{stem}.png'} and .svg")


def main() -> None:
    all_rows = pd.read_csv(ROOT / "data/derived/cimi_kaiowa_ms_conflicts.csv")
    focus = pd.read_csv(ROOT / "data/derived/cimi_kaiowa_ms_conflicts_focus_territories.csv")

    # Both figures share one year axis so they can be read side by side, and
    # years without cases stay visible as empty columns instead of closing up.
    first = int(min(all_rows["year"].min(), focus["year"].min()))
    last = int(max(all_rows["year"].max(), focus["year"].max()))
    years = list(range(first, last + 1))

    heatmap_cases(all_rows,
                  "Cases per territory and year, Kaiowá in Mato Grosso do Sul\n"
                  "(colour = most frequent conflict type)",
                  "cimi_kaiowa_conflict_heatmap",
                  legend_side="right",
                  years=years)

    heatmap_cases(focus,
                  "Cases per territory and year, focus territories\n"
                  "(colour = most frequent conflict type)",
                  "cimi_kaiowa_conflict_heatmap_focus_territories",
                  years=years)


if __name__ == "__main__":
    main()
