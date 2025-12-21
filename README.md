# FontFixer

**Version 1.0.0**

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

```bash
pip install -r requirements.txt
```

### Dependencies

- `fonttools>=4.0.0` - Font manipulation library
- `rich>=13.0.0` - Terminal formatting (optional, for enhanced output)

## Usage

### Basic Usage

```bash
# Process all fonts in a directory
python main.py fonts/

# Process recursively with 8 parallel workers
python main.py -r -j 8 fonts/

# Save fixed fonts to a different directory
python main.py -o output/ fonts/
```

### Handler Selection

```bash
# Only run specific handlers
python main.py --handlers os2,style fonts/

# Skip specific handlers
python main.py --skip-handlers name fonts/
```

### Validation Mode

```bash
# Preview what would be changed without modifying files
python main.py --validate-only -v fonts/MyFont.ttf
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

The project is organized into modular components:

```
FontFixer/
├── main.py                          # CLI entry point
├── support/
│   ├── constants.py                 # OpenType constants
│   ├── data_models.py               # FontFixResult, HandlerSpec
│   ├── decorators.py                 # @conditional_fix decorator
│   ├── utilities.py                  # Utility functions
│   ├── bitfield.py                   # Bitfield specifications
│   ├── name_table_utils.py           # Name table manipulation
│   ├── style_analyzer.py             # Font style analysis
│   ├── corruption_detection.py       # Corruption detection and quarantine
│   ├── handlers/
│   │   ├── base_handler.py           # TableHandler ABC, ChangeBuilder
│   │   ├── os2_handler.py            # OS2TableHandler
│   │   ├── style_handler.py          # StyleConsistencyHandler
│   │   ├── glyph_handler.py          # GlyphHandler
│   │   ├── kern_handler.py           # KernHandler
│   │   └── name_handler.py            # NameTableHandler
│   └── font_fixer.py                 # FontFixer orchestrator
└── FontCore/                         # Symlink to shared FontCore
```

## Original Script

The original script (`FontFileTools/Tools_FontFixer.py`) has been deprecated in favor of this modular version. It is kept for reference only.

## License

See the main project license.

