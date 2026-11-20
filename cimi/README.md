# CIMI PROJECT

When a figure or table needs a change, change the script.

Every figure label, title, legend and axis is in English. CIMI category strings
stay in the data columns; the heatmap legend translates the three
`conflict-type-major` values it draws, and the FUNAI legal stages go through
`ti_names.stage_en()` so no Portuguese stage name reaches a chart.

## Repository size

This project version-controls its sources, not only its code, so a fresh clone is
large on purpose:

| Path | Size | Why it is committed |
|---|---|---|
| `docs/cimi-reports/pdf/` | about 127 MB | The 18 CIMI reports (2008-2025) are the primary source. They are not re-downloadable from a stable archive, so they stay in git. |
| `docs/cimi-reports/txt/` | about 16 MB | Text extracted from those PDFs, committed so the parsers can run without a PDF step. Regenerable with `pdftext.py`. |
| `out/figures/` | about 20 MB | PNG and SVG exports of every figure, so a reader sees the result without running the pipeline. Regenerable by re-running the plot scripts. |
| `data/derived/` | about 8 MB | Small tables and the FUNAI GeoJSONs the figures and later analyses read. Regenerable in pipeline order. |
| `data/raw/` | excluded | The FUNAI download and the MS boundary are git-ignored; `data/raw/README.md` records where each came from. |

Expect a clone of roughly 170 MB. Nothing here needs Git LFS at this size, but a
shallow clone (`--depth 1`) is the quick way to read the code without the reports.

## Name conventions

`config/ti_names.yaml` holds the territory-name data: the ten focus
territories, the CIMI spelling variants, and the FUNAI-to-CIMI name mapping.
`scripts/ti_names.py` loads it and holds the normalisation rules (`norm_ti`).
Every script imports from there; nothing else defines a TI mapping. If a name
needs to change, change the YAML, not the code.

Two special cases in that file, both checked against the case text on
2026-11-19. `cimi_variants` folds CIMI's own renamings into one label: AMAMBAI
absorbs AMAMBAI (ANTIGA GUAPOY) and GUAPOY (the tekoha Guapoy retomada), and
LARANJEIRA NHANDERU E BOQUEIRAO (BRILHANTEPEGUA) absorbs LARANJEIRA NHANDERU
and BOQUEIRAO. `cimi_multi` is the opposite: a single record that CIMI prints
under two names, Guyraroka and Panambi-Lagoa Rica, expands to one row per
territory because the record is real in both. That is the only deliberate
double count, and it is why 209 printed cases become 210 rows.

## Setup

1. Create a conda environment (install miniconda3 if you don't have it):

   ```bash
   conda create -p ./.cimi-venv python=3.12
   ```

2. Install the pinned dependencies:

   ```bash
   ./.cimi-venv/bin/pip install -r requirements.txt
   ```

3. Add the reports you want to use for your analysis to `docs/cimi-reports/pdf/`.

## Pipeline

All commands assume you are in the project root (`cimi/`). Run in this order.

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

The 2008-2025 reports changed shape several times, and the parser handles each
form it uses. A state block can open with `BA – 2 Caso(s)` (2008), `MS – 2
casos` (2009), `MS<TAB> 1 Caso` (2013, 2014), `MATO GROSSO DO SUL  –  9 CASOS`
(2021) or `MATO GROSSO DO SUL (148)` (2022 on), and a continuation page repeats
the header. A chapter 1 section title can be wrapped over two or three lines
(`Invasões possessórias, exploração ilegal de recursos naturais` /
`e danos diversos ao patrimônio`), carries the printed page number on the cover
page, and repeats as a running header. The parser reads a section only from a
standalone heading that is a prefix of the printed title, so CIMI's own
case-type labels (`TIPO DE DANO/CONFLITO: Omissão e morosidade na demarcação da
TI`) never flip the section mid-record. Chapters II to IV repeat the same
`TERRA INDÍGENA` / `TIPO DE DANO` labels, so a chapter heading closes chapter 1
and everything after it is dropped.

```bash
./.cimi-venv/bin/python3 scripts/build_funai_inventory.py
```

Reads the FUNAI download in `data/raw/` (one GeoJSON with the polygons and the
legal-stage dates, pulled from the WFS layer `Funai:tis_poligonais_portarias`
on `geoserver.funai.gov.br`, filtered to Mato Grosso do Sul; cite FUNAI as the
source when reproducing it), keeps the territories FUNAI attributes to the
Guarani Kaiowá plus the focus territories listed in `config/ti_names.yaml`
(some attributed to the Nhandeva or the Guaraní), and writes
1. `data/derived/funai_territorial_inventory_ms.csv`, one row per territory
   with the official area, the stage reached, its date and the `TI_CLEAN`
   name,
2. `data/derived/funai_kaiowa_ms_clipped.geojson`, the same rows with geometry, and
3. `data/derived/funai_ms_territories_clipped.geojson`, every distinct territory
   name in the download (46), with geometry. Only the all-label bubble map reads
   it, to anchor labels that are not Kaiowá.

Each row carries every stage date FUNAI publishes (`data_delimitada`,
`data_declarada`, `data_homologada`, `data_regularizada`) together with the
legal act behind it (`tit_*`). `defined_date` stays the earliest of those four
dates with `defined_stage` naming which one it is; the MapBiomas figures use
the full set of dates instead. A stage without a date means FUNAI records no
act for it, not that the territory skipped the stage: Ñande Ru Marangatu has a
declaration and a ratification but no delimitation, and Potrero Guaçu only a
declaration. The download does carry `data_em_estudo`, deliberately left out
of the inventory: it is empty for 30 of the 50 features and, on Sombrerito and
Jatayvari, holds a 2012-11-20 "Portaria Migração" later than their own
delimitation.
No other script re-reads the FUNAI download; the GAUL boundary is only the map
backdrop, and no script clips to it.

```bash
./.cimi-venv/bin/python3 scripts/prepare_kaiowa_dataset.py
```

Adds `TI_CLEAN` to the conflict rows (Kaiowá, MS) using the name conventions,
prints which territories exist on only one side of the FUNAI/CIMI pair, and
writes the analysis datasets:
1. `data/derived/cimi_kaiowa_ms_conflicts.csv` — all Kaiowá-in-MS conflict rows.
2. `data/derived/cimi_kaiowa_ms_conflicts_focus_territories.csv` — the ten focus
   territories only. The focus set is selected by territory, not by the people
   label: CIMI files some Potrero Guasu and Sombrerito cases under `Guarani` or
   `Guarani Nhandeva`, and a people-based filter drops them.
3. `data/derived/funai_focus_territories_inventory.csv` — the focus territories' FUNAI rows.
4. `data/derived/funai_focus_territories.geojson` — their clipped polygons.
Outputs 3 and 4 are the inputs for the later MapBiomas and Sentinel-1 analyses.

```bash
./.cimi-venv/bin/python3 scripts/plot_conflict_heatmap.py
```

Territory-year grid of CIMI cases, Kaiowá in MS. One number per cell, colour =
the `conflict-type-major` that appears most in that cell; a single-case cell
takes that case's own colour; empty cells stay grey. Both figures share one year
axis from the first to the last year with a case, so a year without cases stays
visible as an empty column instead of closing up. Writes
`out/figures/cimi_kaiowa_conflict_heatmap.*` and
`out/figures/cimi_kaiowa_conflict_heatmap_focus_territories.*` (PNG at 300 dpi and SVG).

```bash
./.cimi-venv/bin/python3 scripts/plot_occupation_lollipop.py
```

Share of each territory the community occupies, as CIMI reports it. CIMI first
published the figure in the 2020 edition and later dropped this reporting, so
the input `data/derived/cimi_ms_occupation_shares.csv` was copied by hand from
that report and has no producing script.
Writes `out/figures/cimi_kaiowa_occupation_share.*`.

```bash
./.cimi-venv/bin/python3 scripts/plot_conflict_wordcloud.py
```

Word cloud of the `conflict-type-minor` labels, Kaiowá rows in Mato Grosso do
Sul. Labels split on `;` count separately, are accent-folded and lower-cased,
and whole phrases stay whole (the cloud is built from counts, never from raw
text). Writes `out/figures/cimi_kaiowa_conflict_types_wordcloud.*` and the label
counts `data/derived/cimi_kaiowa_conflict_type_counts.csv`.

```bash
./.cimi-venv/bin/python3 scripts/plot_funai_map.py
```

Map of the Kaiowá territories over the state boundary, focus territories in blue with
labels. Writes `out/figures/funai_kaiowa_ms_map.*`.

```bash
./.cimi-venv/bin/python3 scripts/plot_conflict_bubble_map.py
./.cimi-venv/bin/python3 scripts/plot_conflict_bubble_map.py --source mentions
```

Bubble map of the ten focus territories: the state boundary and the territory
polygons of the map above, carrying the counts of the heatmap (`--source cases`,
the default) or of the whole-report mention scan (`--source mentions`). Bubble
area is proportional to the count (radius grows with the square root), so a
territory with four times the count covers four times the ink. Each bubble sits
on the polygon's representative point, its count is printed beside it, and a
legend carries reference sizes. The main axes zoom to the southern cone where
every focus territory sits; a left panel carries the whole state with a box
around the zoom. Writes `out/figures/cimi_kaiowa_conflict_bubble_map.*` and
`out/figures/cimi_kaiowa_mentions_bubble_map.*`.

The two sources answer different questions and are never mixed. `cases` is the
Chapter I conflict table, one row per recorded conflict, 73 cases. `mentions` is
the whole-report scan, any place the territory is named in Chapters I-V plus
front matter, prose and tables included, 408 mentions. The mention map therefore
counts attention across the reports, not conflict.

Scope is the ten focus territories on purpose. Chapter I carries 209 Kaiowá-MS
cases (210 rows, because one printed record names two territories) under 41
territory labels; only 20 match a FUNAI territory name, and the rest are
acampamentos, municipalities and squatted-farm names, so a bubble per label
would put invented points on the map. The all-territory figure below plots the
20 and lists the other 21. The focus script asserts that every focus territory
has a polygon, and stops if a case turns up under a territory outside the focus
set.

```bash
./.cimi-venv/bin/python3 scripts/plot_conflict_bubble_map_all.py
```

The same figure for every row of the all-Kaiowá heatmap: 41 territory labels and
210 rows for 209 printed cases. Twenty labels match a FUNAI territory name and
get a numbered bubble, sized by the count; the right-hand key maps each number
to its label and count. The other 21 labels have no polygon to sit on, so they
are listed with their counts along the bottom instead of being dropped:
`DOURADOS AMAMBAIPEGUA II` (10 cases, an area CIMI names but FUNAI has not
delimited), `KURUSU AMBA` (8), acampamentos such as `NU VERA`, the municipality
rows and the `VARIAS` catch-all.

Two caveats the figure itself carries: the CIMI rows `DOURADOS`, `AMAMBAI` and
`CAARAPO` name the reserve or the municipality, so those three bubbles mean "in
or around" the named FUNAI polygon; and a label only places when the CIMI
spelling matches the FUNAI name after normalisation. Writes
`out/figures/cimi_kaiowa_conflict_bubble_map_all.*`.

```bash
./.cimi-venv/bin/python3 scripts/plot_mapbiomas_landcover.py --ti "ARROIO KORA"
```

Land cover inside one focus territory, 1985-2025, from MapBiomas Collection 11
(30 m annual) via Earth Engine, as a stacked-area chart in hectares. The 33
classes collapse into six groups (native vegetation, pasture, agriculture,
mosaic of uses, forest plantation, other non-vegetated) plus water and a
non-observed bucket. The title carries the current FUNAI stage and the
community's effective occupation from the CIMI shares, plus the territory area.
Each FUNAI legal act recorded in the focus inventory gets its own vertical
line, coloured by stage: delimitation (indigo), declaration (amber),
ratification (purple). Ratification is the closing act and draws solid; the two
earlier stages draw evenly dashed. A territory with no date for a stage gets no
line for it, and no stage text is written inside the plot; a second legend,
titled "Legal status", names the line colours. `--ti` takes any `TI_CLEAN` name
from `funai_focus_territories.geojson`; `--refresh` requeries GEE, otherwise the
run reuses the cache CSV `data/derived/mapbiomas_landcover_<ti>.csv`. Writes
`out/figures/<TI>/mapbiomas_landcover_1985_2025.*` (PNG at 300 dpi and SVG).

```bash
./.cimi-venv/bin/python3 scripts/plot_mapbiomas_grid.py
```

All ten focus territories on one figure: a 5x2 grid of the stacked-area land
cover charts, titled "LULC per delimited territory", built from the
per-territory cache CSVs (no Earth Engine call). Panels follow the
`focus_territories` order in `config/ti_names.yaml` and keep the per-territory
style of `plot_mapbiomas_landcover.py`, including the legal-act lines, each
panel title naming its current stage, and an x-axis (Year) and y-axis
(Hectares (ha)) on every panel. Two shared legends above the grid: "Legend" for
the land-cover classes, then "Legal status" for the line colours, separated by
a blank line. Run it after the ten `plot_mapbiomas_landcover.py` runs above.
Writes `out/figures/mapbiomas_landcover_grid_5x2.*` (PNG at 300 dpi and SVG).

```bash
./.cimi-venv/bin/python3 scripts/extract_territory_mentions.py
```

Scans every report cover to cover — Chapter I to V, plus the executive summary,
introduction and the articles — for the ten focus territories, which
`chapter1_txt_to_csv.py` does not do: that script only reads the Chapter I
tables and misses most of the focus-territory cases before 2019. Each mention
becomes one row with the report year, the chapter it sits in, the CIMI territory
label, CIMI's own case type (`dano`), one `conflict_class` from the nine-label
taxonomy, the description, and a `mention_kind`:

- `record` — a labeled case block (`TERRA INDÍGENA / TIPO DE DANO/CONFLITO /
  DESCRIÇÃO / FONTE`), how Chapters I to III file cases in every edition.
- `prose` — running text (executive summary, chapter analysis, articles) that
  names the territory; a sentence naming it plus one sentence of context.
- `table` — a status table (`Situação das Terras Indígenas com pendências
  administrativas`, the MapBiomas-style land-possession tables). Class is forced
  to `demarcacao_omissao_judicializacao`, rule `pending_table`.

Matching comes from the `mention_patterns` block in `config/ti_names.yaml`: the
name regex, the collisions to reject (Taquaritiua, Panambi (RS), Tekoha
Marangatu in Paraná, the Amambaipeguá II/III numerals, the bamboo sense of
*taquara*), and `requires_ms` for names that also exist outside Mato Grosso do
Sul. Chapters come from the running chapter headings, with the table-of-contents
cluster skipped, so a mention is filed under the chapter of the page it sits on;
front matter is `front`. Repeated descriptions collapse into one row and keep a
count in `repeats`. Writes `data/derived/cimi_mentions_focus_territories.csv`
(all ten) and `data/derived/cimi_mentions_<slug>.csv` (one file per territory).

```bash
./.cimi-venv/bin/python3 scripts/plot_territory_mention_timelines.py
```

One timeline per focus territory, from the mention log: nine conflict-class
lanes, one marker per mention (filled circle = case record, open square = prose,
grey tick = status table), marker colour = the chapter the mention sits in, the
FUNAI first legal act as a dashed line, and a lower strip counting mentions per
report year stacked by chapter. The reusable entry point is
`plot_territory_timeline(ti_clean, df, outdir)`, so a notebook can plot one
territory against any subset of the log. `--ti` restricts the run. Writes
`out/figures/<TI>/cimi_mention_timeline.*` (PNG at 300 dpi and SVG).

## Scripts and files

| Piece | What it is |
|---|---|
| `config/ti_names.yaml` | Territory-name data: focus territories, CIMI variants, FUNAI-to-CIMI mapping, open questions. The single source of truth. |
| `scripts/ti_names.py` | Loads the YAML and holds `norm_ti`, `cimi_ti`, `funai_ti`. Imported by every script that touches TI names. |
| `scripts/pdftext.py` | PDF reports to text. |
| `scripts/chapter1_txt_to_csv.py` | Chapter 1 tables to `data/derived/chapter1_conflicts.csv`. |
| `scripts/build_funai_inventory.py` | FUNAI inventory CSV and the Kaiowá GeoJSON, from the single FUNAI WFS download. |
| `scripts/prepare_kaiowa_dataset.py` | `TI_CLEAN` on both sides, side-by-side name check, focus-10 extracts. |
| `scripts/plot_conflict_heatmap.py` | Figure: cases per TI and year, all Kaiowá and focus territories. |
| `scripts/plot_occupation_lollipop.py` | Figure: occupied share per territory. Input CSV is hand-copied from the CIMI 2020 report. |
| `scripts/plot_conflict_wordcloud.py` | Figure + counts: conflict-type-minor labels. |
| `scripts/plot_funai_map.py` | Figure: territories over the state, focus territories highlighted. |
| `scripts/ms_map_base.py` | Shared map base for the three map figures: boundary, polygon layers, colours, label offsets, representative-point anchor. No figure of its own. |
| `scripts/plot_conflict_bubble_map.py` | Figure: bubble map per focus territory, from Chapter I cases (`--source cases`) or whole-report mentions (`--source mentions`). |
| `scripts/plot_conflict_bubble_map_all.py` | Figure: bubble map of all 41 heatmap labels, numbered and keyed, the 21 without a polygon listed below. |
| `scripts/plot_mapbiomas_landcover.py` | Figure + cache CSV: MapBiomas C11 land-cover share per group, 1985-2025, one territory per run. |
| `scripts/plot_mapbiomas_grid.py` | Figure: the ten MapBiomas land-cover charts as one 5x2 grid, from the cache CSVs. |
| `scripts/extract_territory_mentions.py` | Whole-report scan for the ten focus territories, every chapter: `data/derived/cimi_mentions_focus_territories.csv` plus one CSV per territory. |
| `scripts/plot_territory_mention_timelines.py` | Figure: CIMI mention timeline per territory, `plot_territory_timeline()` reusable from a notebook. |

### Figures

Every figure is a 300 dpi PNG plus an SVG of the same name. Change a figure by
changing its script and re-running it.

| File | Written by | What it shows |
|---|---|---|
| `out/figures/cimi_kaiowa_conflict_heatmap.*` | `plot_conflict_heatmap.py` | Cases per territory and year, all Kaiowá labels in MS, colour = most frequent conflict type |
| `out/figures/cimi_kaiowa_conflict_heatmap_focus_territories.*` | `plot_conflict_heatmap.py` | The same heatmap restricted to the ten focus territories |
| `out/figures/cimi_kaiowa_conflict_bubble_map.*` | `plot_conflict_bubble_map.py` | Bubble map of the ten focus territories, Chapter I cases |
| `out/figures/cimi_kaiowa_mentions_bubble_map.*` | `plot_conflict_bubble_map.py --source mentions` | Bubble map of the ten focus territories, mentions across every chapter |
| `out/figures/cimi_kaiowa_conflict_bubble_map_all.*` | `plot_conflict_bubble_map_all.py` | Bubble map of all 41 heatmap labels, numbered and keyed, unplaced labels listed |
| `out/figures/funai_kaiowa_ms_map.*` | `plot_funai_map.py` | FUNAI Kaiowá territories over the state boundary, focus territories in blue |
| `out/figures/cimi_kaiowa_conflict_types_wordcloud.*` | `plot_conflict_wordcloud.py` | Word cloud of the conflict-type-minor labels |
| `out/figures/cimi_kaiowa_occupation_share.*` | `plot_occupation_lollipop.py` | Share of each territory the community occupies, from the CIMI 2020 report |
| `out/figures/mapbiomas_landcover_grid_5x2.*` | `plot_mapbiomas_grid.py` | The ten land-cover charts as one 5x2 grid |
| `out/figures/<TI>/mapbiomas_landcover_1985_2025.*` | `plot_mapbiomas_landcover.py --ti "<TI>"` | Land cover inside one focus territory, 1985-2025 |
| `out/figures/<TI>/cimi_mention_timeline.*` | `plot_territory_mention_timelines.py` | CIMI mentions per class and year for one focus territory |

`<TI>` is the territory key with underscores, e.g. `PANAMBI_LAGOA_RICA`; the ten
folders are created by the per-territory scripts.

### Derived data

Every file under `data/derived/` has a producing script, except the one marked
hand-copied. The last column lists the scripts that read it, so a change to a
producer can be traced to the figures it invalidates.

| File | Written by | Read by |
|---|---|---|
| `chapter1_conflicts.csv` | `chapter1_txt_to_csv.py` | `prepare_kaiowa_dataset.py` |
| `cimi_kaiowa_ms_conflicts.csv` | `prepare_kaiowa_dataset.py` | `plot_conflict_heatmap.py`, `plot_conflict_wordcloud.py`, `plot_conflict_bubble_map_all.py` |
| `cimi_kaiowa_ms_conflicts_focus_territories.csv` | `prepare_kaiowa_dataset.py` | `plot_conflict_heatmap.py`, `plot_conflict_bubble_map.py` |
| `funai_territorial_inventory_ms.csv` | `build_funai_inventory.py` | `prepare_kaiowa_dataset.py` |
| `funai_kaiowa_ms_clipped.geojson` | `build_funai_inventory.py` | `prepare_kaiowa_dataset.py`, `ms_map_base.py` |
| `funai_ms_territories_clipped.geojson` | `build_funai_inventory.py` | `ms_map_base.py` (anchor layer for `plot_conflict_bubble_map_all.py`) |
| `funai_focus_territories_inventory.csv` | `prepare_kaiowa_dataset.py` | `plot_mapbiomas_grid.py`, `plot_territory_mention_timelines.py` |
| `funai_focus_territories.geojson` | `prepare_kaiowa_dataset.py` | `ms_map_base.py`, `plot_mapbiomas_landcover.py` |
| `cimi_mentions_focus_territories.csv` | `extract_territory_mentions.py` | `plot_territory_mention_timelines.py`, `plot_conflict_bubble_map.py --source mentions` |
| `cimi_mentions_<slug>.csv` | `extract_territory_mentions.py` | none, one file per territory for reading and sharing |
| `cimi_kaiowa_conflict_type_counts.csv` | `plot_conflict_wordcloud.py` | none, the counts behind the word cloud |
| `cimi_ms_occupation_shares.csv` | hand-copied from the CIMI 2020 report | `plot_occupation_lollipop.py`, `plot_mapbiomas_landcover.py`, `plot_territory_mention_timelines.py` |
| `mapbiomas_landcover_<ti>.csv` | `plot_mapbiomas_landcover.py` | `plot_mapbiomas_grid.py` |

Raw inputs, both under `data/raw/` and git-ignored: the FUNAI WFS download
`FUNAI_tis_portarias_poligonais_MS_2026-11-12.geojson` (read only by
`build_funai_inventory.py`) and the MS state boundary
`gaul_ms_boundary_2025.geojson` (used only as the map backdrop, loaded through
`ms_map_base.py` by the three map figures).


