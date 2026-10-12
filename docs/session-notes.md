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

## Session 2: HTML sense-page renderer

### Key decisions
- Generate one example sense page first (`60.22`, "fourteen") to validate the template before batching all 6,729 senses — per user's answer.
- Output location: `html/senses/<entryCode>.html`, with sense-code links as relative paths within that folder (e.g. `href="10.28.html"`).
- No cap/pagination on verse count per sense page, even for very frequent senses (e.g. `33.69` has 2,003 verses) — render everything.
- Reused `biblelib.book.Books()["MAT"].usfmnumber` to convert a display ref (`"MAT 1:17"`) back to the numeric verse id (`"40001017"`) needed to look up `nt_BSB.tsv` rows, rather than changing `sense_verses.json`'s schema from the previous session.
- Merge rule: consecutive BSB tokens sharing the exact same (possibly multi-code) sense-code set collapse into one `colspan` cell in the code row; tokens with no sense never merge with each other or with sensed neighbors, even if adjacent.

### Status: done for the example page
- `src/render_sense_page.py` written and run; `html/senses/60.22.html` generated and opened in browser.
- Verified against raw data for MAT 1:17: "there were fourteen" (BSB ids 40001017006-008) correctly merge into one cell linking both `10.28` and `60.22` (confirmed both codes genuinely present on all three tokens via `bsb_sense_lookup.json`); "generations" (10.28 only) gets its own unmerged, unbolded cell; all three "fourteen" occurrences bold (page's own sense); commas/"then" render as separate empty cells, never merged.
- HTML output validated as well-formed (no unclosed/mismatched tags).

### Next steps
- User to review `html/senses/60.22.html` visually; once approved, extend `main()` (or a new batch driver) to generate all 6,729 sense pages.

## Session 3: quoting + small batch

- Quoted `label.glosses` in the H1 (now renders as `60.22 — "fourteen" — ...`).
- Extended `main()` in `src/render_sense_page.py` to generate a configurable batch (`ADDITIONAL_SENSE_COUNT = 30`) alongside the original example: picks the next 30 distinct sense codes in sorted order (`1.1` through `1.30`), plus `60.22`. 31 pages now in `html/senses/`.
- Next: still not yet generating the full 6,729; batching logic is in place and just needs the count/selection raised if/when the user wants full coverage.

## Session 4: tooltips on sense links

- Added `sense_tooltip(code, sense_verses)` to `src/render_sense_page.py`, producing a `title="glosses — definitionShort"` attribute on every sense-code hyperlink (not just the page's own sense) — threaded `sense_verses` down through `render_sense_page` and `render_verse_row` so any linked code's label can be looked up, since a verse can link to codes other than the page's own.
- Degrades gracefully for the 11 codes with no UBS lexicon entry (e.g. `13.1`): empty `title=""`, no error.
- Regenerated all 31 existing pages; verified HTML still well-formed and spot-checked tooltip text against `data/sense_verses.json`.
