# FontFixer

**Version 1.0.1**

A high-performance font validation and correction tool that applies comprehensive OpenType font fixes in a single pass.

## Overview

FontFixer is a modular, handler-based font fixing tool designed to replace sequential ftcli command workflows with efficient batch processing. It applies all fixes in a single pass, opening each font once, applying all corrections, and writing once.

## Features

- **Single-pass processing**: Opens each font once, applies all fixes, writes once
- **Handler-based design**: Modular table-specific validators and fixers
- **Parallel processing**: Multi-core support for large font collections
- **Comprehensive fixes**: OS/2 table, style consistency, glyph fixes, kerning cleanup, name table cleanup
- **Corruption detection**: Automatic detection and quarantine of corrupted fonts
- **Performance**: ~10-12x faster than sequential ftcli-fix-loop for equivalent operations

## Installation

The canonical command is **`fontfixer`**. On macOS, a second `FontFixer` script is not shipped (case-insensitive filesystem collision); use an optional alias if you want the capital-F name.

### From GitHub (recommended)

```bash
pip install "git+https://github.com/andrewsipe/FontFixer.git"
```

Or install from a zip download:

```bash
pip install https://github.com/andrewsipe/FontFixer/archive/refs/heads/main.zip
```

### From a clone / download

```bash
cd FontFixer
pip install .
# or editable during development:
pip install -e .
```

Then run:

```bash
fontfixer fonts/
```

Optional alias:

```bash
alias FontFixer=fontfixer
```

If the installer says the script is not on PATH, add Python’s user bin (e.g. `~/Library/Python/3.x/bin` on macOS) to your PATH.

### Dependencies

Installed automatically with the package:

- `fonttools>=4.0.0` — font manipulation
- `rich>=13.0.0` — terminal formatting

## Usage

### Basic Usage

```bash
fontfixer fonts/

# Process recursively with 8 parallel workers
fontfixer -r -j 8 fonts/

# Save fixed fonts to a different directory
fontfixer -o output/ fonts/
```

### Handler Selection

```bash
# Only run specific handlers
fontfixer --handlers os2,style fonts/

# Skip specific handlers
fontfixer --skip-handlers name fonts/
```

### Validation Mode

```bash
# Preview what would be changed without modifying files
fontfixer --validate-only -v fonts/MyFont.ttf
```

## Available Handlers

| Handler | Description |
|---------|-------------|
| `os2` | OS/2 table version upgrade, embedding permissions, monospace detection, USE_TYPO_METRICS and WWS flags |
| `style` | Style consistency across post, hhea, OS/2, and head tables (italic angle, caret slope, fsSelection, macStyle) |
| `glyph` | Glyph-level fixes: .notdef structure, nbsp (U+00A0) presence and width matching space character |
| `kern` | Legacy kern table removal when modern GPOS table exists |
| `name` | Name table cleanup: Windows English records only, removal of problematic nameIDs |

## Handler Execution Order

The handlers execute in a specific order that is critical for correct functionality:

1. **OS2TableHandler** - Upgrades OS/2 version, enables v4 features
2. **StyleConsistencyHandler** - Depends on OS/2 v4 being current
3. **GlyphHandler** - Independent
4. **KernHandler** - Independent
5. **NameTableHandler** - Independent, runs last

## Architecture

```
FontFixer/
├── main.py                          # CLI entry point
├── support/
│   ├── constants.py                 # OpenType constants
│   ├── data_models.py               # FontFixResult, HandlerSpec
│   ├── decorators.py                # @conditional_fix decorator
│   ├── utilities.py                 # Utility functions
│   ├── bitfield.py                  # Bitfield specifications
│   ├── name_table_utils.py          # Name table manipulation
│   ├── style_analyzer.py            # Font style analysis
│   ├── corruption_detection.py      # Corruption detection and quarantine
│   ├── handlers/
│   │   ├── base_handler.py          # TableHandler ABC, ChangeBuilder
│   │   ├── os2_handler.py           # OS2TableHandler
│   │   ├── style_handler.py         # StyleConsistencyHandler
│   │   ├── glyph_handler.py         # GlyphHandler
│   │   ├── kern_handler.py          # KernHandler
│   │   └── name_handler.py           # NameTableHandler
│   └── font_fixer.py                # FontFixer orchestrator
└── FontCore/                        # Vendored slim FontCore subset
```

See `FontCore/VENDOR.md` for which modules are included and how to refresh them.

## License

See the main project license.
