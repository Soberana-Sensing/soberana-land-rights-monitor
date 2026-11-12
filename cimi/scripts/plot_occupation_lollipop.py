"""Figure: share of each territory the community occupies, as CIMI reports it.

Input : data/derived/cimi_ms_occupation_shares.csv
Output: out/figs/cimi_kaiowa_occupation_share.png/.svg

CIMI first publishes the figure in the 2020 edition; the CSV holds the repeats.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SHARES = ROOT / "data/derived/cimi_ms_occupation_shares.csv"
FIGS = ROOT / "out/figs"
STEM = "cimi_kaiowa_occupation_share"


def main() -> None:
    if not SHARES.exists():
        raise SystemExit(f"Missing input: {SHARES}")

    occ = pd.read_csv(SHARES)
    occ["share"] = pd.to_numeric(occ["share_pct"], errors="coerce")
    occ = occ.dropna(subset=["share"]).sort_values("share")

    rows = list(occ["territory"])
    share = occ["share"].to_numpy()
    area = occ["area_ha"].astype(float).to_numpy()
    held = occ["occupied_ha"].astype(float).to_numpy()

    fig, ax = plt.subplots(figsize=(9, 4.8))
    y = np.arange(len(rows))
    ax.hlines(y, 0, share, color="#b07a3a", linewidth=1.4)
    ax.plot(share, y, "o", color="#8c4a1f", markersize=7, zorder=3)
    for yi, v, a, h in zip(y, share, area, held):
        ax.text(v + 1.2, yi, f"{v:.2f}%  ({h:,.0f} of {a:,.0f} ha)",
                va="center", fontsize=8)
    ax.set_yticks(y)
    ax.set_yticklabels(rows, fontsize=9)
    ax.set_xlim(0, share.max() * 1.25)
    ax.set_xlabel("% of the territory occupied by the community")
    ax.set_title(
        "Share of each territory the community occupies, as CIMI reports it\n"
        f"{len(rows)} territories; CIMI first publishes the figure in the 2020 edition",
        loc="left", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color="#dddddd", linewidth=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()

    FIGS.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(FIGS / f"{STEM}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {FIGS / f'{STEM}.png'} and .svg")


if __name__ == "__main__":
    main()
