# Changelog

All notable changes to FontFixer will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

