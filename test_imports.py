#!/usr/bin/env python3
"""Smoke test to verify all FontFixer modules can be imported."""

import sys
from pathlib import Path

# Add project root to path for imports
_project_root = Path(__file__).parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def test_imports():
    """Test that all modules can be imported."""
    errors = []

    try:
        from support import FontFixer, FontFixResult, HandlerSpec, CorruptionDetector  # noqa: F401

        print("✓ Core support modules imported successfully")
    except ImportError as e:
        errors.append(f"Core support modules: {e}")
        print(f"✗ Core support modules import failed: {e}")

    try:
        from support.handlers import (  # noqa: F401
            OS2TableHandler,
            StyleConsistencyHandler,
            GlyphHandler,
            KernHandler,
            NameTableHandler,
        )

        print("✓ Handler modules imported successfully")
    except ImportError as e:
        errors.append(f"Handler modules: {e}")
        print(f"✗ Handler modules import failed: {e}")

    try:
        from support import (  # noqa: F401
            constants,
            data_models,
            decorators,
            utilities,
            bitfield,
            name_table_utils,
            style_analyzer,
            corruption_detection,
            font_fixer,
        )

        print("✓ Utility modules imported successfully")
    except ImportError as e:
        errors.append(f"Utility modules: {e}")
        print(f"✗ Utility modules import failed: {e}")

    try:
        from FontFixer import __version__  # noqa: F401

        print(f"✓ Package version imported: {__version__}")
    except ImportError as e:
        errors.append(f"Package version: {e}")
        print(f"✗ Package version import failed: {e}")

    if errors:
        print(f"\n✗ {len(errors)} import error(s) found")
        return False
    else:
        print("\n✓ All modules imported successfully")
        return True


if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
