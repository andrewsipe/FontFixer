# FontFixer

**Version 1.1.0**

A simple OpenType tidy-up tool: OS/2, style flags, glyphs, and legacy kern — one pass per font.

Intended workflow: run **after** naming cleanup (FontNameID) and **before** metrics normalization.

## Features

- **Single-pass**: Opens each font once, applies selected tidy-ups, writes once
- **Four handlers**: `os2`, `style`, `glyph`, `kern` (naming belongs in FontNameID)
- **Parallel processing**: Multi-core support for large collections
- **Corruption quarantine**: Moves bad files to `<input>/_quarantine/` by default

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

```bash
fontfixer fonts/

# Recursive, all CPU cores
fontfixer -r -j 0 fonts/

# Write tidied copies instead of overwriting
fontfixer -o tidy/ fonts/

# Only specific handlers
fontfixer --handlers os2,style fonts/

# Skip a handler
fontfixer --skip-handlers kern fonts/

# Report problems without applying changes
fontfixer --validate-only -v fonts/MyFont.ttf
```

**WARNING:** By default changes overwrite the originals (no backup). Use `-o`, `--validate-only`, or `-n` first when unsure.

## Available Handlers

| Handler | Description |
|---------|-------------|
| `os2` | Upgrade OS/2 to v4; installable embedding; monospace; USE_TYPO_METRICS, WWS |
| `style` | Sync italic/bold angles and flags across post, hhea, OS/2, head (after os2) |
| `glyph` | Ensure .notdef is drawn; ensure nbsp (U+00A0) matches space width |
| `kern` | Remove legacy kern table when GPOS is present |

## Handler Execution Order

1. **os2** — Upgrades OS/2 to v4 (required before style)
2. **style** — Depends on OS/2 v4
3. **glyph** — Independent
4. **kern** — Independent

Naming cleanup is intentionally out of scope; use **FontNameID** for that.

## Architecture

```
FontFixer/
├── main.py                          # CLI entry point
├── support/
│   ├── constants.py
│   ├── data_models.py
│   ├── decorators.py
│   ├── utilities.py
│   ├── bitfield.py
│   ├── style_analyzer.py
│   ├── corruption_detection.py
│   ├── handlers/
│   │   ├── base_handler.py
│   │   ├── os2_handler.py
│   │   ├── style_handler.py
│   │   ├── glyph_handler.py
│   │   └── kern_handler.py
│   └── font_fixer.py
└── FontCore/                        # Vendored slim FontCore subset
```

See `FontCore/VENDOR.md` for which modules are included and how to refresh them.

## License

See the main project license.
