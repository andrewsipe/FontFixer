# Vendored FontCore subset

fontfixer ships a minimal copy of [FontCore](https://github.com/andrewsipe/FontCore)
so it installs without the full library, a submodule, or a symlink.

**Source:** FontCore 0.2.4 (`v0.3.0`)

**Do not edit these files here.** Fix them in FontCore, then re-sync.

## Declared modules

- `core_console_config.py`
- `core_console_styles.py`
- `core_file_collector.py`
- `core_logging_config.py`

## Refresh

From a FontCore checkout:

```bash
python tools/vendor_fontcore.py sync ../fontfixer
```

The module list lives in `[tool.fontcore-vendor]` in this project's `pyproject.toml`.
