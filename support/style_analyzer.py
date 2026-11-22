"""
Font style analysis.

This module provides the FontStyleAnalyzer class for determining font style
characteristics including italic angle, bold weight, and oblique vs italic distinction.
"""

from __future__ import annotations

import math
import re
from statistics import median
from typing import Iterable, List, Optional, Sequence

try:
    from fontTools.ttLib import TTFont
    from fontTools.pens.statisticsPen import StatisticsPen
except ImportError:
    TTFont = None  # Type hint fallback
    StatisticsPen = None

from .utilities import glyph_name_for_codepoint

# Uppercase stems via Unicode; cmap resolves uniXXXX / custom names.
# Lowercase is skipped: StatisticsPen often reports the wrong sign on italic lc.
_SLANT_CODEPOINTS: Sequence[int] = (
    0x0048,  # H
    0x0049,  # I
    0x004E,  # N
)

_SLANT_NAME_FALLBACKS: Sequence[str] = (
    "H",
    "uni0048",
    "I",
    "uni0049",
    "N",
    "uni004E",
)

_NAME_IDS_STYLE = (1, 2, 4, 6, 16, 17)


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

    def _name_texts(self, name_ids) -> List[str]:
        """Lowercased name strings for these IDs. Windows English records only when the font has them (as
        fontnameid reads), so a leftover Mac record from an old tool cannot decide the style flags."""
        if "name" not in self.font:
            return []
        records = self.font["name"].names
        windows_only = any(r.platformID == 3 and r.langID == 0x409 for r in records)
        out: List[str] = []
        for record in records:
            if record.nameID not in name_ids:
                continue
            if windows_only and not (record.platformID == 3 and record.langID == 0x409):
                continue
            try:
                out.append(record.toUnicode().lower())
            except Exception:
                continue
        return out

    def _style_name_strings(self) -> List[str]:
        """Lowercased name-table strings used for style words."""
        return self._name_texts(_NAME_IDS_STYLE)

    def _name_implies_oblique(self) -> bool:
        return any(re.search(r"\boblique\b", s) for s in self._style_name_strings())

    def _name_implies_italic(self) -> bool:
        return any(re.search(r"\bitalic\b", s) for s in self._style_name_strings())

    def _iter_slant_glyph_names(self) -> Iterable[str]:
        """Yield unique glyph names for slant sampling (cmap first, then names)."""
        seen = set()
        glyph_set = self.font.getGlyphSet()

        for codepoint in _SLANT_CODEPOINTS:
            name = glyph_name_for_codepoint(
                self.font, codepoint, name_fallbacks=()
            )
            if name and name not in seen and name in glyph_set:
                seen.add(name)
                yield name

        for name in _SLANT_NAME_FALLBACKS:
            if name not in seen and name in glyph_set:
                seen.add(name)
                yield name

    def _measure_glyph_angle(self, glyph_name: str) -> Optional[float]:
        """Return italic angle in degrees from one glyph, or None on failure."""
        try:
            glyph_set = self.font.getGlyphSet()
            pen = StatisticsPen(glyph_set)
            glyph_set[glyph_name].draw(pen)
            slant = pen.slant
            if not slant:
                return None
            return -math.degrees(math.atan(slant))
        except Exception:
            return None

    def _calculate_italic_angle(self, min_slant: float = 2.0) -> float:
        """
        Calculate italic angle from multiple stem glyphs.

        - Measure H/I/N/h/n via cmap (with uniXXXX name fallbacks)
        - Use the median of samples with |angle| >= min_slant
        - If none clear the floor but names say italic/oblique, keep a
          non-zero post.italicAngle instead of forcing 0
        """
        samples: List[float] = []
        for glyph_name in self._iter_slant_glyph_names():
            angle = self._measure_glyph_angle(glyph_name)
            if angle is not None and abs(angle) >= min_slant:
                samples.append(angle)

        if samples:
            # Prefer the dominant sign so one noisy glyph cannot flip the result.
            neg = [a for a in samples if a < 0]
            pos = [a for a in samples if a > 0]
            if len(neg) > len(pos):
                samples = neg
            elif len(pos) > len(neg):
                samples = pos
            return round(float(median(samples)), 2)

        # Measurement failed or stayed under the floor — do not zero out a
        # named italic/oblique that already carries a post angle.
        if self._name_implies_italic() or self._name_implies_oblique():
            if "post" in self.font:
                try:
                    post_angle = float(self.font["post"].italicAngle or 0.0)
                except (TypeError, ValueError):
                    post_angle = 0.0
                if abs(post_angle) >= 0.1:
                    return round(post_angle, 2)

        return 0.0

    def _analyze_style(self):
        """Analyze style flags from names; angle stays measurement-driven."""
        name_oblique = self._name_implies_oblique()
        name_italic = self._name_implies_italic()

        # Flags follow labels only — measured slant must not mark a Roman italic, and a slanted face
        # named Regular stays Regular (Italic is a linked alternative to a Regular).
        # Oblique is slanted too: it gets ITALIC as well as OBLIQUE, the same flags fontnameid writes for
        # the face's ID2 (Italic). Angle / caret remain honest to outline measurement elsewhere.
        self._is_oblique = name_oblique
        self._is_italic = name_italic or name_oblique

        # Bold: the word "Bold" in the style, nothing else. usWeightClass is not used (a Semibold is often 700
        # too), matching fontnameid, so running one tool after the other does not flip the flags back.
        # The style records are ID2 and ID17; the full name (ID4) is read only when neither exists.
        texts = self._name_texts((2, 17)) or self._name_texts((4,))
        self._is_bold = any(re.search(r"\bbold\b", t) for t in texts)
