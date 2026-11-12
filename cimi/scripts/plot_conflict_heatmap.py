"""Figure: CIMI conflict cases per territory and year, Kaiowá in Mato Grosso do Sul.

Input : data/derived/cimi_kaiowa_ms_conflicts.csv
        data/derived/cimi_kaiowa_ms_conflicts_focus5.csv
Output: out/figs/cimi_kaiowa_conflict_heatmap.png/.svg        (all Kaiowá TIs)
        out/figs/cimi_kaiowa_conflict_heatmap_focus5.png/.svg (focus territories)

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
FIGS = ROOT / "out/figs"

GREY = "#d9d9d9"


def heatmap_cases(df: pd.DataFrame, title: str, stem: str,
                  year_col: str = "year", ti_col: str = "TI_CLEAN",
                  color_col: str = "conflict-type-major") -> None:
    counts = df.groupby([ti_col, year_col]).size()
    modal = (df.groupby([ti_col, year_col])[color_col]
               .agg(lambda s: s.mode().iat[0] if len(s.mode()) else np.nan))

    years = sorted(counts.index.get_level_values(year_col).unique())
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
    ax.pcolormesh(np.arange(len(years) + 1), np.arange(len(tis) + 1),
                  np.ma.masked_invalid(type_mat),
                  cmap=cmap, norm=norm, edgecolors="white")

    for i in range(len(tis)):
        for j in range(len(years)):
            n = int(count_mat[i, j])
            if n:
                ax.text(j + 0.5, i + 0.5, str(n), ha="center", va="center",
                        fontsize=9, fontweight="bold")

    ax.set_xticks(np.arange(len(years)) + 0.5, years, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(tis)) + 0.5, tis)
    ax.invert_yaxis()
    ax.set_xlabel("Ano")
    ax.set_ylabel("TI")
    ax.set_title(title, pad=12)

    handles = [mpatches.Patch(color=cmap(i), label=t) for i, t in enumerate(types)]
    handles.append(mpatches.Patch(color=GREY, label="sem casos"))
    ax.legend(handles=handles, title=color_col,
              bbox_to_anchor=(1.02, 1), loc="upper left")

    FIGS.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(FIGS / f"{stem}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {FIGS / f'{stem}.png'} and .svg")


def main() -> None:
    all_rows = pd.read_csv(ROOT / "data/derived/cimi_kaiowa_ms_conflicts.csv")
    heatmap_cases(all_rows,
                  "Casos por TI e ano, Kaiowá em MS (cor = tipo mais frequente)",
                  "cimi_kaiowa_conflict_heatmap")

    focus = pd.read_csv(ROOT / "data/derived/cimi_kaiowa_ms_conflicts_focus5.csv")
    heatmap_cases(focus,
                  "Casos por TI e ano, territórios de foco (cor = tipo mais frequente)",
                  "cimi_kaiowa_conflict_heatmap_focus5")


if __name__ == "__main__":
    main()
