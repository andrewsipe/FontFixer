"""
Glyph handler.

This handler fixes glyph-level issues including .notdef structure
and nbsp (U+00A0) presence and metrics.
"""

from typing import Dict, Any, Tuple, Any as AnyType
import copy

try:
    from fontTools.ttLib import TTFont
except ImportError:
    TTFont = None  # Type hint fallback

from .base_handler import TableHandler
from ..data_models import HANDLER_GLYPH


class GlyphHandler(TableHandler):
    """
    Handles glyph-level fixes.

    Responsibilities:
    - .notdef glyph presence and structure
    - nbsp (U+00A0) presence and metrics
    """

    def get_table_name(self) -> str:
        return HANDLER_GLYPH.full_name

    def validate(self) -> Dict[str, Dict[str, Any]]:
        """Validate glyph issues."""
        self.validate_condition(
            "notdef_valid", lambda: self._validate_notdef_helper(), ".notdef validation"
        )
        self.validate_condition(
            "nbsp_present", lambda: self._validate_nbsp_helper(), "nbsp validation"
        )
        return self.validations

    def _validate_notdef_helper(self) -> Tuple[bool, str]:
        """Helper: check if .notdef is valid."""
        is_empty = False

        if "glyf" in self.font:
            glyf = self.font["glyf"]
            if ".notdef" in glyf:
                notdef = glyf[".notdef"]
                is_empty = notdef.numberOfContours == 0
        elif "CFF " in self.font:
            try:
                cff = self.font["CFF "].cff
                top_dict = cff.topDictIndex[0]
                char_strings = top_dict.CharStrings
                if ".notdef" in char_strings:
                    is_empty = self._is_cff_notdef_empty(char_strings[".notdef"])
            except Exception:
                pass

        is_valid = not is_empty
        return (
            is_valid,
            f"Status: .notdef glyph {'empty' if is_empty else 'valid'}, Compliant: {is_valid}",
        )

    def _validate_nbsp_helper(self) -> Tuple[bool, str]:
        """Helper: check if nbsp exists and has correct width."""
        if "cmap" not in self.font:
            return (True, "No cmap table")

        cmap = self.font.getBestCmap()
        if cmap is None:
            return (True, "No cmap")

        nbsp_present = 0x00A0 in cmap
        if not nbsp_present:
            return (
                False,
                "Status: nbsp (U+00A0) missing, Compliant: False",
            )

        # Also validate width if both space and nbsp exist
        if "hmtx" in self.font and 0x0020 in cmap:
            hmtx = self.font["hmtx"]
            space_glyph = cmap[0x0020]
            nbsp_glyph = cmap[0x00A0]
            space_width = hmtx[space_glyph][0]
            nbsp_width = hmtx[nbsp_glyph][0]
            width_correct = space_width == nbsp_width

            # Track width validation separately
            self._track_validation(
                "nbsp_width_correct",
                width_correct,
                f"Current: {nbsp_width}, Expected: {space_width}"
                if not width_correct
                else f"Current: {nbsp_width}, Expected: {space_width} (matches)",
            )
        else:
            self._track_validation("nbsp_width_correct", True, "Cannot validate width")

        return (
            True,
            "Status: nbsp (U+00A0) present, Compliant: True",
        )

    def fix(self) -> bool:
        """Fix glyph issues."""
        any_changed = False

        if not self.validations.get("notdef_valid", {}).get("valid", True):
            any_changed |= self._fix_notdef()

        if not self.validations.get("nbsp_present", {}).get("valid", True):
            any_changed |= self._fix_nbsp_missing()

        if not self.validations.get("nbsp_width_correct", {}).get("valid", True):
            any_changed |= self._fix_nbsp_width()

        return any_changed

    def _fix_notdef(self) -> bool:
        """Create .notdef glyph if empty."""
        if "glyf" in self.font:
            return self._fix_notdef_truetype()
        elif "CFF " in self.font:
            return self._fix_notdef_cff()
        return False

    def _fix_notdef_truetype(self) -> bool:
        """Fix .notdef for TrueType fonts."""
        glyf = self.font["glyf"]
        if ".notdef" not in glyf:
            return False

        notdef = glyf[".notdef"]
        if notdef.numberOfContours != 0:
            return False  # Already has contours

        # For variable fonts, try copying from space/nbsp first to avoid gvar issues
        is_variable = "gvar" in self.font
        if is_variable and self._copy_notdef_from_fallback(is_cff=False):
            return True

        # If we didn't copy, create new glyph (but skip for variable fonts)
        if is_variable:
            return False  # Skip fixing .notdef in variable fonts to avoid gvar table issues

        return self._create_notdef_truetype()

    def _fix_notdef_cff(self) -> bool:
        """Fix .notdef for CFF fonts."""
        try:
            cff = self.font["CFF "].cff
            top_dict = cff.topDictIndex[0]
            char_strings = top_dict.CharStrings

            if ".notdef" not in char_strings:
                return False

            cs = char_strings[".notdef"]
            if not self._is_cff_notdef_empty(cs):
                return False  # Already has content

            # For variable fonts, try copying from space/nbsp first to avoid gvar issues
            is_variable = "gvar" in self.font
            if is_variable and self._copy_notdef_from_fallback(is_cff=True):
                return True

            # If we didn't copy, create new glyph (but skip for variable fonts)
            if is_variable:
                return False  # Skip fixing .notdef in variable fonts to avoid gvar table issues

            return self._create_notdef_cff()
        except Exception:
            return False

    def _copy_notdef_from_fallback(self, is_cff: bool) -> bool:
        """Try copying .notdef from space (U+0020) or nbsp (U+00A0)."""
        if "cmap" not in self.font:
            return False

        cmap = self.font.getBestCmap()
        if not cmap:
            return False

        # Try space first, then nbsp
        for codepoint in [0x0020, 0x00A0]:
            if codepoint not in cmap:
                continue

            source_glyph = cmap[codepoint]

            if is_cff:
                if self._copy_notdef_cff(source_glyph):
                    self._track_notdef_copy(source_glyph, is_cff=True)
                    return True
            else:
                if self._copy_notdef_truetype(source_glyph):
                    self._track_notdef_copy(source_glyph, is_cff=False)
                    return True

        return False

    def _copy_notdef_truetype(self, source_glyph: str) -> bool:
        """Copy TrueType glyph to .notdef."""
        glyf = self.font["glyf"]
        if source_glyph not in glyf:
            return False

        source = glyf[source_glyph]
        if source.numberOfContours == 0:
            return False  # Don't copy empty glyphs

        glyf[".notdef"] = copy.deepcopy(source)

        # Remove gvar variations for .notdef
        self._remove_gvar_for_notdef()

        # Copy metrics
        if "hmtx" in self.font and source_glyph in self.font["hmtx"]:
            source_width = self.font["hmtx"][source_glyph][0]
            source_lsb = self.font["hmtx"][source_glyph][1]
            self.font["hmtx"][".notdef"] = (source_width, source_lsb)

        return True

    def _copy_notdef_cff(self, source_glyph: str) -> bool:
        """Copy CFF charstring to .notdef."""
        try:
            cff = self.font["CFF "].cff
            char_strings = cff.topDictIndex[0].CharStrings

            if source_glyph not in char_strings:
                return False

            source_cs = char_strings[source_glyph]

            # Check source is not empty
            program = source_cs.program
            if len(program) <= 2 and program[-1] == "endchar":
                return False

            char_strings[".notdef"] = copy.deepcopy(source_cs)

            # Remove gvar variations for .notdef
            self._remove_gvar_for_notdef()

            # Copy metrics
            if "hmtx" in self.font and source_glyph in self.font["hmtx"]:
                source_width = self.font["hmtx"][source_glyph][0]
                source_lsb = self.font["hmtx"][source_glyph][1]
                self.font["hmtx"][".notdef"] = (source_width, source_lsb)

            return True
        except Exception:
            return False

    def _create_notdef_truetype(self) -> bool:
        """Create new .notdef glyph for TrueType fonts."""
        from fontTools.pens.ttGlyphPen import TTGlyphPen

        upm = self.font["head"].unitsPerEm
        width = int(upm * 0.5)
        height = int(upm * 0.75)
        thickness = max(int(upm * 0.05), 50)

        pen = TTGlyphPen(self.font.getGlyphSet())
        self._draw_notdef_outline(pen, width, height, thickness)

        glyf = self.font["glyf"]
        glyf[".notdef"] = pen.glyph()

        # Update hmtx
        if "hmtx" in self.font:
            self.font["hmtx"][".notdef"] = (width, thickness)

        self.track_changes().add(".notdef_empty", True, False).add(
            ".notdef_width", 0, width
        ).add_info(".notdef_contours", 2).commit()

        return True

    def _create_notdef_cff(self) -> bool:
        """Create new .notdef glyph for CFF fonts."""
        from fontTools.pens.t2CharStringPen import T2CharStringPen

        upm = self.font["head"].unitsPerEm
        width = int(upm * 0.5)
        height = int(upm * 0.75)
        thickness = max(int(upm * 0.05), 50)

        # Get advance width from hmtx if available
        if "hmtx" in self.font and ".notdef" in self.font["hmtx"]:
            width = self.font["hmtx"][".notdef"][0]

        cff = self.font["CFF "].cff
        char_strings = cff.topDictIndex[0].CharStrings
        glyph_set = self.font.getGlyphSet()

        pen = T2CharStringPen(width=width, glyphSet=glyph_set)
        self._draw_notdef_outline(pen, width, height, thickness)

        new_charstring = pen.getCharString()

        # Preserve private dictionary reference
        original_charstring = char_strings[".notdef"]
        if hasattr(original_charstring, "private"):
            new_charstring.private = original_charstring.private

        char_strings[".notdef"] = new_charstring

        # Update hmtx
        if "hmtx" in self.font:
            self.font["hmtx"][".notdef"] = (width, thickness)

        self.track_changes().add(".notdef_empty", True, False).add(
            ".notdef_width", 0, width
        ).add_info(".notdef_contours", 2).commit()

        return True

    def _draw_notdef_outline(
        self, pen: AnyType, width: int, height: int, thickness: int
    ) -> None:
        """Draw standard .notdef outline (two rectangles)."""
        # Outer rectangle
        pen.moveTo((thickness, thickness))
        pen.lineTo((thickness, height - thickness))
        pen.lineTo((width - thickness, height - thickness))
        pen.lineTo((width - thickness, thickness))
        pen.closePath()

        # Inner rectangle
        pen.moveTo((thickness * 2, thickness * 2))
        pen.lineTo((width - thickness * 2, thickness * 2))
        pen.lineTo((width - thickness * 2, height - thickness * 2))
        pen.lineTo((thickness * 2, height - thickness * 2))
        pen.closePath()

    def _is_cff_notdef_empty(self, charstring: AnyType) -> bool:
        """Check if CFF .notdef charstring is empty."""
        try:
            program = charstring.program
            # Empty glyph: only endchar or width + endchar
            return len(program) <= 2 and program[-1] == "endchar"
        except Exception:
            # Fallback to bytecode check
            try:
                return len(charstring.bytecode) < 10
            except Exception:
                return False

    def _remove_gvar_for_notdef(self) -> None:
        """Remove .notdef variations from gvar table."""
        if "gvar" not in self.font:
            return

        try:
            gvar = self.font["gvar"]
            gid = self.font.getGlyphID(".notdef")
            if gid in gvar.variations:
                del gvar.variations[gid]
        except (KeyError, AttributeError, IndexError):
            pass

    def _track_notdef_copy(self, source_glyph: str, is_cff: bool) -> None:
        """Track .notdef changes when copied from another glyph."""
        width = 0
        contours = 0

        if "hmtx" in self.font and source_glyph in self.font["hmtx"]:
            width = self.font["hmtx"][source_glyph][0]

        if not is_cff and "glyf" in self.font:
            if source_glyph in self.font["glyf"]:
                contours = self.font["glyf"][source_glyph].numberOfContours

        self.track_changes().add(".notdef_empty", True, False).add_info(
            ".notdef_contours", contours
        ).add(".notdef_width", 0, width).commit()

    def _fix_nbsp_missing(self) -> bool:
        """Add nbsp if missing."""
        if "cmap" not in self.font:
            return False

        cmap = self.font.getBestCmap()
        if cmap is None or 0x00A0 in cmap:
            return False

        # Add nbsp by copying space (U+0020) if it exists
        if 0x0020 in cmap:
            space_glyph = cmap[0x0020]
            # Add mapping to cmap tables
            for table in self.font["cmap"].tables:
                if 0x0020 in table.cmap:
                    table.cmap[0x00A0] = space_glyph

            self._track_change("nbsp_exists", False, True, True)
            self._track_change("nbsp_glyph", None, space_glyph, True)
            return True

        return False

    def _fix_nbsp_width(self) -> bool:
        """Fix nbsp width to match space."""
        if "cmap" not in self.font or "hmtx" not in self.font:
            return False

        cmap = self.font.getBestCmap()
        if not cmap or 0x0020 not in cmap or 0x00A0 not in cmap:
            return False

        hmtx = self.font["hmtx"]
        space_glyph = cmap[0x0020]
        nbsp_glyph = cmap[0x00A0]

        space_width = hmtx[space_glyph][0]
        nbsp_width = hmtx[nbsp_glyph][0]

        if space_width != nbsp_width:
            # Copy space metrics to nbsp
            hmtx[nbsp_glyph] = hmtx[space_glyph]
            self._track_change(
                "space_width", space_width, space_width, False, info_only=True
            )
            self._track_change("nbsp_width", nbsp_width, space_width, True)
            return True

        return False
