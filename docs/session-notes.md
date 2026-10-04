# Session notes

## Key decisions
- Join `data/SBLGNT.tsv` (pos) with `data/macula-greek-SBLGNT.tsv` (class/domain/ln) by id — the "SBLGNT with pos+LN" the task described is really these two files joined; `pos` and `class` were verified identical for all 137,741 tokens.
- Use `biblealignlib.burrito.source.SourceReader` / `.target.TargetReader` directly on the existing flat `data/` files (lightweight reuse); skip the full `Manager`/`AlignmentSet` pipeline since it expects a nested `CLEARROOT`-style directory layout this repo doesn't have.
- Parse `data/SBLGNT-BSB-manual.json` with plain `json` (records are a simple flat list; every source id appears in exactly one record).
- Fix `acailib.lexicon.ubsdgnt.UBSParser` (currently broken: `ModuleNotFoundError: No module named 'acai'`) by adding the user's local clone at `~/git/Clear-Bible/ACAI` as an editable path dependency (`acai`) in `pyproject.toml`, so LN sense codes can be enriched with domain/gloss text.
- Outputs: JSON files in `data/` — `sense_verses.json` (sense code → label + verse refs) and `bsb_sense_lookup.json` (BSB token id → list of `{lemma, senses}` for each aligned Greek source token, since one BSB token can align to more than one Greek word).

## Findings
- `nt_BSB.tsv` marks punctuation with `exclude = "y"` (29,242 rows) — must never receive sense tags.
- ~1,188 content-POS tokens have no `ln` value; ~1,291 of 71,210 content tokens have no alignment record at all. Both are skipped and logged, not fatal.
- `ln` codes are occasionally multiple (polysemy) and ~2,100 have letter suffixes (`93.108a`) for sub-senses.

## Open questions / risks
- Unconfirmed whether `UBSParser.get_entryCode_meanings` resolves letter-suffixed codes directly or only the base numeric code — need to verify during implementation and add a fallback (strip suffix for the gloss lookup only) if not.

## Next steps
- Add `acai` path dependency to `pyproject.toml`, `uv sync`, verify `UBSParser()` imports cleanly.
- Write `src/build_sense_concordance.py` per the approved plan (see `/Users/seanboisen/.claude/plans/generic-baking-deer.md`).
- Run it, sanity-check counts and spot-check both output files.

## Status: implementation complete

- Added `acai` as an editable local path dependency in `pyproject.toml` (pointing at `~/git/Clear-Bible/ACAI`), plus a `[tool.uv] override-dependencies = ["biblelib>=0.5.2,<0.6.0"]` override — `acailib` (pinned to `biblelib<0.4.0`) and `acai` (pinned to `biblelib>=0.5.2,<0.6.0`) have incompatible transitive pins on PyPI; the override forces a single resolvable `biblelib` version and both packages still work fine against it. Worth reporting upstream at some point, but unblocked for now.
- Resolved the open risk from the plan: `UBSParser.get_entryCode_meanings` DOES resolve letter-suffixed codes directly (e.g. `"93.108a"` works) — no fallback needed. Of 6,729 distinct LN codes used by content words, only 11 have no UBS lexicon entry (likely entries marked `IsBiblicalTerm == "N"`, which the parser filters out).
- Simplified the plan's step 1: `data/macula-greek-SBLGNT.tsv` alone provides pos (`class`), lemma, text, and `ln` for every token, so there was no need to also read `data/SBLGNT.tsv` via `SourceReader` as the plan first sketched — one less join, same result.
- `src/build_sense_concordance.py` written and run successfully:
  - 70,113 content tokens with LN data (1,097 skipped for no `ln` value)
  - 1,217 content tokens with no alignment record (skipped)
  - 0 excluded/punctuation BSB tokens ever appear in `bsb_sense_lookup.json`
  - 6,729 distinct senses written to `data/sense_verses.json` (each with a UBS-lexicon label plus sorted verse refs)
  - 112,081 BSB tokens tagged in `data/bsb_sense_lookup.json`, each as a list of `{lemma, senses}`
  - Spot-checked `sense_verses.json["33.19"]` (MAT 1:1, γένεσις) and the BSB tokens aligned to `n40001001002` — all correct. Note: BSB function-word tokens (e.g. "This", "is", "the" in MAT 1:1, which translate a single Greek word as a 4-word English phrase) legitimately do get tagged, since the alignment is phrase-level, not strictly word-for-word — this is correct, not a bug.

## Next steps
- None required for this step; it's done. Future: use these two JSON files to drive the HTML concordance display (not yet started/designed — AGENTS.md still says "Content Architecture: TBD").
