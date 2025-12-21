# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Quick Commands

**Run FontFixer on a directory:**
```bash
python main.py fonts/
python main.py -r -j 8 fonts/          # Recursive, 8 parallel workers
python main.py --validate-only fonts/  # Validation mode (no changes)
```

**Run import smoke test:**
```bash
python test_imports.py
```

**Lint code:**
```bash
ruff check support/ main.py
```

**Fix linting issues:**
```bash
ruff check --fix support/ main.py
```

## Architecture Overview

FontFixer is a modular, handler-based font validation and correction tool. The architecture centers on single-pass processing: each font is opened once, all fixes are applied, then written once.

### Key Design Principles

1. **Handler-Based Architecture**: Each font table type (OS/2, style, glyphs, kerning, names) has its own handler class. Handlers inherit from `TableHandler` base class and implement fix logic in a standardized way.

2. **Critical Execution Order**: Handlers must execute in a specific order due to inter-handler dependencies:
   - **OS2TableHandler** (first): Upgrades OS/2 table to v4, which is required by subsequent handlers
   - **StyleConsistencyHandler** (depends on OS/2 v4): Fixes style consistency across multiple tables
   - **GlyphHandler** (independent): Fixes .notdef and nbsp glyphs
   - **KernHandler** (independent): Removes legacy kern table when GPOS exists
   - **NameTableHandler** (last): Cleanup operation, doesn't affect other handlers

3. **Single-Pass Processing**: FontFixer opens each font once (with appropriate bounding box settings), applies all handler fixes sequentially, then writes the result. This is ~10-12x faster than sequential ftcli-fix-loop workflows.

### Module Organization

```
FontFixer/
├── main.py                      # CLI entry point, argument parsing, orchestration
├── support/
│   ├── font_fixer.py            # FontFixer class (orchestrator)
│   ├── data_models.py           # FontFixResult, HandlerSpec data classes
│   ├── handlers/
│   │   ├── base_handler.py      # TableHandler ABC, ChangeBuilder
│   │   ├── os2_handler.py       # OS/2 table fixes
│   │   ├── style_handler.py     # Style consistency fixes
│   │   ├── glyph_handler.py     # .notdef and nbsp fixes
│   │   ├── kern_handler.py      # Legacy kern removal
│   │   └── name_handler.py      # Name table cleanup
│   ├── corruption_detection.py  # Corruption detection and quarantine
│   ├── constants.py             # OpenType constants
│   ├── bitfield.py              # Bitfield specifications
│   ├── style_analyzer.py        # Font style analysis utilities
│   ├── name_table_utils.py      # Name table manipulation
│   ├── decorators.py            # @conditional_fix decorator
│   └── utilities.py             # Misc utility functions
└── FontCore/                    # Symlink to shared FontCore module
```

### Core Data Flow

1. **main.py**: Parses arguments → collects font files → spawns worker processes
2. **FontFixer.fix_font()**: Opens font → runs handlers in order → writes result
3. **Handlers**: Read font tables → detect issues → apply fixes via ChangeBuilder → return changes
4. **FontFixResult**: Tracks what changed, which handlers ran, any errors or quarantine status

### Handler Pattern

Each handler follows this pattern:
```python
class MyHandler(TableHandler):
    def handle(self, font, font_fixer=None) -> tuple[bool, dict]:
        # Analyze tables and detect issues
        # Build changes using ChangeBuilder
        # Return (was_changed, changes_dict)
```

The `ChangeBuilder` class provides a structured way to track property changes with old/new values, enabling detailed change reporting.

## Important Considerations

- **Glyph Bounding Box Validation**: FontFixer detects glyphs with out-of-range bounds (>signed 16-bit) and reopens the font without `recalcBBoxes` to preserve original values. This prevents fonttools from auto-correcting bounds that may be intentional.

- **Corruption Quarantine**: Fonts detected as corrupted are moved to a quarantine directory rather than processed, preventing broken fonts from being silently modified.

- **Font Flavor Preservation**: Original font flavor (WOFF, WOFF2) is preserved when font is reopened with different bounding box settings.

- **Parallel Processing**: Uses ProcessPoolExecutor to process multiple fonts concurrently. Each worker process receives font paths and processes them independently.

- **FontCore Dependency**: Requires symlink to FontCore for console styling and file collection utilities. Path discovery logic searches up directory tree to find FontCore.

## Testing

- **test_imports.py**: Smoke test that verifies all modules can be imported successfully. Good baseline check before larger changes.
- **--validate-only mode**: Preview what changes would be made without modifying files. Useful for testing handler logic on specific fonts.

## Extending FontFixer

To add a new handler:
1. Create handler class in `support/handlers/` inheriting from `TableHandler`
2. Implement `handle(font, font_fixer)` method
3. Register in handler execution order in `font_fixer.py` if order-dependent
4. Add HandlerSpec to `data_models.py`
5. Update handler selection logic in `main.py` argument parsing
6. Update README.md with handler description
