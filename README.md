# FontFixer

**Version 1.1.2**

Tidy OpenType fonts in a single pass — OS/2, style flags, glyphs, and legacy kern — without renaming or touching vertical metrics.

Intended pipeline: naming cleanup ([FontNameID](https://github.com/andrewsipe/FontNameID)) → **FontFixer** → metrics ([ebrium](https://github.com/andrewsipe/ebrium)).

**Docs:** [Handlers, flags, and safety](https://andrewsipe.github.io/FontFixer/) · also `fontfixer --help`

## Install

Preferred: [pipx](https://pipx.pypa.io/):

```bash
pipx install "git+https://github.com/andrewsipe/FontFixer.git"
# later: pipx upgrade fontfixer
```

Or from a clone: `pipx install .` / `pip install -e .`

The canonical command is **`fontfixer`**. On macOS a second `FontFixer` script is not shipped (case-insensitive collision); use `alias FontFixer=fontfixer` if you want the capital-F name.

Requires Python 3.9+.

## Quick start

```bash
fontfixer fonts/

# Recursive, all CPU cores
fontfixer -r -j 0 fonts/

# Write tidied copies instead of overwriting
fontfixer -o tidy/ fonts/

# Report problems without applying fixes
fontfixer --validate-only -v fonts/

# Only list files/handlers (fonts are not opened)
fontfixer -n fonts/

# Run a subset of handlers
fontfixer --handlers os2,style fonts/
fontfixer --skip-handlers kern fonts/
```

By default, fixes **overwrite originals** (no backup). Use `-o`, `--validate-only`, or `-n` first when unsure. Corrupted fonts are moved to `<input>/_quarantine/` unless you pass `--no-quarantine`.

## What it does (in short)

Four handlers, always in this order when enabled:

1. **os2** — OS/2 v4, embedding, monospace, `USE_TYPO_METRICS`, WWS  
2. **style** — sync italic/bold angles and flags (needs OS/2 v4)  
3. **glyph** — drawn `.notdef`; nbsp width matches space  
4. **kern** — drop legacy `kern` when GPOS is present  

Naming stays in FontNameID; metrics stay in ebrium.

For handler detail, every flag, and how `-n` differs from `--validate-only`, use the [doc site](https://andrewsipe.github.io/FontFixer/).

## Related

- [FontNameID](https://github.com/andrewsipe/FontNameID) — name-table editing  
- [ebrium](https://github.com/andrewsipe/ebrium) — vertical metrics normalization  
- [Changelog](CHANGELOG.md)
