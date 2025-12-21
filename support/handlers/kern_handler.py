"""
Kern table handler.

This handler removes legacy kern tables when modern GPOS tables exist.
"""

from typing import Dict, Any

try:
    from fontTools.ttLib import TTFont
except ImportError:
    TTFont = None  # Type hint fallback

from .base_handler import TableHandler
from ..data_models import HANDLER_KERN


class KernHandler(TableHandler):
    """
    Handles kern table cleanup.

    Implements fix 10:
    - Remove legacy kern table if GPOS exists
    """

    def get_table_name(self) -> str:
        return HANDLER_KERN.full_name

    def validate(self) -> Dict[str, Dict[str, Any]]:
        """Validate kerning table state."""
        has_gpos = "GPOS" in self.font
        has_kern = "kern" in self.font

        self._track_validation(
            "kern_redundant",
            not (has_gpos and has_kern),
            f"Status: GPOS={has_gpos}, kern={has_kern}, Compliant: {not (has_gpos and has_kern)}",
        )

        return self.validations

    def fix(self) -> bool:
        """Remove legacy kern table if needed."""
        if not self.validations.get("kern_redundant", {}).get("valid", True):
            if "GPOS" in self.font and "kern" in self.font:
                del self.font["kern"]
                self._track_change("has_kern", True, False, True)
                self._track_change("has_GPOS", True, True, False, info_only=True)
                return True
        return False
