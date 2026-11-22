# FontFixer

**Version 1.4.1**

Tidy OpenType fonts in a single pass — OS/2, style flags, glyphs, and legacy kern — without renaming or touching vertical metrics.

Intended pipeline: naming cleanup ([FontNameID](https://github.com/andrewsipe/FontNameID)) → **FontFixer** → metrics ([ebrium](https://github.com/andrewsipe/ebrium)).

**Docs:** [Handlers, family slant, flags, and safety](https://andrewsipe.github.io/FontFixer/) · also `fontfixer --help`

## Install

Preferred: [uv](https://docs.astral.sh/uv/):

```bash
uv tool install "git+https://github.com/andrewsipe/FontFixer.git"
# later: uv tool upgrade fontfixer
```

From a clone: `uv tool install --editable .` (edits take effect immediately).

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

1. **os2** — OS/2 v4, embedding, monospace, `USE_TYPO_METRICS` (WWS left alone)  
2. **style** — measurement-driven angles (multi-glyph); name-driven italic/oblique bits; sync post/hhea/OS/2/head/CFF  
3. **glyph** — drawn `.notdef`; nbsp width matches space  
4. **kern** — drop legacy `kern` when GPOS `kern`/`vkrn` is present  

After a normal run (style enabled, interactive TTY), a **family slant review** surveys
families by measured angle and may prompt to SET/CLEAR italic/oblique *flags* when
named italics define a clear upright vs slanted split — Apply all / Review each / Quit.
Roman-only or incomplete families are skipped. Angles stay as measured.

Naming stays in FontNameID; metrics stay in ebrium.

For handler detail, family slant rules, every flag, and how `-n` differs from `--validate-only`, use the [doc site](https://andrewsipe.github.io/FontFixer/).

## Related

- [FontNameID](https://github.com/andrewsipe/FontNameID) — name-table editing  
- [Ebrium](https://github.com/andrewsipe/ebrium) — vertical metrics normalization  
- [Changelog](CHANGELOG.md)
