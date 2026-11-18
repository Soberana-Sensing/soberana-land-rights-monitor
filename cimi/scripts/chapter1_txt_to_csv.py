#!/usr/bin/env python3
"""Extract Chapter I ("Violencia Contra o Patrimonio") case tables from Cimi .txt into one CSV.

Input : any mix of directories and .txt files produced by pdftext.py.
        Directories are scanned for *.txt (recursive with --recursive).
Output: one CSV, one row per case, columns

    year,conflict-type-major,conflict-type-minor,state,TI,povo,description,source

Chapter I holds three major conflict types, in this order per report:

    conflitos relativos a direitos territoriais
    invasoes possessorias, exploracao ilegal de recursos naturais e danos diversos ao patrimonio
    omissao e morosidade na regularizacao de terras

Each one opens with its title, usually "Dados - YYYY" and "Total de casos: N"
(2008) or a bare "N Casos" line (2019+), then one block per state, alphabetical,
each block holding label-prefixed records:

    TERRA INDIGENA: ...   POVO(S): ...   TIPO DE DANO/CONFLITO: ...
    DESCRICAO: ...        FONTE: ... or Com informacoes de: ...

Records outside those three sections are dropped, so chapter II and III are
ignored even when their records also carry a TERRA INDIGENA label: those blocks
carry VITIMA and no TIPO DE * label.

Per file the script cross-checks the parsed case count against the printed
section total and reports every mismatch. --strict turns warnings into errors.

Usage, from the project root:

    ./.cimi-venv/bin/python3 scripts/chapter1_txt_to_csv.py docs/cimi-reports/txt
    ./.cimi-venv/bin/python3 scripts/chapter1_txt_to_csv.py docs/cimi-reports/txt/*.txt -o out.csv
"""

import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

COLUMNS = [
    "year",
    "conflict-type-major",
    "conflict-type-minor",
    "state",
    "TI",
    "povo",
    "description",
    "source",
]

# canonical chapter I section labels, in the order they appear in the reports
SECTIONS = {
    "territorial": "conflitos relativos a direitos territoriais",
    "invasao": (
        "invasões possessórias, exploração ilegal de recursos naturais "
        "e danos diversos ao patrimônio"
    ),
    "omissao": "omissão e morosidade na regularização de terras",
}

STATE_MAP = {
    "acre": "AC",
    "alagoas": "AL",
    "amapa": "AP",
    "amazonas": "AM",
    "bahia": "BA",
    "ceara": "CE",
    "distrito federal": "DF",
    "espirito santo": "ES",
    "goias": "GO",
    "maranhao": "MA",
    "mato grosso": "MT",
    "mato grosso do sul": "MS",
    "minas gerais": "MG",
    "para": "PA",
    "paraiba": "PB",
    "parana": "PR",
    "pernambuco": "PE",
    "piaui": "PI",
    "rio de janeiro": "RJ",
    "rio grande do norte": "RN",
    "rio grande do sul": "RS",
    "rondonia": "RO",
    "roraima": "RR",
    "santa catarina": "SC",
    "sao paulo": "SP",
    "sergipe": "SE",
    "tocantins": "TO",
}
STATE_UFS = {uf.lower(): uf for uf in STATE_MAP.values()}

# State header, every shape the reports use:
#   "BA - 2 Caso(s)"            classic, dash
#   "MS – 2 casos"              lower-case count (2009)
#   "MS\t 1 Caso"               tab instead of dash (2013, 2014)
#   "MATO GROSSO DO SUL  –  9 CASOS"   upper-case count, double spaces (2021)
#   "MATO GROSSO DO SUL (148)"         count in parentheses (2022+)
#   "MATO GROSSO DO SUL (148) - Continuação"   continuation page (2022+)
RE_STATE_HEADER_DASH = re.compile(
    r"^(?P<name>[A-Za-zÀ-Úà-ú][A-Za-zÀ-Úà-ú .]{1,34}?)\s*[–—-]\s*(?P<n>\d{1,4})"
    r"\s*(?:[Cc][Aa][Ss][Oo][Ss]?(?:\(s\))?)?(?:\s*[–—-]\s*(?P<tail>.*))?$"
)
RE_STATE_HEADER_PAREN = re.compile(
    r"^(?P<name>[A-Za-zÀ-Úà-ú][A-Za-zÀ-Úà-ú .]{1,34}?)\s*\(\s*(?P<n>\d{1,4})\s*\)"
    r"(?:\s*[–—-]\s*(?P<tail>.*))?$"
)
# tab or plain spaces are only a state header when the count carries the word
# "Caso(s)"; a bare "MS 4" is a table cell, not a header.
RE_STATE_HEADER_CASO = re.compile(
    r"^(?P<name>[A-Za-zÀ-Úà-ú][A-Za-zÀ-Úà-ú .]{1,34}?)\s+\t?\s*(?P<n>\d{1,4})"
    r"\s*[Cc][Aa][Ss][Oo][Ss]?(?:\(s\))?\b(?:\s*[–—-]\s*(?P<tail>.*))?$"
)
# what may follow the count on a state header: victim counts and page markers
RE_STATE_TAIL = re.compile(r"vitima|indigena|comunidade|continua|caso")
RE_COUNT = re.compile(r"^(?P<n>\d+)\s*Caso(?:s)?(?:\(s\))?$", re.IGNORECASE)
# A section total closes a section title block: capital "Casos", nothing else
# after it. The case-insensitive form above also matches a table cell ("1 caso"
# in the pending-status tables), and treating that as a section total would end
# the section and silently drop every record that follows.
RE_SECTION_COUNT = re.compile(r"^(?P<n>\d+)\s*Casos?$")
# "Total de casos: 16"
RE_TOTAL = re.compile(r"^Total de casos\s*:?\s*(?P<n>\d+)\s*$", re.IGNORECASE)
# "TERRA INDIGENA: X"
RE_LABEL = re.compile(r"^([A-ZÀ-Ú][A-ZÀ-Ú0-9 ()/ºª.\-]{0,40}):\s*(.*)$")
# "Com informacoes de: ..." is the only lowercase source label
RE_SOURCE_PROSE = re.compile(r"^Com informa[çc][õo]es de\s*:\s*(.*)$", re.IGNORECASE)

NOISE = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^Conselho Indigenista Mission[áa]rio",
        r"^Cimi\s*[–-]\s*Conselho Indigenista",
        r"^RELAT[ÓO]RIO\s*[–-]\s*Viol[êe]ncia Contra os Povos",
        r"^Viol[êe]ncia [Cc]ontra os [Pp]ovos Ind[íi]genas no Brasil",
        r"^Viol[êe]ncia Contra o Patrim[ôo]nio",
        r"^Cap[íi]tulo\s+[IVX]+\s*$",
        r"^Foto\b",
        r"^(https?://|www\.)",
        r"^\|+$",
        r"^\d{1,4}$",
        r"^P[áa]gina\s+\d+",
        r"^Dados\s*[-–—]\s*\d{4}\s*$",
    )
]


def fold(text):
    """Accent- and case-insensitive key."""
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", stripped).casefold().strip()


def squash(text):
    return re.sub(r"\s+", " ", text).strip()


def join_value(prev, nxt):
    """Append a wrapped line, undoing soft hyphenation."""
    if not prev:
        return nxt
    if prev.endswith("/"):
        return prev + nxt
    if prev.endswith("-") and nxt[:1].islower():
        return prev[:-1] + nxt
    return prev + " " + nxt


def classify_label(label):
    key = fold(label)
    if key.startswith("terra"):
        return "TI"
    if key.startswith("povo"):
        return "povo"
    if key.startswith("tipo de"):
        return "tipo"
    if key.startswith("descr"):
        return "desc"
    if key.startswith("fonte"):
        return "source"
    if key.startswith("vitima"):
        return "victim"
    return "other"


# Section banners are wrapped over two or three lines from 2021 on, and the first
# fragment is the only part that reliably appears on one line, so a line counts
# when it is a prefix of the banner or the banner plus its tail.
BANNER = {
    "territorial": "conflitos relativos a direitos territoriais",
    "invasao": (
        "invasoes possessorias, exploracao ilegal de recursos naturais "
        "e danos diversos ao patrimonio"
    ),
    "omissao": "omissao e morosidade na regularizacao de terras",
}
# a banner line may also carry the printed page number, tab-separated or not
RE_BANNER_TAIL = re.compile(r"[\s.]+\d{1,4}$")


def match_section(line):
    """Chapter I section key for a title-ish line, else None.

    Only a standalone heading counts, and the seed words must be followed by
    nothing or by the rest of the printed banner. Two failure modes this rules
    out: CIMI's case-type labels repeat the same phrases ("Omissão e morosidade
    na demarcação da TI", "Invasões possessórias, exploração ilegal de
    recursos") and would flip the section mid-record, and lower-case running
    text can start with the same words.
    """
    if len(line) > 150 or ":" in line or re.search(r"\.{3,}", line):
        return None
    stripped = line.strip()
    if not stripped or not stripped[0].isupper():
        return None
    key = re.sub(r"\s+", " ", fold(stripped))
    key = RE_BANNER_TAIL.sub("", key).strip(" ,;")
    if len(key) < 12:
        return None
    for section, banner in BANNER.items():
        if banner.startswith(key) or key.startswith(banner):
            return section
    return None


def match_chapter_end(line):
    """True when the line opens a chapter after chapter I.

    Chapter I only holds its three conflict types. Chapters II-IV repeat the
    same TERRA INDIGENA / TIPO DE DANO labels with a different subject, so a
    stale section key would file them under whichever chapter I section was last
    seen. Their opening lines are "Capítulo II", "capitulo II",
    "CAPÍTULO II    n    Violência Contra a Pessoa" and the same for III and IV.
    """
    if len(line) > 150 or re.search(r"\.{3,}", line):
        return False
    key = re.sub(r"\s+", " ", fold(line)).strip()
    return bool(re.match(r"capitulo (ii|iii|iv)\b", key))


def is_state_name(line):
    key = fold(line)
    return STATE_MAP.get(key) or STATE_UFS.get(key)


def parse_state_header(line):
    """(uf, printed_count) when the line is a state header, else None.

    The reports changed the shape of this header four times between 2008 and
    2025: "BA - 2 Casos", "MS\t 1 Caso", "MATO GROSSO DO SUL  -  9 CASOS",
    "MATO GROSSO DO SUL (148)". The name is validated against the state table,
    and a plain whitespace + number is accepted only with the word "Caso(s)",
    so a table cell like "MS 4" is not read as a header.
    """
    for pattern in (RE_STATE_HEADER_DASH, RE_STATE_HEADER_PAREN, RE_STATE_HEADER_CASO):
        m = pattern.match(line.strip())
        if not m:
            continue
        uf = is_state_name(m.group("name").strip())
        if not uf:
            continue
        tail = fold(m.group("tail") or "").strip()
        if tail and not RE_STATE_TAIL.search(tail):
            continue
        return uf, int(m.group("n"))
    return None


def is_noise(line):
    return any(rx.search(line) for rx in NOISE)


def next_content(lines, start):
    """Index of the next non-blank line at or after start, else None."""
    for idx in range(start, len(lines)):
        if lines[idx].strip():
            return idx
    return None


def prev_content(lines, start):
    for idx in range(start, -1, -1):
        if lines[idx].strip():
            return idx
    return None


def looks_like_title(line):
    if not line or len(line) > 110 or ":" in line:
        return False
    if re.search(r"\.{3,}", line) or line.endswith("."):
        return False
    return bool(re.search(r"[A-Za-zÀ-Ú]", line))


def section_from_lookback(lines, end_idx, window=4):
    """Section key if a chapter I title opens the block ending at end_idx."""
    idx = end_idx
    for _ in range(window):
        if idx is None or idx < 0:
            break
        key = match_section(lines[idx].strip())
        if key:
            return key
        idx = prev_content(lines, idx - 1)
    return None


def detect_year(path, lines):
    found = re.search(r"(19|20)\d{2}", path.stem)
    if found:
        return int(found.group(0))
    joined = "\n".join(lines[:4000])
    for pattern in (
        r"Dados\s*[-–—]\s*(\d{4})",
        r"Ano de (\d{4})",
        r"Dados de (\d{4})",
    ):
        found = re.search(pattern, joined, re.IGNORECASE)
        if found:
            return int(found.group(1))
    return None


def new_record(year, section, state):
    return {
        "year": year,
        "section": section,
        "state": state,
        "TI": "",
        "povo": "",
        "tipo": "",
        "desc": "",
        "source": "",
        "victim": False,
    }


def parse_file(path, stats):
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    year = detect_year(path, lines)
    if year is None:
        raise ValueError(f"{path}: cannot determine year from filename or header")

    rows = []
    section = None
    state = None
    section_totals = {}
    state_totals = {}
    parsed = {key: 0 for key in SECTIONS}
    sections_seen = set()
    dropped = 0
    skipped = []

    rec = None
    field = None

    def flush():
        nonlocal rec, field
        if rec is None:
            return
        if rec["section"] in SECTIONS:
            parsed[rec["section"]] += 1
            if not rec["victim"] and rec["TI"] and rec["tipo"]:
                rows.append(
                    {
                        "year": rec["year"],
                        "conflict-type-major": SECTIONS[rec["section"]],
                        "conflict-type-minor": squash(rec["tipo"]).rstrip("."),
                        "state": rec["state"] or "",
                        "TI": squash(rec["TI"]),
                        "povo": squash(rec["povo"]),
                        "description": squash(rec["desc"]),
                        "source": squash(rec["source"]),
                    }
                )
            else:
                reason = "victima" if rec["victim"] else "no TI/TIPO label"
                skipped.append((rec["section"], reason, squash(rec["TI"])[:40]))
        rec = None
        field = None

    i = 0
    total_lines = len(lines)
    while i < total_lines:
        line = lines[i].strip()
        here = i
        i += 1
        if not line:
            continue

        # photo captions leak into descriptions; drop the line above "Foto: ..."
        # (but never a section banner or a chapter heading, which can sit right
        # above a full-page photo)
        nxt = next_content(lines, here + 1)
        if (
            nxt is not None
            and fold(lines[nxt]).startswith("foto")
            and not match_section(line)
            and not match_chapter_end(line)
        ):
            dropped += 1
            continue

        # chapter II or later: chapter I is over, do not file its records
        if match_chapter_end(line):
            flush()
            section = None
            state = None
            field = None
            continue

        if is_noise(line):
            dropped += 1
            continue

        # section total, e.g. "Total de casos: 16"
        total = RE_TOTAL.match(line)
        if total:
            if section:
                section_totals.setdefault(section, int(total.group("n")))
                sections_seen.add(section)
            field = None
            continue

        # section title, including the running header repeated on every page
        sec = match_section(line)
        if sec:
            if sec == section:
                field = None
                continue
            flush()
            section = sec
            state = None
            sections_seen.add(sec)
            field = None
            continue

        # state header with inline count, any of the report-era shapes
        header = parse_state_header(line)
        if header:
            uf, printed = header
            flush()
            state = uf
            state_totals[uf] = state_totals.get(uf, 0) + printed
            continue

        # state header, bare name followed by a count line: "ACRE" / "1 Caso"
        uf = is_state_name(line) if len(line) <= 30 else None
        if uf:
            nxt = next_content(lines, here + 1)
            if nxt is not None and RE_COUNT.match(lines[nxt].strip()):
                flush()
                state = uf
                state_totals[uf] = state_totals.get(uf, 0) + int(
                    RE_COUNT.match(lines[nxt].strip()).group("n")
                )
                i = nxt + 1
                continue

        # bare section total: "158 Casos" closing a section title block
        count = RE_SECTION_COUNT.match(line)
        if count:
            anchor = prev_content(lines, here - 1)
            if anchor is not None:
                raw_anchor = lines[anchor].strip()
                key = section_from_lookback(lines, anchor)
                if key:
                    section = key
                    section_totals.setdefault(key, int(count.group("n")))
                    sections_seen.add(key)
                elif not (
                    is_state_name(raw_anchor) or parse_state_header(raw_anchor)
                ) and looks_like_title(raw_anchor):
                    # a title that is not one of the three chapter I ones:
                    # chapter II or III begins here
                    flush()
                    section = None
                    state = None
                field = None
                continue

        probe = line
        label = RE_LABEL.match(probe)
        prose_source = RE_SOURCE_PROSE.match(probe)
        if prose_source:
            if rec is not None:
                rec["source"] = join_value(rec["source"], prose_source.group(1).strip())
                field = "source"
            continue
        if label:
            kind = classify_label(label.group(1))
            value = label.group(2).strip()
            if kind == "TI":
                flush()
                rec = new_record(year, section, state)
                rec["TI"] = value
                field = "TI"
                continue
            if rec is None:
                field = None
                continue
            if kind == "victim":
                rec["victim"] = True
                field = None
            elif kind in ("povo", "tipo", "source", "desc"):
                rec[kind] = join_value(rec[kind], value)
                field = kind
            else:
                field = None
            continue

        # continuation of the field above
        if rec is not None and field in ("TI", "povo", "tipo", "source", "desc"):
            rec[field] = join_value(rec[field], line)

    flush()

    stats.append(
        {
            "path": path,
            "year": year,
            "rows": len(rows),
            "parsed": parsed,
            "totals": section_totals,
            "state_totals": state_totals,
            "state_rows": {
                uf: sum(1 for row in rows if row["state"] == uf)
                for uf in {row["state"] for row in rows if row["state"]}
            },
            "sections": sections_seen,
            "dropped": dropped,
            "skipped": skipped,
        }
    )
    return rows, parsed, section_totals, sections_seen


def collect_inputs(paths, recursive):
    files = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            pattern = "**/*.txt" if recursive else "*.txt"
            found = sorted(path.glob(pattern))
            if not found:
                print(f"warning: no .txt found in {path}", file=sys.stderr)
            files.extend(found)
        elif path.is_file():
            files.append(path)
        else:
            raise SystemExit(f"error: no such file or directory: {path}")
    seen = set()
    unique = []
    for path in files:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique


def report(stats, strict):
    problems = []
    print(f"{'year':<6}{'file':<52}{'rows':>6}   sections", file=sys.stderr)
    for item in stats:
        name = item["path"].name
        marks = []
        for key in ("territorial", "invasao", "omissao"):
            got = item["parsed"].get(key, 0)
            want = item["totals"].get(key)
            if want is None:
                marks.append(f"{key[:5]} {got}/?")
            elif want != got:
                marks.append(f"{key[:5]} {got}/{want} MISMATCH")
                problems.append(
                    f"{name}: {SECTIONS[key]} parsed {got}, report says {want}"
                )
            else:
                marks.append(f"{key[:5]} {got}")
        missing = [
            key for key in ("territorial", "invasao", "omissao")
            if key not in item["sections"]
        ]
        if missing:
            problems.append(f"{name}: section title not found: {', '.join(missing)}")
        if item["rows"] == 0:
            problems.append(f"{name}: no chapter I records parsed")
        # a record with no state means the state header was not recognised, and
        # every downstream MS filter silently drops it
        unstated = item["rows"] - sum(item["state_rows"].values())
        if unstated:
            problems.append(
                f"{name}: {unstated} of {item['rows']} rows have no state"
            )
            marks.append(f"no-state {unstated}")
        if item["state_totals"]:
            marks.append(f"states {len(item['state_totals'])}")
        skips = {}
        for _, reason, _ in item["skipped"]:
            skips[reason] = skips.get(reason, 0) + 1
        skip_note = ""
        if skips:
            skip_note = "  skipped " + ", ".join(f"{k}={v}" for k, v in skips.items())
        print(
            f"{item['year']:<6}{name[:50]:<52}{item['rows']:>6}   "
            + "  ".join(marks)
            + skip_note,
            file=sys.stderr,
        )

    if problems:
        print("", file=sys.stderr)
        for problem in problems:
            print(f"warning: {problem}", file=sys.stderr)
        if strict:
            raise SystemExit("error: --strict, structure checks failed")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Chapter I case tables from Cimi .txt files into one CSV."
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        default=["docs/cimi-reports/txt"],
        help="directories and/or .txt files (default: docs/cimi-reports/txt)",
    )
    parser.add_argument(
        "-o",
        "--out",
        default="chapter1_conflicts.csv",
        help="output CSV (default: chapter1_conflicts.csv)",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="scan input directories recursively",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail on structure mismatches instead of warning",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="skip the per-file summary on stderr",
    )
    args = parser.parse_args(argv)

    files = collect_inputs(args.inputs, args.recursive)
    if not files:
        raise SystemExit("error: no input .txt files")

    stats = []
    rows = []
    for path in files:
        file_rows, parsed, totals, sections = parse_file(path, stats)
        rows.extend(file_rows)

    rows.sort(key=lambda row: row["year"])

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    if not args.no_report:
        report(stats, args.strict)
    print(f"{out}: {len(rows)} rows from {len(files)} file(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
