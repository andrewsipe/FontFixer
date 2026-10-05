"""
Kern table handler.

This handler removes legacy kern tables when GPOS already provides kerning.
"""

from typing import Dict, Any

try:
    from fontTools.ttLib import TTFont
except ImportError:
    TTFont = None  # Type hint fallback

from .base_handler import TableHandler
from ..data_models import HANDLER_KERN
from ..utilities import gpos_has_kerning


class KernHandler(TableHandler):
    """
    Handles kern table cleanup.

    Implements fix 10:
    - Remove legacy kern table if GPOS has kern/vkrn features
    """

    def get_table_name(self) -> str:
        return HANDLER_KERN.full_name

    def validate(self) -> Dict[str, Dict[str, Any]]:
        """Validate kerning table state."""
        has_gpos = "GPOS" in self.font
        has_kern = "kern" in self.font
        has_gpos_kern = gpos_has_kerning(self.font)

        # Redundant only when legacy kern coexists with GPOS kerning features.
        redundant = has_kern and has_gpos_kern
        self._track_validation(
            "kern_redundant",
            not redundant,
            f"Status: GPOS={has_gpos}, GPOS_kern={has_gpos_kern}, kern={has_kern}, "
            f"Compliant: {not redundant}",
        )

        return self.validations

    def fix(self) -> bool:
        """Remove legacy kern table if GPOS already kerns."""
        if not self.validations.get("kern_redundant", {}).get("valid", True):
            if "kern" in self.font and gpos_has_kerning(self.font):
                del self.font["kern"]
                self._track_change("has_kern", True, False, True)
                self._track_change("has_GPOS_kern", True, True, False, info_only=True)
                return True
        return False
