# Raw inputs

Downloads as delivered. Nothing here is edited by hand, and the folder is
git-ignored: both files are reproducible from the sources below. Re-download
before re-running the pipeline on a fresh clone.

| File | Source | Date |
|---|---|---|
| `FUNAI_tis_portarias_poligonais_MS_2026-11-12.geojson` | FUNAI WFS layer `Funai:tis_poligonais_portarias` on `geoserver.funai.gov.br`, filtered to `uf_sigla = 'MS'`, retrieved 2026-11-12. One file carries the polygons and the legal-stage dates. The server rejects scripted and WSL clients (403, private government CA), so the export is a browser download from the WFS layer. | retrieved 2026-11-12 |
| `gaul_ms_boundary_2025.geojson` | FAO GAUL administrative boundary for Mato Grosso do Sul, 2025 edition. Used only as the map backdrop in `plot_funai_map.py`, `plot_conflict_bubble_map.py` and `plot_conflict_bubble_map_all.py`. | published 2025; retrieval date not recorded |

Read by `scripts/build_funai_inventory.py` (the FUNAI file) and
`scripts/ms_map_base.py` (the boundary, shared by the three map figures). No
other script opens this folder.

REMEMBER: every mention of this data in a document carries the dates above.
