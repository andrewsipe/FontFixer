# Vendored FontCore subset

FontFixer ships a minimal copy of FontCore so it installs without the full
library or a git submodule.

## Included modules

- `core_file_collector.py` — font path collection
- `core_console_styles.py` — console UX formatting
- `core_console_config.py` — theme / labels / Rich setup
- `core_logging_config.py` — logging helpers required by the console stack

## Refresh from monorepo FontCore

From the Good Font Scripts monorepo root:

```bash
cp FontCore/core_file_collector.py \
   FontCore/core_console_styles.py \
   FontCore/core_console_config.py \
   FontCore/core_logging_config.py \
   FontFixer/FontCore/
```

Re-copy when console or collector APIs change in a way FontFixer relies on.
This tree is owned by FontFixer; it is not kept in live sync with FontCore.
