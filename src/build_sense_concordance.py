"""Build Louw-Nida sense concordance data.

Joins the Greek NT (SBLGNT) token data, its Louw-Nida sense tagging (from the
Macula Greek dataset), and the SBLGNT<->BSB word alignment, to produce two
lookup tables:

- data/sense_verses.json: for every Louw-Nida sense attested on a content
  word (noun, verb, adj, adv), a human-readable label plus the sorted list
  of verse references where that sense occurs.
- data/bsb_sense_lookup.json: for every BSB (English) token, the list of
  {lemma, senses} pairs for each aligned Greek source token, so English
  display text can be annotated/linked back to Greek senses.

Run with: uv run python src/build_sense_concordance.py
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

from biblealignlib.burrito.source import macula_unprefixer
from biblealignlib.burrito.target import TargetReader
from acailib.lexicon.ubsdgnt import UBSParser

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MACULA_PATH = DATA_DIR / "macula-greek-SBLGNT.tsv"
BSB_PATH = DATA_DIR / "nt_BSB.tsv"
ALIGNMENT_PATH = DATA_DIR / "SBLGNT-BSB-manual.json"
SENSE_VERSES_OUT = DATA_DIR / "sense_verses.json"
BSB_LOOKUP_OUT = DATA_DIR / "bsb_sense_lookup.json"

CONTENT_POS = {"noun", "verb", "adj", "adv"}


def load_content_tokens() -> tuple[dict[str, dict], dict[str, str]]:
    """Return (bare SBLGNT id -> {lemma, text, verse_num, senses}, verse_num -> display ref).

    macula-greek-SBLGNT.tsv already carries pos (as `class`, verified
    identical to SBLGNT.tsv's `pos` for every token), lemma, text, and the
    Louw-Nida `ln` codes, so it alone suffices as the per-token source --
    no separate read of SBLGNT.tsv is needed.

    `verse_num` is the zero-padded "BBCCCVVV" numeric id (the first 8
    characters of the bare token id), which sorts correctly as a plain
    string in canonical book/chapter/verse order; `ref` from the macula
    file (e.g. "MAT 1:1!2", stripped of the trailing "!N") is a
    human-readable display string for the same verse.
    """
    tokens: dict[str, dict] = {}
    verse_labels: dict[str, str] = {}
    no_ln = 0
    with MACULA_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if row["class"] not in CONTENT_POS:
                continue
            if not row["ln"]:
                no_ln += 1
                continue
            bare_id = macula_unprefixer(row["xml:id"])
            verse_num = bare_id[:8]
            verse_labels[verse_num] = row["ref"].split("!")[0]
            tokens[bare_id] = {
                "lemma": row["lemma"],
                "text": row["text"],
                "verse_num": verse_num,
                "senses": row["ln"].split(),
            }
    print(f"Content tokens with LN data: {len(tokens)}; skipped (no ln value): {no_ln}")
    return tokens, verse_labels


def load_alignment_map() -> dict[str, list[str]]:
    """Return bare SBLGNT source id -> list of bare BSB target ids."""
    with ALIGNMENT_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    source_to_targets: dict[str, list[str]] = {}
    for record in data["records"]:
        targets = record["target"]
        for source_id in record["source"]:
            source_to_targets[macula_unprefixer(source_id)] = targets
    return source_to_targets


def build_outputs(
    tokens: dict[str, dict],
    source_to_targets: dict[str, list[str]],
    targets: TargetReader,
) -> tuple[dict[str, set[str]], dict[str, list[dict]]]:
    """Walk content tokens, aggregating sense->verses and bsb_id->[{lemma, senses}]."""
    sense_verses: dict[str, set[str]] = defaultdict(set)
    bsb_senses: dict[str, list[dict]] = defaultdict(list)
    no_alignment = 0
    excluded_targets_skipped = 0

    for sblgnt_id, info in tokens.items():
        for sense in info["senses"]:
            sense_verses[sense].add(info["verse_num"])

        bsb_ids = source_to_targets.get(sblgnt_id)
        if bsb_ids is None:
            no_alignment += 1
            continue
        for bsb_id in bsb_ids:
            target = targets.get(bsb_id)
            if target is not None and target.exclude:
                excluded_targets_skipped += 1
                continue
            bsb_senses[bsb_id].append({"lemma": info["lemma"], "senses": info["senses"]})

    print(f"Content tokens with no alignment record: {no_alignment}")
    print(f"Excluded (punctuation) target tokens skipped: {excluded_targets_skipped}")
    return sense_verses, bsb_senses


def enrich_sense_labels(sense_codes) -> dict[str, dict]:
    """Return sense code -> UBS lexicon label dict (via acailib's UBSParser), when available."""
    parser = UBSParser()
    labels: dict[str, dict] = {}
    missing = 0
    for code in sense_codes:
        try:
            meaning = parser.get_entryCode_meanings(code)
            labels[code] = meaning.serialize()
        except KeyError:
            missing += 1
            labels[code] = {}
    print(f"Sense codes with no UBS lexicon entry: {missing} of {len(sense_codes)}")
    return labels


def main() -> None:
    tokens, verse_labels = load_content_tokens()
    source_to_targets = load_alignment_map()
    targets = TargetReader(BSB_PATH)

    sense_verses, bsb_senses = build_outputs(tokens, source_to_targets, targets)
    labels = enrich_sense_labels(sense_verses.keys())

    sense_verses_out = {
        code: {
            "label": labels[code],
            "verses": [verse_labels[v] for v in sorted(verses)],
        }
        for code, verses in sense_verses.items()
    }

    print(f"Distinct senses: {len(sense_verses_out)}")
    print(f"BSB tokens tagged with at least one sense: {len(bsb_senses)}")

    with SENSE_VERSES_OUT.open("w", encoding="utf-8") as f:
        json.dump(sense_verses_out, f, ensure_ascii=False, indent=2, sort_keys=True)
    with BSB_LOOKUP_OUT.open("w", encoding="utf-8") as f:
        json.dump(dict(bsb_senses), f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Wrote {SENSE_VERSES_OUT}")
    print(f"Wrote {BSB_LOOKUP_OUT}")


if __name__ == "__main__":
    main()
