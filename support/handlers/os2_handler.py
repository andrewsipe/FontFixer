"""
OS/2 table handler.

This handler manages OS/2 table validation and correction including version
upgrades, embedding permissions, monospace detection, and selection flags.
"""

import struct
import unicodedata
from typing import Dict, Any, Tuple

try:
    from fontTools.ttLib import TTFont, TTLibError
    from fontTools.ttLib.tables.O_S_2f_2 import Panose
except ImportError:
    TTFont = None  # Type hint fallback
    TTLibError = Exception
    Panose = None

from .base_handler import TableHandler
from ..data_models import HANDLER_OS2
from ..bitfield import FS_SELECTION
from ..decorators import conditional_fix


class OS2TableHandler(TableHandler):
    """
    Handles OS/2 table validation and correction.

    Responsibilities:
    - Table version management (upgrade to version 4)
    - Embedding permissions (fsType = 0 for installable)
    - Width classification (monospace detection, xAvgCharWidth)
    - Selection flags (USE_TYPO_METRICS, WWS bits)
    - Metrics (sxHeight, sCapHeight, ulCodePageRange)
    """

    # Unicode codepoints allowed to be zero-width
    ZERO_WIDTH_ALLOWED = {
        0x0000,
        0x0008,
        0x0009,
        0x000D,
        0x001D,
        0x00AD,
        0x034F,
        0x061C,
        0x180E,
        0x200B,
        0x200C,
        0x200D,
        0x200E,
        0x200F,
        0x202A,
        0x202B,
        0x202C,
        0x202D,
        0x202E,
        0x2060,
        0x2061,
        0x2062,
        0x2063,
        0x2064,
        0x206A,
        0x206B,
        0x206C,
        0x206D,
        0x206E,
        0x206F,
        0xFEFF,
        0xFFF9,
        0xFFFA,
        0xFFFB,
    }

    # Unicode ranges for combining marks (zero-width allowed)
    COMBINING_MARK_RANGES = [
        (0x0300, 0x036F),
        (0x1AB0, 0x1AFF),
        (0x1DC0, 0x1DFF),
        (0x20D0, 0x20FF),
        (0xFE20, 0xFE2F),
    ]

    def get_table_name(self) -> str:
        return HANDLER_OS2.full_name

    def is_monospace(self) -> bool:
        """Check if font is truly monospaced."""
        try:
            if "hmtx" not in self.font:
                return False

            # Build glyph → codepoint mapping
            glyph_to_cp = self._build_glyph_codepoint_map()

            # Collect non-zero widths (excluding allowed zero-width glyphs)
            non_zero_widths = set()
            hmtx = self.font["hmtx"]

            for glyph_name in self.font.getGlyphOrder():
                width = hmtx[glyph_name][0]

                if width == 0:
                    # Check if zero-width is allowed for this glyph
                    if self._is_zero_width_allowed(glyph_name, glyph_to_cp):
                        continue

                if width > 0:
                    non_zero_widths.add(width)

            # Analyze width distribution
            return self._is_width_distribution_monospace(non_zero_widths)
        except Exception:
            return False

    def _build_glyph_codepoint_map(self) -> dict[str, int]:
        """Build reverse cmap: glyph_name -> codepoint."""
        if "cmap" not in self.font:
            return {}

        cmap = self.font.getBestCmap()
        if not cmap:
            return {}

        return {v: k for k, v in cmap.items()}

    def _is_zero_width_allowed(
        self, glyph_name: str, glyph_to_cp: dict[str, int]
    ) -> bool:
        """Check if glyph is allowed to be zero-width."""
        codepoint = glyph_to_cp.get(glyph_name)

        # Check explicit allowed list
        if codepoint in self.ZERO_WIDTH_ALLOWED:
            return True

        # Check combining mark ranges
        if codepoint and self._is_combining_mark(codepoint):
            return True

        # Check glyph name patterns
        if self._is_combining_mark_name(glyph_name):
            return True

        return False

    def _is_combining_mark(self, codepoint: int) -> bool:
        """Check if codepoint is in combining mark ranges."""
        # Check explicit ranges
        for start, end in self.COMBINING_MARK_RANGES:
            if start <= codepoint <= end:
                return True

        # Check Unicode category
        try:
            category = unicodedata.category(chr(codepoint))
            # Mn = Nonspacing Mark, Me = Enclosing Mark, Cf = Format
            return category in ("Mn", "Me", "Cf")
        except (ValueError, OverflowError):
            return False

    def _is_combining_mark_name(self, glyph_name: str) -> bool:
        """Check if glyph name suggests combining mark."""
        glyph_lower = glyph_name.lower()

        patterns = [
            "comb",
            "grave",
            "acute",
            "tilde",
            "dieresis",
        ]

        if any(pattern in glyph_lower for pattern in patterns):
            return True

        # Check uni03xx and uni04xx patterns
        if glyph_lower.startswith(("uni03", "uni04", "uni20d")):
            return True

        return False

    def _is_width_distribution_monospace(self, widths: set[int]) -> bool:
        """
        Determine if width distribution indicates monospace font.

        Rules:
        - 1 unique width: monospace
        - 2 widths where one is exactly double: CJK monospace
        - Otherwise: proportional
        """
        if len(widths) == 1:
            return True

        if len(widths) == 2:
            return self._is_cjk_monospace(widths)

        return False

    def _is_cjk_monospace(self, widths: set[int]) -> bool:
        """
        Check if font is CJK monospace (narrow + double-width glyphs).

        CJK monospace fonts have:
        - Two widths: narrow and exactly double
        - Significant number of glyphs at each width
        """
        assert len(widths) == 2, "CJK monospace check requires exactly 2 unique widths"
        widths_list = sorted(widths)

        # Check if wider is exactly double
        if widths_list[1] != widths_list[0] * 2:
            return False

        # Count glyphs at each width
        hmtx = self.font["hmtx"]
        narrow_count = sum(1 for w in hmtx.values() if w[0] == widths_list[0])
        wide_count = sum(1 for w in hmtx.values() if w[0] == widths_list[1])

        # If we have a significant number of both widths, it's likely CJK
        return narrow_count > 10 and wide_count > 10

    def validate(self) -> Dict[str, Dict[str, Any]]:
        """Validate OS/2 table state."""
        if "OS/2" not in self.font:
            self._track_validation("table_exists", False, "OS/2 table missing")
            return self.validations

        try:
            os2 = self.font["OS/2"]
        except (TTLibError, AttributeError, IndexError, ValueError) as e:
            # OS/2 table is corrupted and cannot be read
            error_msg = str(e) if str(e) else "Unknown error"
            self._track_validation(
                "table_readable",
                False,
                f"OS/2 table is corrupted and cannot be read: {error_msg}",
            )
            return self.validations

        # Fix corrupted panose field (should be an object, not a string)
        try:
            if hasattr(os2, "panose"):
                # Check if panose is corrupted (should be an object, not a string)
                if isinstance(os2.panose, str):
                    # Reconstruct panose as a proper object
                    new_panose = Panose()
                    # Try to decode the string if it looks like raw bytes
                    if len(os2.panose) >= 10:
                        try:
                            # Interpret as bytes
                            panose_bytes = os2.panose.encode("latin1")[:10]
                            new_panose.bFamilyType = (
                                panose_bytes[0] if len(panose_bytes) > 0 else 0
                            )
                            new_panose.bSerifStyle = (
                                panose_bytes[1] if len(panose_bytes) > 1 else 0
                            )
                            new_panose.bWeight = (
                                panose_bytes[2] if len(panose_bytes) > 2 else 0
                            )
                            new_panose.bProportion = (
                                panose_bytes[3] if len(panose_bytes) > 3 else 0
                            )
                            new_panose.bContrast = (
                                panose_bytes[4] if len(panose_bytes) > 4 else 0
                            )
                            new_panose.bStrokeVariation = (
                                panose_bytes[5] if len(panose_bytes) > 5 else 0
                            )
                            new_panose.bArmStyle = (
                                panose_bytes[6] if len(panose_bytes) > 6 else 0
                            )
                            new_panose.bLetterForm = (
                                panose_bytes[7] if len(panose_bytes) > 7 else 0
                            )
                            new_panose.bMidline = (
                                panose_bytes[8] if len(panose_bytes) > 8 else 0
                            )
                            new_panose.bXHeight = (
                                panose_bytes[9] if len(panose_bytes) > 9 else 0
                            )
                        except Exception:
                            # If decode fails, use all zeros
                            pass

                    os2.panose = new_panose

                    if self.verbose:
                        self.log(
                            "Fixed corrupted panose field (was string, now proper object)"
                        )
        except Exception as e:
            if self.verbose:
                self.log(f"Could not fix panose field: {e}")

        # Version validation
        self.validate_field(
            "version_current",
            "OS/2",
            "version",
            lambda v: (v >= 4, f"Current: {v}, Expected: 4 (minimum required)"),
        )

        # Embedding validation
        self.validate_field(
            "fstype_installable",
            "OS/2",
            "fsType",
            lambda v: (v == 0, f"Current: {v}, Expected: 0 (installable fonts)"),
        )

        # Monospace validation
        self.validate_condition(
            "monospace_consistent",
            lambda: self._validate_monospace_flags(),
            "monospace detection",
        )

        # fsSelection flags validation
        self.validate_condition(
            "fsselection_flags_set",
            lambda: self._validate_fsselection_flags(),
            "fsSelection flags",
        )

        return self.validations

    def _validate_monospace_flags(self) -> Tuple[bool, str]:
        """Helper: validate monospace flags consistency."""
        is_mono = self.is_monospace()
        is_correct = self._is_monospace_flags_correct(is_mono)
        return (is_correct, f"Status: monospace={is_mono}, Compliant: {is_correct}")

    def _validate_fsselection_flags(self) -> Tuple[bool, str]:
        """Helper: validate fsSelection flags."""
        os2 = self.font["OS/2"]
        version = getattr(os2, "version", 0)
        if version < 4:
            return (
                False,
                f"Check: fsSelection flags (FAIL - requires OS/2 v4+, current: {version})",
            )

        fs_selection = getattr(os2, "fsSelection", 0)
        has_use_typo = FS_SELECTION.flags["USE_TYPO_METRICS"].is_set(fs_selection)
        has_wws = FS_SELECTION.flags["WWS"].is_set(fs_selection)
        is_valid = has_use_typo and has_wws
        return (
            is_valid,
            f"Status: USE_TYPO_METRICS={has_use_typo}, WWS={has_wws}, Compliant: {is_valid}",
        )

    def _is_monospace_flags_correct(self, is_mono: bool) -> bool:
        """
        Verify that monospace-related flags are consistent with actual glyph metrics.

        Checks:
            - OS/2.panose.bProportion should be 9 for monospace fonts
            - post.isFixedPitch should be 1 for monospace fonts

        Args:
            is_mono: Whether the font is actually monospace based on glyph analysis

        Returns:
            True if flags correctly reflect the monospace state

        Note:
            For proportional fonts, these flags should NOT be set. This method
            returns False if any discrepancy is found.
        """
        if not is_mono:
            # For proportional fonts, check that flags are cleared
            if "OS/2" in self.font and hasattr(self.font["OS/2"], "panose"):
                if self.font["OS/2"].panose.bProportion == 9:
                    return False
            if "post" in self.font and self.font["post"].isFixedPitch != 0:
                return False
            return True
        else:
            # For monospace fonts, check that flags are set
            if "OS/2" in self.font and hasattr(self.font["OS/2"], "panose"):
                if self.font["OS/2"].panose.bProportion != 9:
                    return False
            if "post" in self.font and self.font["post"].isFixedPitch != 1:
                return False
            return True

    def fix(self) -> bool:
        """Apply all OS/2 fixes based on validation results."""
        if "OS/2" not in self.font:
            return False

        # Check if table is readable - if validation failed due to corruption, skip fixes
        if not self.validations.get("table_readable", {}).get("valid", True):
            # Table is corrupted and cannot be fixed
            return False

        # Verify OS/2 table is accessible before attempting fixes
        try:
            _ = self.font["OS/2"]
        except (TTLibError, AttributeError, IndexError, ValueError):
            # Table became unreadable, skip fixes
            return False

        return any(
            [
                self._fix_version(),
                self._fix_fstype(),
                self._fix_monospace(),
                self._fix_fsselection_flags(),
            ]
        )

    @conditional_fix("version_current")
    def _fix_version(self) -> bool:
        """Upgrade OS/2 table to version 4."""
        os2 = self.font["OS/2"]
        old_version = os2.version

        if old_version >= 4:
            return False

        old_sxHeight = getattr(os2, "sxHeight", None)
        old_sCapHeight = getattr(os2, "sCapHeight", None)
        old_cp1 = getattr(os2, "ulCodePageRange1", None)
        old_cp2 = getattr(os2, "ulCodePageRange2", None)

        os2.version = 4

        # Initialize fields added in version 1 (if upgrading from v0)
        if old_version < 1:
            if not hasattr(os2, "ulCodePageRange1"):
                os2.ulCodePageRange1 = 0
            if not hasattr(os2, "ulCodePageRange2"):
                os2.ulCodePageRange2 = 0

        # Initialize fields added in version 2 (if upgrading from v0 or v1)
        if old_version < 2:
            if not hasattr(os2, "sxHeight"):
                os2.sxHeight = 0
            if not hasattr(os2, "sCapHeight"):
                os2.sCapHeight = 0
            if not hasattr(os2, "usDefaultChar"):
                os2.usDefaultChar = 0
            if not hasattr(os2, "usBreakChar"):
                os2.usBreakChar = 32
            if not hasattr(os2, "usMaxContext"):
                os2.usMaxContext = 0

        # Calculate metrics if missing
        self._calculate_metrics()

        # Recalculate code page ranges if needed
        if os2.ulCodePageRange1 == 0 and os2.ulCodePageRange2 == 0:
            try:
                os2.recalcCodePageRanges(self.font)
            except Exception:
                pass

        # Track changes using ChangeBuilder
        self.track_changes().add("version", old_version, 4).add_if_changed(
            "sxHeight", old_sxHeight or 0, os2.sxHeight
        ).add_if_changed(
            "sCapHeight", old_sCapHeight or 0, os2.sCapHeight
        ).add_if_changed(
            "ulCodePageRange",
            f"({old_cp1 or 0}, {old_cp2 or 0})",
            f"({os2.ulCodePageRange1}, {os2.ulCodePageRange2})",
        ).commit()

        return True

    def _calculate_metrics(self):
        """Calculate sxHeight and sCapHeight from glyphs."""
        os2 = self.font["OS/2"]

        # Calculate sxHeight from 'x' glyph if available
        if os2.sxHeight == 0:
            try:
                glyph_set = self.font.getGlyphSet()
                if "x" in glyph_set:
                    from fontTools.pens.boundsPen import BoundsPen

                    pen = BoundsPen(glyph_set)
                    glyph_set["x"].draw(pen)
                    if pen.bounds:
                        os2.sxHeight = int(round(pen.bounds[3]))
            except Exception:
                pass

        # Calculate sCapHeight from 'H' glyph if available
        if os2.sCapHeight == 0:
            try:
                glyph_set = self.font.getGlyphSet()
                if "H" in glyph_set:
                    from fontTools.pens.boundsPen import BoundsPen

                    pen = BoundsPen(glyph_set)
                    glyph_set["H"].draw(pen)
                    if pen.bounds:
                        os2.sCapHeight = int(round(pen.bounds[3]))
            except Exception:
                pass

    @conditional_fix("fstype_installable")
    def _fix_fstype(self) -> bool:
        """Set fsType to 0 (installable)."""
        os2 = self.font["OS/2"]
        old_fstype = os2.fsType

        if old_fstype == 0:
            return False

        os2.fsType = 0
        self._track_change("fsType", old_fstype, 0, True)
        return True

    @conditional_fix("monospace_consistent")
    def _fix_monospace(self) -> bool:
        """Fix monospace attributes."""
        os2 = self.font["OS/2"]
        is_mono = self.is_monospace()

        old_proportion = (
            getattr(os2.panose, "bProportion", None) if hasattr(os2, "panose") else None
        )
        old_spacing = (
            getattr(os2.panose, "bSpacing", None) if hasattr(os2, "panose") else None
        )
        old_post_fixed = self.font["post"].isFixedPitch if "post" in self.font else None
        old_cff_fixed = None
        old_xavg = os2.xAvgCharWidth

        changed = False

        if is_mono:
            # Set monospace flags
            if hasattr(os2, "panose") and os2.panose.bFamilyType in [2, 3, 4, 5]:
                if os2.panose.bProportion != 9:
                    os2.panose.bProportion = 9
                    changed = True

            if hasattr(os2, "panose") and os2.panose.bFamilyType in [3, 5]:
                if os2.panose.bSpacing != 3:
                    os2.panose.bSpacing = 3
                    changed = True

            if "post" in self.font and self.font["post"].isFixedPitch != 1:
                self.font["post"].isFixedPitch = 1
                changed = True

            # Handle CFF (skip CFF2 for variable fonts)
            if "CFF " in self.font and "CFF2" not in self.font:
                try:
                    cff = self.font["CFF "].cff
                    if hasattr(cff, "topDictIndex") and len(cff.topDictIndex) > 0:
                        top_dict = cff.topDictIndex[0]
                        old_cff_fixed = getattr(
                            top_dict, "isFixedPitch", False
                        )  # Capture BEFORE
                        if not old_cff_fixed:
                            top_dict.isFixedPitch = True
                            changed = True
                except Exception:
                    old_cff_fixed = None
                    pass
        else:
            # Clear monospace flags
            if hasattr(os2, "panose") and os2.panose.bProportion == 9:
                os2.panose.bProportion = 0
                changed = True

            if "post" in self.font and self.font["post"].isFixedPitch != 0:
                self.font["post"].isFixedPitch = 0
                changed = True

            # Clear CFF (skip CFF2 for variable fonts)
            if "CFF " in self.font and "CFF2" not in self.font:
                try:
                    cff = self.font["CFF "].cff
                    if hasattr(cff, "topDictIndex") and len(cff.topDictIndex) > 0:
                        top_dict = cff.topDictIndex[0]
                        old_cff_fixed = getattr(
                            top_dict, "isFixedPitch", False
                        )  # Capture BEFORE
                        if old_cff_fixed:
                            top_dict.isFixedPitch = False
                            changed = True
                except Exception:
                    old_cff_fixed = None
                    pass

        # Recalculate xAvgCharWidth
        if "hmtx" in self.font:
            try:
                os2.recalcAvgCharWidth(self.font)
                if os2.xAvgCharWidth != old_xavg:
                    changed = True
            except (AttributeError, KeyError, TypeError, struct.error):
                # Font has unusual metrics table structure, skip recalculation
                if self.verbose:
                    self.log(
                        "Could not recalculate xAvgCharWidth (unusual metrics table)"
                    )
                pass
            except Exception as e:
                # Catch struct.error and other unexpected errors
                if self.verbose:
                    self.log(f"Could not recalculate xAvgCharWidth: {e}")
                pass

        if changed:
            # Track changes using ChangeBuilder
            builder = self.track_changes()
            builder.add_info("is_monospace", is_mono)

            if old_proportion is not None:
                builder.add_if_changed(
                    "bProportion", old_proportion, os2.panose.bProportion
                )
            if old_spacing is not None:
                builder.add_if_changed("bSpacing", old_spacing, os2.panose.bSpacing)
            if old_post_fixed is not None:
                builder.add_if_changed(
                    "post.isFixedPitch", old_post_fixed, self.font["post"].isFixedPitch
                )
            if "CFF " in self.font:
                try:
                    cff = self.font["CFF "].cff
                    new_cff = getattr(cff.topDictIndex[0], "isFixedPitch", False)
                    if old_cff_fixed is not None:
                        builder.add_if_changed(
                            "CFF.isFixedPitch", old_cff_fixed, new_cff
                        )
                except Exception:
                    pass
            builder.add_if_changed("xAvgCharWidth", old_xavg, os2.xAvgCharWidth)
            builder.commit()

        return changed

    @conditional_fix("fsselection_flags_set")
    def _fix_fsselection_flags(self) -> bool:
        """Set USE_TYPO_METRICS and WWS flags."""
        os2 = self.font["OS/2"]

        if os2.version < 4:
            return False

        original_fs = os2.fsSelection
        os2.fsSelection = FS_SELECTION.flags["USE_TYPO_METRICS"].set(os2.fsSelection)
        os2.fsSelection = FS_SELECTION.flags["WWS"].set(os2.fsSelection)

        if os2.fsSelection != original_fs:
            self._track_bitfield_change(
                "fsSelection", original_fs, os2.fsSelection, FS_SELECTION
            )
            return True

        return False
