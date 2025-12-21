"""
Font style analysis.

This module provides the FontStyleAnalyzer class for determining font style
characteristics including italic angle, bold weight, and oblique vs italic distinction.
"""

import math
import re

try:
    from fontTools.ttLib import TTFont
    from fontTools.pens.statisticsPen import StatisticsPen
except ImportError:
    TTFont = None  # Type hint fallback
    StatisticsPen = None

from .constants import WEIGHT_BOLD


class FontStyleAnalyzer:
    """
    Centralized font style analysis.

    Determines:
    - Italic angle
    - Is italic vs oblique
    - Is bold
    - Is regular
    """

    def __init__(self, font: TTFont):
        self.font = font
        self._italic_angle = None
        self._is_italic = None
        self._is_oblique = None
        self._is_bold = None

    @property
    def italic_angle(self) -> float:
        """Calculate italic angle (cached)."""
        if self._italic_angle is None:
            self._italic_angle = self._calculate_italic_angle()
        return self._italic_angle

    @property
    def is_italic(self) -> bool:
        """Determine if font is italic (cached)."""
        if self._is_italic is None:
            self._analyze_style()
        return self._is_italic

    @property
    def is_oblique(self) -> bool:
        """Determine if font is oblique (cached)."""
        if self._is_oblique is None:
            self._analyze_style()
        return self._is_oblique

    @property
    def is_bold(self) -> bool:
        """Determine if font is bold (cached)."""
        if self._is_bold is None:
            self._analyze_style()
        return self._is_bold

    def _calculate_italic_angle(self, min_slant: float = 2.0) -> float:
        """
        Calculate italic angle using StatisticsPen on 'H' glyph.

        Based on FoundryTools logic:
        - Uses StatisticsPen to calculate slant from 'H' glyph
        - Returns 0 if abs(angle) < min_slant (considers upright)
        - Returns calculated angle otherwise
        """
        try:
            glyph_set = self.font.getGlyphSet()
            if "H" not in glyph_set:
                return 0.0

            pen = StatisticsPen(glyph_set)
            glyph_set["H"].draw(pen)

            # StatisticsPen.slant is the tangent of the angle
            # Convert to degrees: angle = -arctan(slant) in degrees
            slant = pen.slant
            angle = -math.degrees(math.atan(slant)) if slant else 0.0

            # Round to reasonable precision
            angle = round(angle, 2)

            # If abs angle is below minimum, consider it upright
            if abs(angle) < min_slant:
                return 0.0

            return angle

        except Exception:
            return 0.0

    def _analyze_style(self):
        """Analyze font style from names and metrics."""
        is_slanted = abs(self.italic_angle) >= 2.0

        self._is_italic = False
        self._is_oblique = False
        self._is_bold = False

        # Check for oblique/italic in names
        if is_slanted and "name" in self.font:
            for record in self.font["name"].names:
                if record.nameID in [1, 2, 4, 6]:  # Family, Subfamily, Full, PostScript
                    name_str = record.toUnicode().lower()
                    # Check for "oblique" first (more specific)
                    if re.search(r"\boblique\b", name_str):
                        self._is_oblique = True
                        break
                    # Check for "italic" (but not if already found oblique)
                    elif re.search(r"\bitalic\b", name_str):
                        self._is_italic = True

            # Default to italic if slanted but no explicit name found
            if not self._is_oblique and not self._is_italic:
                self._is_italic = True

        # Check for bold
        if "OS/2" in self.font:
            os2 = self.font["OS/2"]
            if hasattr(os2, "usWeightClass") and os2.usWeightClass == WEIGHT_BOLD:
                self._is_bold = True
            else:
                # Fallback to name check
                if "name" in self.font:
                    for record in self.font["name"].names:
                        if record.nameID in [1, 2, 4, 6]:
                            name_str = record.toUnicode().lower()
                            # Use word boundary regex to avoid false matches
                            if re.search(r"\bbold\b", name_str):
                                self._is_bold = True
                                break
