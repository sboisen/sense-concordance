"""Render a static HTML page for one Louw-Nida sense.

Shows every verse attesting the sense, with each BSB (English) word
annotated underneath with the Louw-Nida sense code(s) of its aligned Greek
word, cross-linked to the other senses' pages. Reads the JSON lookups built
by build_sense_concordance.py plus data/nt_BSB.tsv (for full verse text,
including function words and punctuation that carry no sense).

Run with: uv run python src/render_sense_page.py
"""

import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from biblelib.book import Books

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HTML_DIR = Path(__file__).resolve().parent.parent / "html" / "senses"
SENSE_VERSES_PATH = DATA_DIR / "sense_verses.json"
BSB_LOOKUP_PATH = DATA_DIR / "bsb_sense_lookup.json"
BSB_TSV_PATH = DATA_DIR / "nt_BSB.tsv"

EXAMPLE_ENTRY_CODE = "60.22"
# An additional batch of senses to generate alongside the example page,
# picked as the next 30 distinct sense codes in sorted order.
ADDITIONAL_SENSE_COUNT = 30


def load_book_usfm_numbers() -> dict[str, str]:
    """Return USFM 3-letter book code -> 2-digit USFM book number, e.g. 'MAT' -> '40'."""
    return {code: book.usfmnumber for code, book in Books().items()}


def ref_to_verse_num(ref: str, book_numbers: dict[str, str]) -> str:
    """Return the zero-padded 'BBCCCVVV' verse id for a display ref like 'MAT 1:17'."""
    book_code, chapter_verse = ref.split(" ", 1)
    chapter, verse = chapter_verse.split(":")
    return f"{book_numbers[book_code]}{int(chapter):03d}{int(verse):03d}"


def index_bsb_tokens() -> dict[str, list[dict]]:
    """Return verse_num -> list of BSB token rows (in verse order), from nt_BSB.tsv."""
    by_verse: dict[str, list[dict]] = defaultdict(list)
    with BSB_TSV_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            by_verse[row["source_verse"]].append(row)
    return by_verse


def token_codes(bsb_id: str, bsb_lookup: dict) -> tuple[str, ...]:
    """Return the sorted, deduplicated sense codes for a BSB token (empty if none)."""
    entries = bsb_lookup.get(bsb_id, [])
    codes = {code for entry in entries for code in entry["senses"]}
    return tuple(sorted(codes))


def sense_tooltip(code: str, sense_verses: dict) -> str:
    """Return an HTML-escaped 'glosses — definitionShort' tooltip string for a sense code."""
    label = sense_verses.get(code, {}).get("label", {})
    parts = [part for part in (label.get("glosses"), label.get("definitionShort")) if part]
    return html.escape(" — ".join(parts))


def render_verse_row(
    verse_num: str, tokens: list[dict], bsb_lookup: dict, entry_code: str, sense_verses: dict
) -> str:
    """Render the two-row (words / codes) inner table for one verse."""
    word_cells = []
    code_cells = []  # list of (colspan, codes) to render, pre-merged
    run_codes: tuple[str, ...] | None = None
    run_length = 0

    def flush_run():
        if run_length:
            code_cells.append((run_length, run_codes))

    for token in tokens:
        codes = token_codes(token["id"], bsb_lookup)
        bold = entry_code in codes
        text = html.escape(token["text"])
        if bold:
            text = f"<strong>{text}</strong>"
        word_cells.append(f"<td>{text}</td>")

        if codes and codes == run_codes:
            run_length += 1
        else:
            flush_run()
            run_codes = codes
            run_length = 1
    flush_run()

    code_cell_html = []
    for colspan, codes in code_cells:
        if not codes:
            code_cell_html.append(f'<td colspan="{colspan}"></td>')
        else:
            links = " ".join(
                f'<a href="{c}.html" title="{sense_tooltip(c, sense_verses)}">{c}</a>' for c in codes
            )
            code_cell_html.append(f'<td colspan="{colspan}" class="codes">{links}</td>')

    return (
        '<table class="verse-text"><tbody>'
        f"<tr>{''.join(word_cells)}</tr>"
        f"<tr>{''.join(code_cell_html)}</tr>"
        "</tbody></table>"
    )


def render_sense_page(
    entry_code: str,
    sense_data: dict,
    bsb_lookup: dict,
    book_numbers: dict[str, str],
    bsb_index: dict[str, list[dict]],
    sense_verses: dict,
) -> str:
    """Return a full standalone HTML document for one sense."""
    label = sense_data["label"]
    h1 = f"{label['entryCode']} — \"{label['glosses']}\" — {label['definitionShort']}"
    h2 = f"{label['lexDomains']} &gt; {label['lexSubDomains']}"

    rows = []
    for ref in sense_data["verses"]:
        verse_num = ref_to_verse_num(ref, book_numbers)
        tokens = bsb_index[verse_num]
        verse_html = render_verse_row(verse_num, tokens, bsb_lookup, entry_code, sense_verses)
        rows.append(f"<tr><td class=\"ref\">{html.escape(ref)}</td><td>{verse_html}</td></tr>")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(h1)}</title>
<style>
body {{ font-family: Georgia, serif; margin: 2em; }}
h1 {{ font-size: 1.4em; }}
h2 {{ font-size: 1.1em; color: #555; font-weight: normal; }}
table.verses {{ border-collapse: collapse; width: 100%; }}
table.verses > tbody > tr > td {{ vertical-align: top; padding: 0.6em 0.8em; border-bottom: 1px solid #ddd; }}
td.ref {{ white-space: nowrap; font-weight: bold; color: #333; }}
table.verse-text {{ border-collapse: collapse; }}
table.verse-text td {{ padding: 0 0.3em; text-align: center; vertical-align: top; }}
table.verse-text tr:first-child td {{ font-size: 1.05em; }}
table.verse-text td.codes {{ font-size: 0.75em; }}
table.verse-text td.codes a {{ color: #0645ad; text-decoration: none; }}
table.verse-text td.codes a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<h1>{html.escape(h1)}</h1>
<h2>{h2}</h2>
<table class="verses"><tbody>
{''.join(rows)}
</tbody></table>
</body>
</html>
"""


def main() -> None:
    sense_verses = json.loads(SENSE_VERSES_PATH.read_text(encoding="utf-8"))
    bsb_lookup = json.loads(BSB_LOOKUP_PATH.read_text(encoding="utf-8"))
    book_numbers = load_book_usfm_numbers()
    bsb_index = index_bsb_tokens()

    HTML_DIR.mkdir(parents=True, exist_ok=True)

    additional_codes = [
        code for code in sorted(sense_verses) if code != EXAMPLE_ENTRY_CODE
    ][:ADDITIONAL_SENSE_COUNT]
    entry_codes = [EXAMPLE_ENTRY_CODE] + additional_codes

    for entry_code in entry_codes:
        page = render_sense_page(
            entry_code, sense_verses[entry_code], bsb_lookup, book_numbers, bsb_index, sense_verses
        )
        out_path = HTML_DIR / f"{entry_code}.html"
        out_path.write_text(page, encoding="utf-8")
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
