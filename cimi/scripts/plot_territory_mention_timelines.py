#!/usr/bin/env python3
"""Figure: CIMI mention timeline for one focus territory, 2008-2025.

Input : data/derived/cimi_mentions_focus_territories.csv
        (from extract_territory_mentions.py)
        data/derived/funai_focus_territories_inventory.csv (demarcation date)
        data/derived/cimi_ms_occupation_shares.csv (occupied share, 2020)
Output: out/figures/<TI>/cimi_mention_timeline.png/.svg

One row per conflict class; each marker is a mention in a CIMI report. Filled
circles are case records (Chapters I-III tables), open squares are mentions in
running text (executive summary, introduction, articles). Marker colour is the
chapter the mention sits in. The dashed line marks the FUNAI first legal act.
The lower strip counts mentions per report year, stacked by chapter.

The reusable entry point is `plot_territory_timeline(ti_clean, df, outdir)`;
`main()` runs it for every focus territory.

Usage, from the project root:

    ./.cimi-venv/bin/python3 scripts/plot_territory_mention_timelines.py
    ./.cimi-venv/bin/python3 scripts/plot_territory_mention_timelines.py --ti GUYRAROKA
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ti_names  # noqa: E402
from extract_territory_mentions import CLASS_ORDER  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived"
FIGS = ROOT / "out/figures"

YEARS = list(range(2008, 2026))

LABELS = {
    "demarcacao_omissao_judicializacao": "Demarcation and omission",
    "grilagem_posse_especulacao": "Land grabbing and possession",
    "agropecuaria_monocultivo_agrotoxico": "Farming and agrochemicals",
    "desmatamento_incendios_queimadas": "Deforestation and fire",
    "exploracao_ilegal_recursos": "Illegal extraction",
    "garimpo_mineracao": "Mining",
    "grandes_empreendimentos_infraestrutura": "Infrastructure projects",
    "violencia_ameacas_danos": "Violence and threats",
    "outros": "No land signal",
}
LANES = list(reversed(CLASS_ORDER))          # violence on top, no-signal at the bottom

CHAPTER_COLORS = {
    "I": "#2b6cb0",      # violência contra o patrimônio
    "II": "#c53030",     # violência contra a pessoa
    "III": "#2c7a7b",    # omissão do poder público
    "IV": "#6b46c1",     # povos isolados
    "V": "#b7791f",      # memória e justiça
    "front": "#718096",  # sumário executivo, apresentação, artigos
}
CHAPTER_LABELS = {
    "I": "Ch. I property",
    "II": "Ch. II person",
    "III": "Ch. III omission",
    "IV": "Ch. IV isolated",
    "V": "Ch. V memory",
    "front": "Front matter",
}
CHAPTER_ORDER = ["I", "II", "III", "IV", "V", "front"]


def slug_dir(ti_clean: str) -> str:
    """Directory name under out/figures, as the MapBiomas figures already use."""
    s = unicodedata.normalize("NFKD", ti_clean).encode("ascii", "ignore").decode().upper()
    s = re.sub(r"[^A-Z0-9]+", "_", s)
    return s.strip("_")


def territory_meta(ti_clean: str) -> dict:
    meta = {"area_ha": None, "stage": "", "defined_year": None, "occupied_pct": None}
    inventory = DERIVED / "funai_focus_territories_inventory.csv"
    if inventory.exists():
        row = pd.read_csv(inventory).loc[lambda d: d["TI_CLEAN"] == ti_clean]
        if not row.empty:
            r = row.iloc[0]
            meta["area_ha"] = float(r["funai_area_official_ha"])
            meta["stage"] = ti_names.stage_en(r["fase_ti"])
            if pd.notna(r["defined_date"]):
                meta["defined_year"] = int(pd.to_datetime(r["defined_date"]).year)
    shares = DERIVED / "cimi_ms_occupation_shares.csv"
    if shares.exists():
        row = pd.read_csv(shares).loc[lambda d: d["territory"].str.contains(
            ti_clean.split()[0].title(), case=False, regex=False)]
        if not row.empty:
            meta["occupied_pct"] = float(row["share_pct"].iloc[0])
    return meta


def plot_territory_timeline(ti_clean: str, df: pd.DataFrame, outdir: Path | None = None) -> Path:
    """Draw the CIMI mention timeline of one territory and save PNG and SVG."""
    outdir = Path(outdir) if outdir else FIGS / slug_dir(ti_clean)
    outdir.mkdir(parents=True, exist_ok=True)
    data = df.loc[df["TI_CLEAN"] == ti_clean].copy()
    data["chapter"] = data["chapter"].fillna("front").replace("", "front")
    data["lane"] = data["conflict_class"].map({c: i for i, c in enumerate(LANES)})
    meta = territory_meta(ti_clean)

    records = data[data["mention_kind"] == "record"]
    prose = data[data["mention_kind"] == "prose"]
    tables = data[data["mention_kind"] == "table"]

    fig = plt.figure(figsize=(11, 5.6))
    grid = fig.add_gridspec(2, 1, height_ratios=[4, 1], hspace=0.08)
    ax = fig.add_subplot(grid[0])
    ax2 = fig.add_subplot(grid[1], sharex=ax)

    # lanes
    for i, cls in enumerate(LANES):
        ax.axhline(i, color="#e2e8f0", linewidth=0.8, zorder=0)
    ax.set_yticks(range(len(LANES)))
    ax.set_yticklabels([LABELS[c] for c in LANES], fontsize=8)
    ax.set_ylim(-0.85, len(LANES) - 0.4)

    # status tables: small tick per year and lane
    for (year, lane), group in tables.groupby(["data_year", "lane"]):
        ax.scatter(year, lane, marker="|", s=26 + 10 * len(group),
                   color="#a0aec0", linewidths=0.9, alpha=0.9, zorder=2)
    # prose mentions: one open square per year and lane, sized by count
    for (year, lane), group in prose.groupby(["data_year", "lane"]):
        ax.scatter(year, lane, marker="s", s=18 + 7 * len(group), facecolors="none",
                   edgecolors=CHAPTER_COLORS[group["chapter"].iloc[0]], linewidths=0.9,
                   alpha=0.7, zorder=2)
    # case records: circles, jittered inside the lane when a year repeats
    for (year, lane), group in records.groupby(["data_year", "lane"]):
        n = len(group)
        offsets = [0.0] if n == 1 else [(-0.16 + 0.32 * k / (n - 1)) for k in range(n)]
        for (_, row), off in zip(group.iterrows(), offsets):
            ax.scatter(row["data_year"], lane + off, s=42 + 12 * (row["repeats"] - 1),
                       color=CHAPTER_COLORS[row["chapter"]], edgecolor="white",
                       linewidth=0.5, zorder=3)

    if meta["defined_year"]:
        year = meta["defined_year"]
        if year >= YEARS[0]:
            ax.axvline(year, color="black", linewidth=1.1, linestyle="--", zorder=1)
            ax.text(year + 0.2, -0.55, f"FUNAI {year}", fontsize=7,
                    va="bottom", ha="left")
        else:
            ax.text(YEARS[0] - 0.4, -0.55, f"FUNAI {year} (before the series)",
                    fontsize=7, va="bottom", ha="left")

    n_rec, n_prose, n_table = len(records), len(prose), len(tables)
    subtitle = []
    if meta["area_ha"]:
        subtitle.append(f"{meta['area_ha']:,.0f} ha")
    if meta["stage"]:
        subtitle.append(f"current stage: {meta['stage']}")
    if meta["occupied_pct"] is not None:
        subtitle.append(f"occupied in 2020: {meta['occupied_pct']:.2f}%")
    ax.set_title(
        f"{ti_clean.title()} — mentions in the CIMI reports, 2008-2025\n"
        f"{n_rec} case records · {n_prose} prose mentions · "
        f"{n_table} rows in a pending-status table"
        + ("\n" + " · ".join(subtitle) if subtitle else ""),
        fontsize=10.5, loc="left",
    )
    ax.tick_params(labelbottom=False, labelsize=8)

    # chapter legend
    handles = [Patch(facecolor=CHAPTER_COLORS[c], label=CHAPTER_LABELS[c]) for c in CHAPTER_ORDER]
    handles += [
        Line2D([], [], marker="o", linestyle="", markersize=6, color="#4a5568",
               label="case record"),
        Line2D([], [], marker="s", linestyle="", markersize=6, markerfacecolor="none",
               markeredgecolor="#4a5568", label="prose mention"),
        Line2D([], [], marker="|", linestyle="", markersize=7, color="#a0aec0",
               label="pending-status table"),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1.0),
              fontsize=7, frameon=False, title="Chapter / kind", title_fontsize=7.5)

    # bottom strip: mentions per report year, stacked by chapter
    years = sorted(set(data["data_year"]))
    bottom = {c: [0] * len(years) for c in CHAPTER_ORDER}
    for (year, chapter), group in data.groupby(["data_year", "chapter"]):
        bottom[chapter][years.index(year)] = len(group)
    bottoms = [0] * len(years)
    for chapter in CHAPTER_ORDER:
        ax2.bar(years, bottom[chapter], bottom=bottoms, width=0.75,
                color=CHAPTER_COLORS[chapter], edgecolor="white", linewidth=0.4)
        bottoms = [b + v for b, v in zip(bottoms, bottom[chapter])]
    ax2.set_ylim(0, max(bottoms) * 1.18 if max(bottoms) else 1)
    ax2.set_ylabel("mentions", fontsize=8)
    ax2.tick_params(labelsize=8)
    ax2.set_xlabel("CIMI report year", fontsize=8.5)
    ax2.set_xlim(YEARS[0] - 0.6, YEARS[-1] + 0.6)
    ax2.set_xticks(YEARS)
    ax2.set_xticklabels(YEARS, rotation=90)

    paths = []
    for ext in ("png", "svg"):
        path = outdir / f"cimi_mention_timeline.{ext}"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        paths.append(path)
    plt.close(fig)
    return paths[0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ti", action="append", help="TI_CLEAN to plot (default: all ten)")
    ap.add_argument("--csv", type=Path,
                    default=DERIVED / "cimi_mentions_focus_territories.csv")
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    targets = args.ti or ti_names.FOCUS_TERRITORIES
    for ti in targets:
        path = plot_territory_timeline(ti, df, args.out_dir)
        print(f"{ti:<26}{path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
