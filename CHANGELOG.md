# Changelog

All notable changes to FontFixer will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.7.2] - 2026-11-27

### Fixed
- A font whose outlines are upright but carries a wrong `post.italicAngle` now gets angle 0 and caret slope 0/1. The outlines decide: every long stem edge leans under half a degree and the whole letter shapes lean under 3 (FontCore `core_slant_measure`). This replaces the earlier rule that trusted a single glyph's area statistic, which wrote 17 and 34 degrees on fonts whose H has an off-centre crossbar, and the rule that kept a stored angle because the names said Italic (an Upright file named Italic held 11.93 for good).
- A stored angle with the wrong sign (a right-leaning italic stored as +13) is set to the measured angle when the stem edges and the whole letter shapes agree on the lean. Where they disagree (a script whose edges lean but whose letters barely do, or a lean of about 3 degrees) the stored angle stays.
- Stair-stepped and pixel italics (every long edge vertical, the letters leaning as a whole) and fonts with no straight stems to measure keep their stored angle as before, and the CFF `ItalicAngle` is synced to it.

## [1.7.1] - 2026-11-27

### Changed
- A warning fontTools writes while it reads a font (an unsorted Coverage, a huge advance height) now prints as a `WARNING` line under that font's own block. It used to print where the worker read the font, which with parallel workers was a few files away from the one it was about.

## [1.7.0] - 2026-11-27

### Added
- The glyph pass repairs an advance width or height stored as unsigned overflow: a negative value read back as 63100, which fontTools reports as a "huge advance height". An advance above 32767 is never intended. A height gets the font's most common height, a space width gets the nbsp width (and the reverse), and any other width gets the font's median width. Side bearings are kept. This replaces the stand-alone advance-width script.

## [1.6.1] - 2026-11-27

FontCore 0.11.9 vendored (see `FontCore/VENDOR.md`).

### Fixed
- nameID 2 (Regular / Italic / Bold / Bold Italic) follows the italic flags when FontFixer changes them, in the style pass and in the family slant review. Before, the flags were corrected and ID2 kept the old value until fontnameid ran.
- The family slant review no longer reads the `Upright Italic` marker (the ID17 of a font with a free slope) as an italic name, so free-slope fonts such as `FL_ScienceSans*-Variable` are not told to set italic flags at an angle of 0. The filename now counts as a name cue (`BT_Circuit-VariableItalic`).
- A variable font whose `ital` axis never reaches upright (BT_Circuit, Costaline) is read as Italic, so the style pass sets its italic flags.
- The filename's own slope word (`QualionNeue-VariableOblique`) keeps the Oblique bit; the style pass used to clear it and the review set it again on every run.

## [1.6.0] - 2026-11-26

FontCore 0.11.4 vendored (see `FontCore/VENDOR.md`).

### Fixed
- An italic variable font whose names do not say Italic keeps its italic flags: for a variable font the style flags follow the tables' slope decision (fvar, STAT, the italic bits, the names, the instances), not the names alone. A font with no free axes still follows its names.

## [1.5.1] - 2026-11-25

### Fixed

- Upright fonts no longer get a positive `post.italicAngle` (and caret slope) of several degrees. The slant was sampled on `H`, `I` and `N`; in an upright font `H` and `I` read 0 and fell under the 2 degree floor, leaving the diagonal of `N` as the only sample. `N` is no longer sampled.
- When `H` and `I` disagree by more than 2 degrees, the angle nearest the one already stored wins (with none stored, `H`), instead of the average of the two, which neither glyph has.
- Re-running FontFixer on a font written with the wrong angle resets it to 0.

## [1.5.0] - 2026-11-25

FontCore 0.8.0 vendored (`core_run_report` added).

### Changed

- Every font now prints as one block in the same order, sequential or `-j`: header, what changed, result. The worker no longer prints; the main process prints from the result, so the parallel path no longer captures output.
- The closing line is one sentence: "Updated 2, unchanged 4, no problems."

## [1.4.3] - 2026-11-25

FontCore 0.7.0 vendored (see `FontCore/VENDOR.md`).

### Changed
- File collection follows one set of rules: macOS junk (`._*`, `__MACOSX`) and hidden files and folders are skipped, each real file is listed once (a symlink and its target are one file), and a path that does not exist gets a warning. Binary formats are the default; this tool asks for TTX where it handles it. FontFixer reads binary fonts only (it never opened TTX).

## [1.4.2] - 2026-11-22

### Fixed
- With `-j N` (or `-j 0`) the console output was out of order: each font's `UPDATED` lines were printed straight from the worker processes, so they appeared before the file's header, after it, or mixed with other fonts, and color codes were sometimes cut in half. Each worker now sends its output back with its result, and the parent prints one block per font: the `PARSING File n of N` header, what the handlers changed, then the result and where it was saved. Single-worker runs are unchanged. The blocks appear in the order the fonts finish, not the input order.

## [Unreleased]

### Changed
- Install and update instructions use `uv tool install` / `uv tool upgrade` (pipx is no longer mentioned).

## [1.4.1] - 2026-11-22

### Fixed
- Style flags no longer disagree with `fontnameid`. Found by running both tools in turn on 802 intake fonts: FontFixer set BOLD from `usWeightClass` 700 (so a Semibold or Ultrabold at 700 came back Bold), and read leftover Mac name records (a Mac `Semi Bold` or `Bold Italic` could set BOLD or ITALIC). Now BOLD follows the word Bold in the style (ID2 and ID17; the full name only when neither exists), and BOLD, ITALIC and OBLIQUE are read from the Windows English records unless the font has none. A second FontFixer pass after `fontnameid` changes nothing.

## [1.4.0] - 2026-11-21

FontCore 0.4.0 vendored (see `FontCore/VENDOR.md`).

### Changed
- An Oblique-named face now gets the ITALIC bit and macStyle italic as well as OBLIQUE (OS/2 v4+), the same flags `fontnameid` writes for its ID2 (Italic). Before, FontFixer cleared ITALIC on Oblique faces and the two tools undid each other. Family slant review follows the same rule.
- Flags still follow the label only: a slanted face named Regular keeps Regular flags.

## [1.3.6] - 2026-11-21

### Fixed
- Vendored FontCore is stamped as 0.3.1 (the 0.3.0 copy was labeled 0.2.4 in `FontCore/VENDOR.md`). No change to what the tool does.

## [1.3.5] - 2026-11-21

### Changed
- Vendored FontCore refreshed to v0.3.0 (console wording and counts: "1 file" / "3 files", `Finished`, one `Proceed?`). No change to what the tool does to fonts.

## [1.3.4] - 2026-11-20

### Fixed
- The family-slant review fix path kept no timestamp: it opened fonts with the default and stamped the current time on save.
- Fonts are opened with `recalcTimestamp=False`, so a save keeps the original `head.modified`
  (fontTools otherwise stamps the current time on every save, even with no edits). A regression test fails
  if a `TTFont()` open omits the flag.

## [1.3.3] - 2026-11-20

### Changed
- Vendored FontCore refreshed to v0.2.0 (see `FontCore/VENDOR.md`). A filename
  containing square brackets is no longer read as a console style tag.
- The vendored copy is now produced by FontCore's `tools/vendor_fontcore.py`,
  with the module list declared under `[tool.fontcore-vendor]` in `pyproject.toml`.

## [1.3.2] - 2026-10-05

### Added
- Static docs site under `docs/` for GitHub Pages (handlers, family slant, flags,
  safety). README slimmed to install + quick start with a Docs link;
  `project.urls.Documentation` and `--help` docs URL point at
  https://andrewsipe.github.io/FontFixer/

### Fixed
- **Family slant review:** Prefer nameID 16 (typographic family) over nameID 1 so
  RIBBI-split weights (`Babel Black`, `Babel Book`, …) group as one family instead
  of dozens of “incomplete (only one cut)” skips

### Changed
- **Family slant review:** In roman-only families (no named Italic/Oblique), do not
  SET italic flags from angle spread alone — weight-correlated roman noise was
  producing false recommendations; CLEAR of misplaced flags on the upright side
  is still allowed
- **Docs:** Family slant page plus updated handlers/style split, safety prompt,
  and nav (`docs/family-slant.html`)

## [1.3.1] - 2026-10-05

### Changed
- **Family slant review:** Clearer survey (one line per family) and recommendations
  that state the flag action (SET/CLEAR italic) instead of forward/backward counts
- **Family slant review:** When a family has named Italic/Oblique cuts, unlabeled
  Romans stay on the upright side so mild positive angles don’t invent a slant band
- **Family slant review:** Survey rows use FontCore `OK` / `WARNING` / `SKIPPED`
  status labels with column-aligned family names

## [1.3.0] - 2026-10-05

### Added
- **Family slant review** (interactive post-pass, no new CLI flag): after a normal
  run that includes the style handler, outline families by measured angle, recommend
  italic/oblique *flag* fixes when upright vs slanted clusters disagree with current
  bits, then prompt **Apply all / Review each / Quit**. Skips incomplete or ambiguous
  families (no upright reference, all upright, tiny spread). Angles are not rewritten.

## [1.2.1] - 2026-10-05

### Changed
- **style:** Italic/oblique `fsSelection` / `macStyle` bits follow name labels only;
  measured slant no longer marks a Roman as italic. Angles and caret stay measurement-driven.

## [1.2.0] - 2026-10-05

### Changed
- **style:** Measure italic angle from multiple uppercase stem glyphs via cmap
  (`H`/`I`/`N`, with `uniXXXX` fallbacks); use the median of samples above the 2°
  floor (dominant sign preferred)
- **style:** If measurement fails but names say Italic/Oblique, keep a non-zero
  `post.italicAngle` instead of forcing 0°
- **style:** Italic/oblique name words set flags even when measured slant is weak
- **style:** Sync `CFF` TopDict `ItalicAngle` with the analyzed angle
- **style:** Clear only bold/italic bits in `head.macStyle` (do not zero the field)
- **os2:** Set `USE_TYPO_METRICS` only; leave the WWS bit unchanged
- **os2:** Resolve `sxHeight` / `sCapHeight` via cmap (`x` / `H`) with uni-name fallbacks
- **kern:** Drop legacy `kern` only when GPOS advertises `kern` or `vkrn` (not merely
  when any GPOS table exists)

## [1.1.2] - 2026-09-20

### Changed
- Rich help v2: handlers, examples, exit status, and docs rendered as themed sections
- Move `-h` / `--version` into a trailing `general` group; drop plain-text epilog

## [1.1.1] - 2026-09-20

### Changed
- `--help` shows a Rich "Heads up" panel for overwrite risk (replaces WARNING text)

## [1.1.0] - 2026-09-20

### Removed
- **`name` handler** — naming cleanup belongs in FontNameID; also removes the old
  aggressive drops of nameIDs 13/14/18/19 from this tool’s default pass
- `support/handlers/name_handler.py` and `support/name_table_utils.py`

### Changed
- Positioned as a post-naming / pre-metrics tidy-up (OS/2, style, glyph, kern)
- Tightened handler help blurbs; handlers list aligned with option help columns
- Default handlers: `os2,style,glyph,kern`

## [1.0.2] - 2026-09-20

### Changed
- CLI help rewritten: overwrite warning up front; `-n` vs `--validate-only` contrasted; quarantine path documented
- `--handlers` / `--skip-handlers` mutually exclusive in usage; handler names from one source
- `--version` added; install/deps sections removed from `--help`
- `--skip-handlers` / `--handlers` preserve canonical handler order
- `-o` no longer creates the output directory during `-n` / `--validate-only`
- `name` handler help names license IDs 13/14 explicitly

## [1.0.1] - 2026-09-20

### Added
- Vendored slim `FontCore/` package (console + file collector only) for standalone installs
- GitHub / local `pip install` packaging without FontCore submodule

### Changed
- Console script is **`fontfixer` only** (`FontFixer` is an optional user alias)
- Dropped FontCore symlink / `.gitmodules` dependency

## [1.0.0] - 2024-12-XX

### Added
- Modular refactor from monolithic script (`FontFileTools/Tools_FontFixer.py`)
- Handler-based architecture with 5 specialized handlers:
  - OS2TableHandler: OS/2 table version, embedding permissions, monospace detection
  - StyleConsistencyHandler: Style consistency across post, hhea, OS/2, and head tables
  - GlyphHandler: .notdef structure and nbsp (U+00A0) fixes
  - KernHandler: Legacy kern table cleanup
  - NameTableHandler: Name table cleanup (Windows English only)
- Corruption detection and quarantine system
- Comprehensive documentation (README.md, inline docstrings)
- Version tracking (`__version__ = "1.0.0"`)
- Smoke test for import validation (`test_imports.py`)

### Changed
- Refactored from single-file script to modular structure:
  - 16 modules organized in `support/` directory
  - Clear separation of concerns (handlers, utilities, data models)
  - Improved maintainability and testability
- Original script (`FontFileTools/Tools_FontFixer.py`) marked as deprecated
- Handler execution order explicitly documented and enforced:
  1. OS2TableHandler (upgrades OS/2 to v4)
  2. StyleConsistencyHandler (depends on OS/2 v4)
  3. GlyphHandler (independent)
  4. KernHandler (independent)
  5. NameTableHandler (independent, runs last)

### Architecture
- **16 modules** organized in `support/` directory:
  - `constants.py`: OpenType constants
  - `data_models.py`: FontFixResult, HandlerSpec
  - `decorators.py`: @conditional_fix decorator
  - `utilities.py`: Utility functions
  - `bitfield.py`: Bitfield specifications
  - `name_table_utils.py`: Name table manipulation
  - `style_analyzer.py`: Font style analysis
  - `corruption_detection.py`: Corruption detection and quarantine
  - `font_fixer.py`: FontFixer orchestrator
  - `handlers/`: Handler implementations (5 handlers)
- **FontCore dependency**: Vendored slim subset under `FontCore/` (standalone installs)
- **Single-pass processing**: Opens each font once, applies all fixes, writes once
- **Parallel processing**: Multi-core support via ProcessPoolExecutor

### Performance
- ~10-12x faster than sequential ftcli-fix-loop for equivalent operations
- Memory-efficient: Suitable for directories with 1000+ font files

### Documentation
- README.md with usage examples and handler descriptions
- Comprehensive docstrings in all modules
- Handler execution order explicitly documented
- CHANGELOG.md for tracking changes

