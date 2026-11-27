"""
Utility functions for font processing.

This module contains pure utility functions used throughout the FontFixer tool.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Iterable, Optional, Sequence

try:
    from fontTools.ttLib import TTFont
except ImportError:
    TTFont = None  # Type hint fallback

from .constants import SIGNED_16BIT_MAX, SIGNED_16BIT_MIN


def clamp_signed_16bit(value: int) -> int:
    """
    Clamp a value to signed 16-bit integer range (-32768 to 32767).

    Args:
        value: The value to clamp

    Returns:
        Clamped value within valid range
    """
    if value > SIGNED_16BIT_MAX:
        return SIGNED_16BIT_MAX
    elif value < SIGNED_16BIT_MIN:
        return SIGNED_16BIT_MIN
    return value


def glyph_name_for_codepoint(
    font: TTFont,
    codepoint: int,
    name_fallbacks: Sequence[str] = (),
) -> Optional[str]:
    """
    Resolve a glyph name for a Unicode codepoint via cmap, then optional names.

    Args:
        font: TTFont to inspect
        codepoint: Unicode code point
        name_fallbacks: Glyph names to try if cmap has no mapping

    Returns:
        Glyph name if present in the font, else None
    """
    try:
        glyph_order = set(font.getGlyphOrder())
    except Exception:
        glyph_order = set()

    try:
        cmap = font.getBestCmap() or {}
    except Exception:
        cmap = {}

    name = cmap.get(codepoint)
    if name and (not glyph_order or name in glyph_order):
        return name

    for fallback in name_fallbacks:
        if fallback in glyph_order or (
            not glyph_order and fallback in font.getGlyphSet()
        ):
            return fallback

    return None


def gpos_has_kerning(font: TTFont) -> bool:
    """
    Return True if GPOS advertises horizontal or vertical kerning features.

    Looks for feature tags ``kern`` / ``vkrn`` only — presence of other GPOS
    lookups alone is not treated as kerning.
    """
    if "GPOS" not in font:
        return False

    try:
        feature_list = font["GPOS"].table.FeatureList
    except Exception:
        return False

    if feature_list is None:
        return False

    try:
        records: Iterable = feature_list.FeatureRecord
    except Exception:
        return False

    for record in records:
        tag = getattr(record, "FeatureTag", None)
        if tag in ("kern", "vkrn"):
            return True

    return False



@contextlib.contextmanager
def capture_fonttools_warnings():
    """Collect what fontTools logs while a font is read and processed, instead of letting it print to the terminal.

    fontTools writes these lines itself, as the font is read, so with several fonts in flight they appear next to
    the wrong file. Yields a list that fills with each distinct message, with a count when one repeats.
    """
    messages: dict = {}

    class _Collect(logging.Handler):
        def emit(self, record):
            if record.levelno >= logging.WARNING:
                text = record.getMessage()
                messages[text] = messages.get(text, 0) + 1

    logger = logging.getLogger("fontTools")
    handler, propagate = _Collect(), logger.propagate
    logger.addHandler(handler)
    logger.propagate = False
    collected: list = []
    try:
        yield collected
    finally:
        logger.removeHandler(handler)
        logger.propagate = propagate
        collected.extend(text if n == 1 else f"{text} (x{n})" for text, n in messages.items())


_RIBBI = {"regular": (False, False), "italic": (False, True), "bold": (True, False), "bold italic": (True, True)}


def sync_style_link_name(font: TTFont, *, bold: bool, italic: bool) -> bool:
    """Make nameID 2 (Regular / Italic / Bold / Bold Italic) agree with the flags just written. A name that is not one of
    those four (a style the designer wrote out) is left alone."""
    if "name" not in font:
        return False
    want = ("Bold Italic" if italic else "Bold") if bold else ("Italic" if italic else "Regular")
    changed = False
    for record in font["name"].names:
        if record.nameID != 2:
            continue
        try:
            current = record.toUnicode().strip()
        except Exception:
            continue
        if current.lower() in _RIBBI and current != want:
            record.string = want
            changed = True
    return changed
