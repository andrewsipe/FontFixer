# Changelog

All notable changes to FontFixer will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added
- Static docs site under `docs/` for GitHub Pages (handlers, flags, safety).
  README slimmed to install + quick start with a Docs link;
  `project.urls.Documentation` and `--help` docs URL point at
  https://andrewsipe.github.io/FontFixer/

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

