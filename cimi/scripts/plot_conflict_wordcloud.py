"""Figure: word cloud of the CIMI conflict-type-minor labels, Kaiowá rows in MS.

Input : data/derived/cimi_kaiowa_ms_conflicts.csv    (prepare_kaiowa_dataset.py)
Output: out/figures/cimi_kaiowa_conflict_types_wordcloud.png/.svg
        data/derived/cimi_kaiowa_conflict_type_counts.csv

Rows hold several labels separated by ';'; every fragment is counted on its own.
Labels are accent-folded and lower-cased, and whole phrases stay whole (the
cloud is built from counts, never from raw text tokenisation).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from wordcloud import WordCloud

ROOT = Path(__file__).resolve().parents[1]
CONFLICTS = ROOT / "data/derived/cimi_kaiowa_ms_conflicts.csv"
COUNTS_OUT = ROOT / "data/derived/cimi_kaiowa_conflict_type_counts.csv"
FIGS = ROOT / "out/figures"
STEM = "cimi_kaiowa_conflict_types_wordcloud"


def norm_txt(value: str) -> str:
    s = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    s = s.lower()
    return re.sub(r"\s+", " ", s).strip()


def main() -> None:
    if not CONFLICTS.exists():
        raise SystemExit(f"Missing input: {CONFLICTS}")

    # the Kaiowá-MS filter and TI_CLEAN live in prepare_kaiowa_dataset.py; do not
    # restate them here, or the two definitions drift apart
    df = pd.read_csv(CONFLICTS)

    labels = (df["conflict-type-minor"]
              .dropna()
              .str.split(";")
              .explode()
              .map(norm_txt))
    labels = labels[labels != ""]
    freq = Counter(labels)

    COUNTS_OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(sorted(freq.items(), key=lambda kv: (-kv[1], kv[0])),
                 columns=["conflict_type", "n"]).to_csv(COUNTS_OUT, index=False)

    wc = WordCloud(width=1200, height=600, background_color="white",
                   random_state=42).generate_from_frequencies(freq)

    fig = plt.figure(figsize=(12, 6))
    plt.imshow(wc, interpolation="bilinear")
    plt.axis("off")
    fig.tight_layout()

    FIGS.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(FIGS / f"{STEM}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {FIGS / f'{STEM}.png'} and .svg")
    print(f"wrote {COUNTS_OUT} ({len(freq)} distinct labels)")


if __name__ == "__main__":
    main()
