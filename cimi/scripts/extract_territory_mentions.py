#!/usr/bin/env python3
"""Scan every CIMI report cover to cover for the ten focus territories.

chapter1_txt_to_csv.py extracts only the Chapter I tables. This script reads the
whole .txt report, every chapter, and logs every record or paragraph that names
one of the focus territories.

Two kinds of mention are captured:

    record    a labeled case block ("TERRA INDIGENA: ... TIPO DE DANO/CONFLITO:
              ... DESCRICAO: ..."), which is how Chapters I, II and III report
              cases in every edition from 2008 to 2025.
    prose     a run of body text (executive summary, chapter introduction,
              analysis) that names the territory outside any record block.

Each mention becomes one row, and every row carries its chapter (I-V, from the
running chapter headings), the CIMI territory label, the case type CIMI used,
a one-label `conflict_class` from the same nine-label taxonomy the Chapter I
classification uses, and the description.

Territory matching uses `mention_patterns` in config/ti_names.yaml: the regex
that finds the name, the collisions to reject (Taquaritiua, Panambi (RS),
Tekoha Marangatu in Parana, the Amambaipegua II/III numerals) and whether a
bare match needs a Mato Grosso do Sul cue. Chapter headings inside the table of
contents are ignored, so the chapter of a mention is the chapter of the page it
sits on.

Output
    data/derived/cimi_mentions_focus_territories.csv   all ten, one row per mention
    data/derived/cimi_mentions_<slug>.csv              one file per territory

Usage, from the project root:

    ./.cimi-venv/bin/python3 scripts/extract_territory_mentions.py
    ./.cimi-venv/bin/python3 scripts/extract_territory_mentions.py --max-lines 40
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ti_names import FOCUS_TERRITORIES, MENTION_PATTERNS, MS_CUES, ROOT  # noqa: E402

REPORT_DIR = ROOT / "docs" / "cimi-reports" / "txt"
DERIVED = ROOT / "data" / "derived"

COLUMNS = [
    "TI_CLEAN",
    "report_year",
    "data_year",
    "event_date",
    "chapter",
    "mention_kind",
    "cimi_ti_label",
    "povo",
    "dano",
    "conflict_class",
    "class_rule",
    "description",
    "source",
    "file",
    "match_note",
    "repeats",
]

# ---------------------------------------------------------------- text shaping

DASHES = str.maketrans({"\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'})


def fold(value: str) -> str:
    """Accent-fold and lower-case. Matching runs on this; output keeps the raw text."""
    s = unicodedata.normalize("NFKD", value.translate(DASHES)).encode("ascii", "ignore").decode()
    return s.lower()


def tidy(value: str) -> str:
    """Collapse the line wrapping a PDF leaves behind."""
    s = re.sub(r"[ \t]+", " ", value)
    s = re.sub(r"\s*\n\s*", " ", s)
    return s.strip()


# ------------------------------------------------------------------- page noise

FOOTER = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^relat[oó]rio\s*[-–]\s*viol[eê]ncia contra os povos ind[ií]genas no brasil",
        r"^conselho indigenista mission[aá]rio",
        r"^cimi\s*[-–]\s*conselho indigenista",
        r"^dados de \d{4}\s*$",
        r"^viol[eê]ncia contra os povos ind[ií]genas no brasil\s*$",
        r"^viol[eê]ncia contra o patrim[oô]nio\s*$",
        r"^foto\b",
        r"^(https?://|www\.)",
        r"^\|+$",
        r"^[.\-–—\s]+$",
        r"^\d{1,4}\s*$",
        r"^(?:[ivxlc]{1,6})\s*$",
        r"^p[aá]gina\s*\d+",
        r"^\d+\s*-\s+[a-zà-ú].{0,40}$",           # TOC entry with page number
    )
]

STATE_BLOCK = re.compile(r"^[A-Z]{2}\s*[-–]\s*\d+\s*Caso", re.IGNORECASE)
CASE_COUNT = re.compile(r"^\d+\s*Caso(?:s|\(s\))?$", re.IGNORECASE)
TOTAL_LINE = re.compile(r"^total de casos\s*:?\s*\d+", re.IGNORECASE)

# running headers only: a bare numeral, or the 2025 "CAPÍTULO I n Violência ..."
# shape. Entries carrying a dash and a title are table-of-contents lines, front
# or back matter, and never mark a chapter of the body.
CHAPTER_HEAD = re.compile(
    r"^(?:cap[ií]tulo)\s+([ivx]{1,4})(?:\s*$|\s+n\s+|\s*\|\s*)", re.IGNORECASE
)
SECTION_HEAD = re.compile(
    r"^(?:conflitos relativos a direitos territoriais"
    r"|invas[oõ]es possess[oó]rias"
    r"|omiss[aã]o e morosidade"
    r"|[a-zà-ú][a-zà-ú ,'\-/]{3,60})$"
)

ROMAN = {"i": "I", "ii": "II", "iii": "III", "iv": "IV", "v": "V"}


def is_noise(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if any(p.search(s) for p in FOOTER):
        return True
    if CASE_COUNT.match(s) or TOTAL_LINE.match(s) or STATE_BLOCK.match(s):
        return True
    return False


# ------------------------------------------------------------------- chapters


def annotate_chapters(lines: list[str]) -> list[str | None]:
    """Chapter per line, from the running chapter headings.

    Chapter tracking starts at the body, so the front matter (sumario,
    apresentacao, introducao, artigos) stays chapterless. A front cluster of
    three or more headings packed into a few hundred lines is the table of
    contents and is skipped; the body starts at the heading after it.
    """
    heads = [
        (i, m.group(1).lower())
        for i, line in enumerate(lines)
        if (m := CHAPTER_HEAD.match(line.strip()))
    ]
    body_start = 0
    k = 0
    while k < len(heads):
        group = [heads[k]]
        j = k + 1
        while j < len(heads) and heads[j][0] - group[-1][0] < 300:
            group.append(heads[j])
            j += 1
        if k == 0 and len(group) >= 3 and group[-1][0] - group[0][0] < 300:
            k = j
            continue
        body_start = group[0][0]
        break

    chapters: list[str | None] = [None] * len(lines)
    current: str | None = None
    for i, line in enumerate(lines):
        if i >= body_start:
            m = CHAPTER_HEAD.match(line.strip())
            if m:
                numeral = ROMAN.get(m.group(1).lower())
                if numeral and numeral != current:
                    current = numeral
        chapters[i] = current
    return chapters


# --------------------------------------------------------------- record fields

LABEL = re.compile(
    r"^\s*(terra ind[ií]gena|munic[ií]pio|local da ocorr[eê]ncia|povos?|tipo de dano(?:/conflito)?"
    r"|descri[cç][aã]o|meio empregado|v[ií]timas?|fonte|com informa[cç][oõ]es de)\s*:",
    re.IGNORECASE,
)

FIELD_ALIASES = {
    "terra indigena": "terra",
    "municipio": "municipio",
    "local da ocorrencia": "local",
    "povo": "povo",
    "povos": "povo",
    "tipo de dano": "dano",
    "tipo de dano/conflito": "dano",
    "descricao": "descricao",
    "meio empregado": "meio",
    "vitima": "vitima",
    "vitimas": "vitima",
    "fonte": "fonte",
    "com informacoes de": "fonte",
}

RECORD_START = re.compile(r"^\s*terra ind[ií]gena\s*:", re.IGNORECASE)
RECORD_END = re.compile(r"^\s*(fonte|com informa[cç][oõ]es de)\s*:", re.IGNORECASE)


def parse_records(lines: list[str], chapters: list[str | None], max_lines: int) -> list[dict]:
    """Labeled case blocks with the chapter each one sits in."""
    records: list[dict] = []
    i, n = 0, len(lines)
    while i < n:
        if not RECORD_START.match(lines[i]):
            i += 1
            continue
        start = i
        chapter = chapters[i]
        fields: dict[str, list[str]] = {}
        current: str | None = None
        content_lines = 0
        j = i
        while j < n and content_lines < max_lines:
            line = lines[j]
            if j > start and RECORD_START.match(line):
                break
            if j > start and chapters[j] and chapter and chapters[j] != chapter:
                break
            if is_noise(line):
                j += 1
                continue
            m = LABEL.match(line)
            if m:
                key = FIELD_ALIASES[fold(m.group(1)).strip()]
                current = key
                fields.setdefault(key, []).append(line[m.end():].strip())
            elif current:
                fields.setdefault(current, []).append(line.strip())
            content_lines += 1
            if RECORD_END.match(line):
                j += 1
                break
            j += 1
        records.append(
            {
                "start": start,
                "end": j,
                "chapter": chapter,
                "terra": tidy(" ".join(fields.get("terra", []))),
                "municipio": tidy(" ".join(fields.get("municipio", []))),
                "povo": tidy(" ".join(fields.get("povo", []))),
                "dano": tidy(" ".join(fields.get("dano", []))),
                "descricao": tidy(" ".join(fields.get("descricao", []))),
                "fonte": tidy(" ".join(fields.get("fonte", []))),
            }
        )
        i = j
    return records


# ------------------------------------------------------------ mention matching


def _numeral_ok(text: str, end: int) -> tuple[bool, str]:
    tail = text[end : end + 14]
    m = re.match(r"a?\s*(i{1,3}|iv)(?![\w])", tail)
    if not m:
        return True, "numeral_absent"
    numeral = m.group(1)
    if numeral in ("i",):
        return True, ""
    return False, ""


def find_territories(text: str) -> list[tuple[str, str]]:
    """(TI_CLEAN, note) for every focus territory named in a block of text."""
    folded = fold(text)
    if not folded.strip():
        return []
    ms = bool(re.search(MS_CUES, folded))
    hits: list[tuple[str, str]] = []
    for ti, spec in MENTION_PATTERNS.items():
        pattern = re.compile(spec["pattern"])
        reject = re.compile(spec["reject"]) if spec.get("reject") else None
        if spec.get("requires_ms") and not ms:
            continue
        note = ""
        for m in pattern.finditer(folded):
            s, e = m.span()
            window = folded[max(0, s - 140) : e + 140]
            if reject and reject.search(window):
                continue
            if spec.get("numerals"):
                ok, extra = _numeral_ok(folded, e)
                if not ok:
                    continue
                note = extra
            hits.append((ti, note))
            break
    return hits


# ---------------------------------------------------------------- classification

# Ordered tiers: first tier that fires wins. The CIMI case type (`dano`) is
# tried first, the description only when the type says nothing. Sector labels
# come before violence so that a record CIMI files under agrotoxin, cattle or
# soy keeps that label, which is the one comparable with land cover.
TIERS: list[tuple[str, str, str]] = [
    (
        "agropecuaria_monocultivo_agrotoxico",
        r"agrot[oó]xic|veneno|pulveriza|herbicida|defensivo agr[ií]cola|monocultur|soja|sojicultur"
        r"|cana[- ]de[- ]a[cç][uú]car|eucalipt|silvicultur|arrendament|lavoura|plantio|pecu[aá]ria"
        r"|rebanho|gado\b|pastagem|trator|agroneg[oó]cio",
        "agro",
    ),
    (
        "grilagem_posse_especulacao",
        r"grilagem|posseir|invas[aã]o|invasor|retirada de cerca|matr[ií]cula|especula[cç][aã]o"
        r"|t[ií]tulo de propriedade|ocupa[cç][aã]o irregular",
        "land_grabbing",
    ),
    (
        "violencia_ameacas_danos",
        r"pistoleir|jagun[cç]|atir|tiro|arma de fogo|disparo|bala de borracha|bomba de g[aá]s"
        r"|assassin|homic[ií]dio|massacre|espancament|agress[aã]o|amea[cç]a|sequestr|cerco armado"
        r"|tortura|les[aã]o corporal|intimida[cç][aã]o|ataque",
        "violence",
    ),
    (
        "demarcacao_omissao_judicializacao",
        r"demarca|morosidade|regulariza[cç][aã]o|rein?tegra[cç][aã]o de posse|despejo|liminar"
        r"|\bstf\b|judicial|portaria|homologa|indeniza|termo de ajustamento|\btac\b|processo"
        r"|senten[cç]a|a[cç][aã]o possess[oó]ria",
        "demarcation",
    ),
    ("garimpo_mineracao", r"garimp|mineradora|minera[cç][aã]o|lavra|dragagem", "mining"),
    (
        "exploracao_ilegal_recursos",
        r"extra[cç][aã]o ilegal|madeira|madeireir|lenha|carv[aã]o|pesca|ca[cç]a\b|palmito|areia"
        r"|recursos naturais",
        "resources",
    ),
    (
        "grandes_empreendimentos_infraestrutura",
        r"hidrel[eé]tric|barragem|usina|rodovia|ferrovia|linha de transmiss[aã]o|porto\b|mineroduto"
        r"|empreendimento|obra de infraestrutura",
        "infrastructure",
    ),
    (
        "desmatamento_incendios_queimadas",
        r"desmatament|queimad|inc[eê]ndio|fogo\b|derrubada|supress[aã]o de vegeta[cç][aã]o",
        "fire_deforestation",
    ),
]

CLASS_ORDER = [
    "demarcacao_omissao_judicializacao",
    "grilagem_posse_especulacao",
    "agropecuaria_monocultivo_agrotoxico",
    "desmatamento_incendios_queimadas",
    "exploracao_ilegal_recursos",
    "garimpo_mineracao",
    "grandes_empreendimentos_infraestrutura",
    "violencia_ameacas_danos",
    "outros",
]


GRAVE = (
    r"assassin|homic[ií]dio|morte|morto|mataram|balead|ferid|golpes|faca\b|pistoleir|jagun[cç]"
    r"|tiro|arma de fogo|disparo|atacad|ataque|agress|amea[cç]a|tortura|sequestr|massacre"
    r"|espancament|capanga|milician|inc[eê]ndio criminoso|queimaram|cerco armado"
)


def classify(dano: str, descricao: str, chapter: str = "") -> tuple[str, str]:
    """One label per case: CIMI's own case type first, then the description.

    Editions up to 2011 carry no case-type field, so the description decides.
    There the lethal-violence wording is checked before any sector, or a murder
    reported next to a cane field would be filed as agriculture. Chapter III
    (omission of the public power: health, education, suicide) skips that
    shortcut: those records describe missing services, not an attack.
    """
    for source in (dano, descricao):
        text = fold(source or "")
        if not text.strip():
            continue
        if source is dano:
            for label, pattern, rule in TIERS:
                if re.search(pattern, text):
                    return label, rule
            continue
        if chapter != "III" and re.search(GRAVE, text):
            return "violencia_ameacas_danos", "violence"
        for label, pattern, rule in TIERS:
            if re.search(pattern, text):
                return label, rule
    return "outros", "none"


# ------------------------------------------------------------------ date in text

MONTHS = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
RE_DATE_LONG = re.compile(r"\b(\d{1,2})\s+de\s+(" + "|".join(MONTHS) + r")(?:\s+de\s+(\d{4}))?")
RE_DATE_SHORT = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")


def extract_date(descricao: str, report_year: int) -> str:
    folded = fold(descricao)
    m = RE_DATE_LONG.search(folded)
    if m:
        day, month, year = int(m.group(1)), MONTHS[m.group(2)], m.group(3)
        year = int(year) if year else report_year
        if 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"
    m = RE_DATE_SHORT.search(folded)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), m.group(3)
        year = int(year) if year else report_year
        if year < 100:
            year += 2000
        if 1 <= day <= 31 and 1 <= month <= 12:
            return f"{year:04d}-{month:02d}-{day:02d}"
    return f"{report_year:04d}"


# ------------------------------------------------------------------- per report


def report_year(path: Path) -> int:
    years = re.findall(r"(?:19|20)\d{2}", path.stem)
    if not years:
        raise ValueError(f"{path}: no year in the filename")
    return int(years[-1])


FUNCTION_WORDS = re.compile(
    r"\b(de|da|do|das|dos|que|em|no|na|nas|com|para|por|foi|nao|seu|sua|pelo|pela|entre|sobre)\b",
    re.IGNORECASE,
)
SENTENCE_BREAK = re.compile(r"(?<=[.!?\u2026])\s+(?=[A-ZÀ-Ú\"“'(\[])")

# Status tables ("Situacao das Terras Indigenas com pendencias administrativas"):
# long name lists with a state abbreviation per line. They are not prose, and
# their only pressure signal is the table's own subject: administrative pending.
RE_UF = re.compile(
    r"\b(?:AC|AL|AM|AP|BA|CE|DF|ES|GO|MA|MG|MS|MT|PA|PB|PE|PI|PR|RJ|RN|RO|RR|RS|SC|SE|SP|TO)\b"
)
RE_TABLE_HEAD = re.compile(
    r"situa[cç][aã]o\s+(?:terra|das terras)|sem provid[eê]ncias|a identificar"
    r"|area ocupada|posse das terras|superficie \(hectares\)"
    r"|listagem geral|terras indigenas sem providencia"
)


def is_table(text: str) -> bool:
    folded = fold(text)
    if RE_TABLE_HEAD.search(folded) or len(RE_UF.findall(folded)) >= 6:
        return True
    # name + povo + municipality + hectares + percentage, with no sentence around it
    numbers = re.findall(r"\d[\d.,]*", folded)
    words = re.findall(r"\w+", folded)
    return len(numbers) >= 10 and len(numbers) / max(1, len(words)) >= 0.15


def sentences(text: str) -> list[str]:
    parts = [s.strip() for s in SENTENCE_BREAK.split(text)]
    return [s for s in parts if s]


def prose_blocks(lines: list[str], chapters: list[str | None], consumed: list[bool]) -> list[dict]:
    """Body text and status tables outside record blocks, one block per mention.

    Text extracted from a PDF has no blank lines, so a run of content lines
    between two page footers is the closest thing to a paragraph boundary. Each
    run is split into sentences, then into consecutive runs of the same kind:
    prose, or table. A prose run that names a focus territory is kept with one
    sentence of context on each side, so the block reads as a case and not as a
    page. A table run is kept whole. Runs with no function words are dropped:
    they list territory names without saying anything about them.
    """
    blocks: list[dict] = []
    run_start: int | None = None

    def flush(end: int) -> None:
        nonlocal run_start
        if run_start is None or end < run_start:
            run_start = None
            return
        text = tidy(" ".join(lines[run_start : end + 1]))
        start, run_start = run_start, None
        if len(text) < 80 or len(re.findall(r"\w+", text)) < 12:
            return
        if len(FUNCTION_WORDS.findall(fold(text))) < 2:
            return
        parts = sentences(text)
        kinds = ["table" if is_table(part) else "prose" for part in parts]

        def emit(kind: str, lo: int, hi: int) -> None:
            chunk = tidy(" ".join(parts[lo : hi + 1]))
            # a leading fragment ("e passou a morar ...") is the tail of a
            # sentence cut by a page footer, not the start of a case
            if len(chunk) > 1 and chunk[0].islower():
                head, _, rest = chunk.partition(" ")
                chunk = rest if re.search(r"[.!?…]", head) else chunk
            if not chunk or not find_territories(chunk):
                return
            blocks.append(
                {
                    "start": start,
                    "end": end,
                    "chapter": chapters[start],
                    "kind": kind,
                    "text": chunk,
                }
            )

        i = 0
        while i < len(parts):
            j = i
            while j + 1 < len(parts) and kinds[j + 1] == kinds[i]:
                j += 1
            if kinds[i] == "table":
                emit("table", i, j)
            else:
                # one block per case: a sentence naming the territory plus one
                # sentence of context, merged when two cases sit side by side
                flagged = [k for k in range(i, j + 1) if find_territories(parts[k])]
                group: list[int] = []
                for k in flagged:
                    if group and k <= group[-1] + 2:
                        group.append(k)
                        continue
                    if group:
                        emit("prose", max(i, group[0] - 1), min(j, group[-1] + 1))
                    group = [k]
                if group:
                    emit("prose", max(i, group[0] - 1), min(j, group[-1] + 1))
            i = j + 1

    for i, line in enumerate(lines):
        if consumed[i] or is_noise(line):
            flush(i - 1)
            continue
        if run_start is None:
            run_start = i
        elif chapters[i] != chapters[i - 1]:
            flush(i - 1)
            run_start = i
    flush(len(lines) - 1)
    return blocks


def scan(path: Path, max_lines: int) -> list[dict]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    chapters = annotate_chapters(lines)
    year = report_year(path)
    rows: list[dict] = []

    records = parse_records(lines, chapters, max_lines)
    consumed = [False] * len(lines)
    for rec in records:
        for k in range(rec["start"], rec["end"]):
            consumed[k] = True

    for rec in records:
        hits = find_territories(rec["terra"])
        if not hits and rec["descricao"]:
            hits = [(ti, "mentioned_in_description") for ti, _ in find_territories(rec["descricao"])]
        for ti, note in hits:
            label, rule = classify(rec["dano"], rec["descricao"], rec["chapter"] or "")
            rows.append(
                {
                    "TI_CLEAN": ti,
                    "report_year": year,
                    "data_year": year,
                    "event_date": extract_date(rec["descricao"], year),
                    "chapter": rec["chapter"] or "front",
                    "mention_kind": "record",
                    "cimi_ti_label": rec["terra"],
                    "povo": rec["povo"],
                    "dano": rec["dano"],
                    "conflict_class": label,
                    "class_rule": rule,
                    "description": rec["descricao"][:1400],
                    "source": rec["fonte"],
                    "file": path.name,
                    "match_note": note,
                    "repeats": 1,
                }
            )

    for block in prose_blocks(lines, chapters, consumed):
        table = block["kind"] == "table"
        for ti, note in find_territories(block["text"]):
            if table:
                label, rule = "demarcacao_omissao_judicializacao", "pending_table"
            else:
                label, rule = classify("", block["text"], block["chapter"] or "")
            rows.append(
                {
                    "TI_CLEAN": ti,
                    "report_year": year,
                    "data_year": year,
                    "event_date": extract_date(block["text"], year),
                    "chapter": block["chapter"] or "front",
                    "mention_kind": "table" if table else "prose",
                    "cimi_ti_label": "",
                    "povo": "",
                    "dano": "",
                    "conflict_class": label,
                    "class_rule": rule,
                    "description": block["text"][:1400],
                    "source": "",
                    "file": path.name,
                    "match_note": note,
                    "repeats": 1,
                }
            )

    rows.sort(key=lambda r: (r["TI_CLEAN"], r["data_year"], r["chapter"], r["mention_kind"]))
    return rows


def slug(ti: str) -> str:
    s = fold(ti).replace("(", "").replace(")", "").replace(" ", "_").replace("-", "_")
    return re.sub(r"_+", "_", s).strip("_")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("reports", nargs="*", type=Path, default=None,
                    help="txt reports or directories (default: docs/cimi-reports/txt)")
    ap.add_argument("-o", "--out-dir", type=Path, default=DERIVED)
    ap.add_argument("--max-lines", type=int, default=45,
                    help="content lines a single case block may span (default 45)")
    args = ap.parse_args()

    paths: list[Path] = []
    for item in args.reports or [REPORT_DIR]:
        paths.extend(sorted(item.glob("*.txt")) if item.is_dir() else [item])
    if not paths:
        print("no reports found", file=sys.stderr)
        return 1

    rows: list[dict] = []
    for path in paths:
        found = scan(path, args.max_lines)
        rows.extend(found)
        per_ti = {ti: sum(1 for r in found if r["TI_CLEAN"] == ti) for ti in
                  {r["TI_CLEAN"] for r in found}}
        print(f"{path.name:<58}{len(found):>5}  " +
              " ".join(f"{k}={v}" for k, v in sorted(per_ti.items())), file=sys.stderr)

    # The same case is repeated across pages in some editions (a record that
    # continues on the next page, or one case filed once per tekoha). Collapse
    # identical descriptions into one row and keep the count in `repeats`.
    seen: dict[tuple, dict] = {}
    deduped: list[dict] = []
    for row in rows:
        key = (
            row["TI_CLEAN"],
            row["report_year"],
            row["chapter"],
            re.sub(r"[^a-z0-9]", "", fold(row["description"]))[:150],
        )
        if key in seen:
            seen[key]["repeats"] += 1
            continue
        seen[key] = row
        deduped.append(row)
    print(f"deduplicated {len(rows) - len(deduped)} repeated rows", file=sys.stderr)
    rows = [row for row in deduped if row["description"].strip()]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    combined = args.out_dir / "cimi_mentions_focus_territories.csv"
    with combined.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    for ti in FOCUS_TERRITORIES:
        subset = [r for r in rows if r["TI_CLEAN"] == ti]
        out = args.out_dir / f"cimi_mentions_{slug(ti)}.csv"
        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(subset)
        print(f"{ti:<26}{len(subset):>5} rows  -> {out.name}", file=sys.stderr)

    print(f"total {len(rows)} rows -> {combined}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
