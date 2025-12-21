# Changelog

All notable changes to FontFixer will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **FontCore dependency**: Symlink to shared FontCore module
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

