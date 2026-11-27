"""
Font style analysis.

This module provides the FontStyleAnalyzer class for determining font style
characteristics including italic angle, bold weight, and oblique vs italic distinction.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from statistics import median
from typing import Iterable, List, Optional, Sequence

try:
    from fontTools.ttLib import TTFont
    from fontTools.pens.statisticsPen import StatisticsPen
except ImportError:
    TTFont = None  # Type hint fallback
    StatisticsPen = None

from .utilities import glyph_name_for_codepoint

# Uppercase vertical stems via Unicode; cmap resolves uniXXXX / custom names.
# Lowercase is skipped: StatisticsPen often reports the wrong sign on italic lc.
# N is skipped too: its diagonal leans left even in an upright font, and once H and I read under the
# floor it was the only sample left, so upright fonts got a positive angle of several degrees.
_SLANT_CODEPOINTS: Sequence[int] = (
    0x0048,  # H
    0x0049,  # I
)

_SLANT_NAME_FALLBACKS: Sequence[str] = (
    "H",
    "uni0048",
    "I",
    "uni0049",
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
            if len(samples) > 1 and max(samples) - min(samples) > 2.0:
                # H and I disagree: their average is an angle neither glyph has. Keep the one the font already
                # agrees with; with no stored angle, H (the first sample) decides.
                stored = 0.0
                if "post" in self.font:
                    try:
                        stored = float(self.font["post"].italicAngle or 0.0)
                    except (TypeError, ValueError):
                        stored = 0.0
                if abs(stored) >= 0.1:
                    return round(min(samples, key=lambda a: abs(a - stored)), 2)
                return round(samples[0], 2)
            return round(float(median(samples)), 2)

        # Measurement failed or stayed under the floor. Names can be stale (an Upright file that was named Italic keeps its
        # wrong angle forever), so the outlines get the last word, but only when they positively read upright: the stems
        # of H, I, l, E and the rest lean under half a degree (stricter than FontCore's 1, since this zeroes a stored angle). A font with no straight stems cannot be measured, and an
        # italic named as one keeps its stored angle (below).
        if self._outlines_read_upright() and not self._named_italic_with_italic_lean():
            return 0.0

        # Do not zero out a named italic/oblique that already carries a post angle.
        if self._name_implies_italic() or self._name_implies_oblique():
            if "post" in self.font:
                try:
                    post_angle = float(self.font["post"].italicAngle or 0.0)
                except (TypeError, ValueError):
                    post_angle = 0.0
                if abs(post_angle) >= 0.1:
                    return round(post_angle, 2)

        return 0.0

    def _named_italic_with_italic_lean(self) -> bool:
        """An italic-named font whose stored angle leans the italic way (-1 degree or more to the right). Stair-stepped
        and pixel italics (AM_BobbyDigital) have no long slanted edge to measure, so upright-looking stems prove nothing
        there. A positive stored angle on an italic name is not an italic lean, so it can still be corrected."""
        if not (self._name_implies_italic() or self._name_implies_oblique()) or "post" not in self.font:
            return False
        try:
            return float(self.font["post"].italicAngle or 0.0) <= -1.0
        except (TypeError, ValueError):
            return False

    def _outlines_read_upright(self) -> bool:
        """True only when the stem outlines are measurable and upright (FontCore.core_slant_measure)."""
        try:
            from FontCore.core_slant_measure import check_slant

            check = check_slant(self.font)
        except Exception:
            return False
        return check.measured is not None and check.verdict != "unmeasurable" and abs(check.measured) < 0.5

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

        # A variable font's slope comes from its tables (fvar, STAT, the italic bits, the names and the instances
        # vote), not from the names alone: an italic variable font named "Regular" keeps its italic flags
        # (FontCore DECISIONS.md, Area 5). A font with no free axes is static in effect and follows its names.
        if "fvar" in self.font:
            try:
                from FontCore.core_variable_traits import analyze_variable_traits

                path = getattr(getattr(getattr(self.font, "reader", None), "file", None), "name", None)
                traits = analyze_variable_traits(self.font, Path(path).stem if path else None)
                if traits.is_variable and not traits.no_free_axes:
                    self._is_italic = traits.slope == "italic"
                    self._is_oblique = bool(traits.slope_word) and traits.slope_word.lower() == "oblique"
            except Exception:
                pass  # keep the name-based answer

        # Bold: the word "Bold" in the style, nothing else. usWeightClass is not used (a Semibold is often 700
        # too), matching fontnameid, so running one tool after the other does not flip the flags back.
        # The style records are ID2 and ID17; the full name (ID4) is read only when neither exists.
        texts = self._name_texts((2, 17)) or self._name_texts((4,))
        self._is_bold = any(re.search(r"\bbold\b", t) for t in texts)
