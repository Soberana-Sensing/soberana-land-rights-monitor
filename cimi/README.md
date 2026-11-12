# CIMI PROJECT

Notebook `notebook.ipynb` is the scratch space where figures were designed; the
scripts below are the canonical pipeline and reproduce everything it did. When
a figure or table needs a change, change the script, not the notebook.

## Name conventions

`config/ti_names.yaml` holds the territory-name data: the five focus
territories, the CIMI spelling variants, and the FUNAI-to-CIMI name mapping.
`scripts/ti_names.py` loads it and holds the normalisation rules (`norm_ti`).
Every script imports from there; nothing else defines a TI mapping. If a name
needs to change, change the YAML, not the code.

## Setup

1. Create a conda environment (install conda if you dont have it, we prefer miniconda3). All commands below assume you are ROOT of your project (`~/cimi/`)
```conda create -p ./.cimi-venv```

2. Install the pinned dependencies:
```./.cimi-venv/bin/pip install -r requirements.txt```

3. Add the reports you want to use for your analysis to `/docs/pdf`.

## Pipeline

Run from the repository root, in this order.

```bash
./.cimi-venv/bin/python3 scripts/pdftext.py --out-dir docs/cimi-reports/txt docs/cimi-reports/pdf/*.pdf
```

Converts the PDF reports to text.

```bash
./.cimi-venv/bin/python3 scripts/chapter1_txt_to_csv.py docs/cimi-reports/txt -o data/derived/chapter1_conflicts.csv
```

Extracts Chapter 1 tables into a single CSV with the columns
`year, conflict-type-major, conflict-type-minor, state, TI, povo, description,
source`. It accepts one `.txt`, several, or a folder, and prints a per-file
summary on stderr comparing parsed case counts against the totals printed in
each report; add `--strict` to turn any mismatch into an error.

```bash
./.cimi-venv/bin/python3 scripts/build_funai_inventory.py
```

Reads the FUNAI shapefile, its stage-dates GeoJSON and the state boundary, keeps
the Kaiowá territories that intersect Mato Grosso do Sul, and writes
1. `data/derived/funai_territorial_inventory_ms.csv`, one row per territory
   with the official area, the stage reached, the `TI_CLEAN` name and the area
   clipped to the state, and
2. `data/derived/funai_kaiowa_ms_clipped.geojson`, the same rows with geometry.
No other script re-clips the shapefile.

```bash
./.cimi-venv/bin/python3 scripts/prepare_kaiowa_dataset.py
```

Adds `TI_CLEAN` to the conflict rows (Kaiowá, MS) using the name conventions,
prints which territories exist on only one side of the FUNAI/CIMI pair, and
writes the analysis datasets:
1. `data/derived/cimi_kaiowa_ms_conflicts.csv` — all Kaiowá-in-MS conflict rows.
2. `data/derived/cimi_kaiowa_ms_conflicts_focus5.csv` — the five focus
   territories only.
3. `data/derived/funai_focus5_inventory.csv` — the focus territories' FUNAI rows.
4. `data/derived/funai_focus5_territories.geojson` — their clipped polygons.
Outputs 3 and 4 are the inputs for the later MapBiomas and Sentinel-1 analyses.

```bash
./.cimi-venv/bin/python3 scripts/plot_conflict_heatmap.py
```

Territory-year grid of CIMI cases, Kaiowá in MS. One number per cell, colour =
the `conflict-type-major` that appears most in that cell; a single-case cell
takes that case's own colour; empty cells stay grey. Writes
`out/figs/cimi_kaiowa_conflict_heatmap.*` and
`out/figs/cimi_kaiowa_conflict_heatmap_focus5.*` (PNG at 300 dpi and SVG).

```bash
./.cimi-venv/bin/python3 scripts/plot_occupation_lollipop.py
```

Share of each territory the community occupies, as CIMI reports it (first
published in the 2020 edition). Writes
`out/figs/cimi_kaiowa_occupation_share.*`.

```bash
./.cimi-venv/bin/python3 scripts/plot_conflict_wordcloud.py
```

Word cloud of the `conflict-type-minor` labels, Kaiowá rows in Mato Grosso do
Sul. Labels split on `;` count separately, are accent-folded and lower-cased,
and whole phrases stay whole (the cloud is built from counts, never from raw
text). Writes `out/figs/cimi_kaiowa_conflict_types_wordcloud.*` and the label
counts `data/derived/cimi_kaiowa_conflict_type_counts.csv`.

```bash
./.cimi-venv/bin/python3 scripts/plot_funai_map.py
```

Map of the Kaiowá territories over the state boundary, focus five in blue with
labels. Writes `out/figs/funai_kaiowa_ms_map.*`.

```bash
./.cimi-venv/bin/python3 scripts/plot_mapbiomas_landcover.py --ti "ARROIO KORA"
```

Land cover inside one focus territory, 1985-2025, from MapBiomas Collection 11
(30 m annual) via Earth Engine, as a stacked-area chart in hectares. The 33
classes collapse into six groups (native vegetation, pasture, agriculture,
mosaic of uses, forest plantation, other non-vegetated) plus water and a
non-observed bucket. The title carries the territory area and the community's
effective occupation from the CIMI shares (2020, the only edition with complete
coverage), and a red dashed line marks the FUNAI demarcation date
(`defined_date`, the first legal act, from the focus inventory). `--ti` takes
any `TI_CLEAN` name from `funai_focus5_territories.geojson`; `--refresh`
requeries GEE, otherwise the run reuses the cache CSV
`data/derived/mapbiomas_landcover_<ti>.csv`. Writes
`out/figs/<TI>/mapbiomas_landcover_1985_2025.*` (PNG at 300 dpi and SVG).

## Scripts and files

| Piece | What it is |
|---|---|
| `config/ti_names.yaml` | Territory-name data: focus five, CIMI variants, FUNAI-to-CIMI mapping, open questions. The single source of truth. |
| `scripts/ti_names.py` | Loads the YAML and holds `norm_ti`, `cimi_ti`, `funai_ti`. Imported by every script that touches TI names. |
| `scripts/pdftext.py` | PDF reports to text. |
| `scripts/chapter1_txt_to_csv.py` | Chapter 1 tables to `data/derived/chapter1_conflicts.csv`. |
| `scripts/build_funai_inventory.py` | FUNAI inventory CSV and the clipped Kaiowá GeoJSON. |
| `scripts/prepare_kaiowa_dataset.py` | `TI_CLEAN` on both sides, side-by-side name check, focus-5 extracts. |
| `scripts/plot_conflict_heatmap.py` | Figure: cases per TI and year, all Kaiowá and focus five. |
| `scripts/plot_occupation_lollipop.py` | Figure: occupied share per territory. |
| `scripts/plot_conflict_wordcloud.py` | Figure + counts: conflict-type-minor labels. |
| `scripts/plot_funai_map.py` | Figure: territories over the state, focus five highlighted. |
| `scripts/plot_mapbiomas_landcover.py` | Figure + cache CSV: MapBiomas C11 land-cover share per group, 1985-2025, one territory per run. |


