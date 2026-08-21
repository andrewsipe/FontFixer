# Product refinement notes — FontFixer

Captured during the 2026-08-21 declutter pass. Use for a later product/release pass. **Not** user-facing docs.

## Declutter verdict

**Nothing to archive inside `FontFixer/`.** This package is already the modular successor to the old monolith. All `support/` modules are referenced; CLI surface matches the predecessor.

Predecessor (already archived earlier in this cleanup):

| Path | Role |
|------|------|
| `_misc/_archive/Tools_FontFixer.py` | Former monolithic script from FontFileTools; marked deprecated in favor of this package |

CLI flag parity check (declutter date): **identical** argparse surface between archived monolith and `main.py` (`-r/-j/-o/-n/-v`, `--handlers`, `--skip-handlers`, `--validate-only`, `--no-quarantine`). Same five handlers (os2, style, glyph, kern, name).

## Active tree

| Path | Role |
|------|------|
| `main.py` | CLI entry |
| `support/font_fixer.py` | Orchestrator |
| `support/handlers/*` | Table-specific fixers |
| `support/corruption_detection.py` | Quarantine / corrupt detection |
| `support/{bitfield,constants,data_models,decorators,name_table_utils,style_analyzer,utilities}.py` | Shared helpers (all used) |
| `test_imports.py` | Smoke import check (not a full pytest suite) |
| `CHANGELOG.md` / `README.md` / `pyproject.toml` | Packaging + docs (`fontfixer` / `FontFixer` console scripts) |

## Product-pass refinements (deferred)

1. **Real tests** — `test_imports.py` only proves imports; add fixture-based tests for each handler and quarantine paths.
2. **Move smoke test** under `tests/` and wire `pytest` in `pyproject.toml`.
3. **Version honesty** — CHANGELOG says `[1.0.0] - 2024-12-XX`; align date / bump when shipping.
4. **Name-handler policy** — “Windows English only” + dropping nameIDs is aggressive; document as intentional or make opt-in for a “safe” vs “strict” profile.
5. **Overlap with siblings** — FontFileTools still has GASP / coverage / UPM tools; FontNameID owns name rewriting. Product pitch should stay “single-pass structural fixes,” not full name-table authoring.
6. **`raw_github_urls.txt`** — PushCore noise; keep out of release artifacts.
7. **Local `fontfixer.egg-info/`** — gitignored build residue; safe to delete locally anytime.

## Do not lose

- Handler **execution order** (OS/2 → style → glyph → kern → name) — documented as load-bearing.
- Corruption quarantine behavior (`_quarantine/`, `--no-quarantine`).
- Parity with archived monolith until intentional behavior changes are changelog’d.
