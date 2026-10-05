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
| `support/{bitfield,constants,data_models,decorators,style_analyzer,utilities}.py` | Shared helpers (all used) |
| `test_imports.py` | Smoke import check (not a full pytest suite) |
| `CHANGELOG.md` / `README.md` / `pyproject.toml` | Packaging + docs (`fontfixer` console script) |
| `FontCore/` | Vendored slim subset (console + file collector); not a submodule |

## Packaging notes (2026-09-20)

- Vendored FontCore subset; **no** FontCore symlink/submodule.
- Canonical CLI: **`fontfixer`**. `FontFixer` is an optional user alias only.
- PushCore: FontFixer is in `PROJECTS_WITHOUT_FONTCORE`.
- **v1.1.0:** `name` handler removed; use FontNameID for naming. Handlers: os2 → style → glyph → kern.

## Docs site

Static Pages site in `docs/` (handlers, family slant, flags, safety). README is
the product front door; advanced detail lives on the site.

Enable once on GitHub: **Settings → Pages → Deploy from a branch → `main` / `/docs`**.
URL: https://andrewsipe.github.io/FontFixer/

Optional: set the repo About “Website” field to that URL.

## Product-pass refinements (deferred)

1. **Real tests** — `test_imports.py` only proves imports; add fixture-based tests for each handler, quarantine paths, and family slant grouping/skip cases.
2. **Move smoke test** under `tests/` and wire `pytest` in `pyproject.toml`.
3. **Overlap with siblings** — FontFileTools still has GASP / coverage / UPM tools; FontNameID owns name rewriting. Product pitch: post-naming tidy-up before metrics.
4. **`raw_github_urls.txt`** — PushCore noise; keep out of release artifacts.
5. **Local `fontfixer.egg-info/`** — gitignored build residue; safe to delete locally anytime.

## Family slant review — shipped (v1.3.0–1.3.2)

Shipped in `support/family_slant_review.py`. User-facing rules: `docs/family-slant.html`.

**Shipped behavior (do not regress):**

- Group by nameID **16** then **1** (RIBBI-split weights stay one family).
- Style pass: angles measurement-driven; italic/oblique bits name-driven.
- Family review: recommend SET/CLEAR flags only; never rewrite angles.
- Named Italic/Oblique present → unlabeled Romans stay upright for flag advice.
- Roman-only families → skip SET from angle alone; CLEAR on upright still allowed.
- Prompt: Apply all / Review each / Quit; skip for `-n` / `--validate-only` / non-TTY / no style.

## Do not lose

- Handler **execution order** (OS/2 → style → glyph → kern) — documented as load-bearing.
- Corruption quarantine behavior (`_quarantine/`, `--no-quarantine`).
- Parity with archived monolith until intentional behavior changes are changelog’d.
- **v1.2.x / v1.3.x style split:** angles measurement-driven; italic/oblique bits name-driven in the style pass; family review is the only place that may recommend sibling-relative flag SET/CLEAR.
