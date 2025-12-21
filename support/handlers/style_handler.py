"""
Style consistency handler.

This handler ensures consistency across post, hhea, OS/2, and head tables
for font style attributes including italic angle, caret slope, and style flags.
"""

import math
from typing import Dict, Any, Tuple, Any as AnyType

try:
    from fontTools.ttLib import TTFont
except ImportError:
    TTFont = None  # Type hint fallback

from .base_handler import TableHandler
from ..data_models import HANDLER_STYLE
from ..style_analyzer import FontStyleAnalyzer
from ..bitfield import FS_SELECTION, MAC_STYLE
from ..utilities import clamp_signed_16bit
from ..constants import SIGNED_16BIT_MIN, SIGNED_16BIT_MAX
from ..decorators import conditional_fix


class StyleConsistencyHandler(TableHandler):
    """
    Ensures consistency across post, hhea, OS/2, and head tables for style.

    Responsibilities:
    - post.italicAngle matches calculated angle
    - hhea.caretSlope matches italic angle
    - OS/2.fsSelection matches style (italic, oblique, bold, regular)
    - head.macStyle matches style (bold, italic)
    """

    def __init__(self, font: TTFont, verbose: bool = False):
        super().__init__(font, verbose)
        self.style_analyzer = FontStyleAnalyzer(font)

    def get_table_name(self) -> str:
        return HANDLER_STYLE.full_name

    def validate(self) -> Dict[str, Dict[str, Any]]:
        """Validate style consistency across tables."""
        # Validate post.italicAngle
        self.validate_field(
            "italic_angle_correct",
            "post",
            "italicAngle",
            lambda v: (
                abs(v - self.style_analyzer.italic_angle) < 0.1,
                f"Current: {v}°, Expected: {self.style_analyzer.italic_angle}°",
            ),
        )

        # Validate hhea.caretSlope
        self.validate_condition(
            "caret_slope_correct", lambda: self._validate_caret_slope(), "caret slope"
        )

        # Validate OS/2.fsSelection
        self.validate_condition(
            "fsselection_style_match",
            lambda: self._validate_fsselection_style(),
            "fsSelection style flags",
        )

        # Validate head.macStyle
        self.validate_condition(
            "macstyle_correct", lambda: self._validate_macstyle(), "macStyle flags"
        )

        return self.validations

    def _validate_caret_slope(self) -> Tuple[bool, str]:
        """Helper: validate hhea caret slope."""
        if "hhea" not in self.font or "head" not in self.font:
            return (True, "hhea or head table missing")

        hhea = self.font["hhea"]
        head = self.font["head"]
        calculated = self.style_analyzer.italic_angle

        if calculated == 0:
            expected_rise = 1
            expected_run = 0
        else:
            upm = head.unitsPerEm
            expected_rise = upm
            expected_run = round(math.tan(math.radians(-1 * calculated)) * upm)

        caret_correct = (
            hhea.caretSlopeRise == expected_rise and hhea.caretSlopeRun == expected_run
        )
        return (
            caret_correct,
            f"Current: rise={hhea.caretSlopeRise}, run={hhea.caretSlopeRun}; "
            f"Expected: rise={expected_rise}, run={expected_run}",
        )

    def _validate_fsselection_style(self) -> Tuple[bool, str]:
        """Helper: validate fsSelection style flags."""
        if "OS/2" not in self.font:
            return (True, "OS/2 table missing")

        os2 = self.font["OS/2"]
        fs_italic = FS_SELECTION.flags["ITALIC"].is_set(os2.fsSelection)
        fs_oblique = (
            FS_SELECTION.flags["OBLIQUE"].is_set(os2.fsSelection)
            if os2.version >= 4
            else False
        )
        fs_bold = FS_SELECTION.flags["BOLD"].is_set(os2.fsSelection)

        style_matches = (
            fs_italic == self.style_analyzer.is_italic
            and fs_oblique == self.style_analyzer.is_oblique
            and fs_bold == self.style_analyzer.is_bold
        )

        return (
            style_matches,
            f"Status: Italic={fs_italic} (expected {self.style_analyzer.is_italic}), "
            f"Oblique={fs_oblique} (expected {self.style_analyzer.is_oblique}), "
            f"Bold={fs_bold} (expected {self.style_analyzer.is_bold}), "
            f"Compliant: {style_matches}",
        )

    def _validate_macstyle(self) -> Tuple[bool, str]:
        """Helper: validate macStyle flags."""
        if "head" not in self.font:
            return (True, "head table missing")

        head = self.font["head"]
        mac_bold = MAC_STYLE.flags["BOLD"].is_set(head.macStyle)
        mac_italic = MAC_STYLE.flags["ITALIC"].is_set(head.macStyle)

        mac_correct = mac_bold == self.style_analyzer.is_bold and mac_italic == (
            self.style_analyzer.is_italic or self.style_analyzer.is_oblique
        )

        return (
            mac_correct,
            f"Status: bold={mac_bold} (expected {self.style_analyzer.is_bold}), "
            f"italic={mac_italic} (expected {self.style_analyzer.is_italic or self.style_analyzer.is_oblique}), "
            f"Compliant: {mac_correct}",
        )

    def fix(self) -> bool:
        """Fix style consistency issues."""
        return any(
            [
                self._fix_italic_angle(),
                self._fix_caret_slope(),
                self._fix_style_flags(),
            ]
        )

    @conditional_fix("italic_angle_correct")
    def _fix_italic_angle(self) -> bool:
        """Fix post.italicAngle."""
        if "post" not in self.font:
            return False

        post = self.font["post"]
        calculated = self.style_analyzer.italic_angle
        old_italic_angle = post.italicAngle

        if abs(calculated - post.italicAngle) > 0.1:
            post.italicAngle = calculated
            self._track_change(
                "italic_angle", f"{old_italic_angle} deg", f"{calculated} deg", True
            )
            return True

        return False

    @conditional_fix("caret_slope_correct")
    def _fix_caret_slope(self) -> bool:
        """Fix hhea.caretSlope."""
        if "hhea" not in self.font or "head" not in self.font:
            return False

        hhea = self.font["hhea"]
        head = self.font["head"]
        calculated = self.style_analyzer.italic_angle

        original_rise = hhea.caretSlopeRise
        original_run = hhea.caretSlopeRun

        if calculated == 0:
            hhea.caretSlopeRise = 1
            hhea.caretSlopeRun = 0
        else:
            upm = head.unitsPerEm
            hhea.caretSlopeRise = upm
            # Calculate run but clamp to valid range for signed 16-bit integer
            calculated_run = round(math.tan(math.radians(-1 * calculated)) * upm)
            original_calculated = calculated_run

            # Clamp to signed 16-bit range
            hhea.caretSlopeRun = clamp_signed_16bit(calculated_run)

            if hhea.caretSlopeRun != original_calculated and self.verbose:
                self.log(
                    f"Clamped caretSlopeRun from {original_calculated} to {hhea.caretSlopeRun} "
                    f"(signed 16-bit range: {SIGNED_16BIT_MIN} to {SIGNED_16BIT_MAX})"
                )

        if hhea.caretSlopeRise != original_rise or hhea.caretSlopeRun != original_run:
            self._track_change(
                "caret_slope_rise",
                original_rise if original_rise is not None else "N/A",
                hhea.caretSlopeRise,
                original_rise is not None and hhea.caretSlopeRise != original_rise,
            )
            self._track_change(
                "caret_slope_run",
                original_run if original_run is not None else "N/A",
                hhea.caretSlopeRun,
                original_run is not None and hhea.caretSlopeRun != original_run,
            )
            return True

        return False

    @conditional_fix("fsselection_style_match", "macstyle_correct")
    def _fix_style_flags(self) -> bool:
        """Fix OS/2.fsSelection and head.macStyle."""
        if "OS/2" not in self.font or "head" not in self.font:
            return False

        os2 = self.font["OS/2"]
        head = self.font["head"]

        original_fs = os2.fsSelection
        original_mac = head.macStyle

        # Apply fixes
        self._apply_fsselection_style(os2)
        self._apply_macstyle(head)

        # Track changes
        any_changed = self._track_style_flag_changes(
            original_fs, os2.fsSelection, original_mac, head.macStyle
        )

        return any_changed

    def _apply_fsselection_style(self, os2: AnyType) -> None:
        """Set fsSelection bits based on style analysis."""
        # Clear style bits
        os2.fsSelection = FS_SELECTION.flags["ITALIC"].clear(os2.fsSelection)
        os2.fsSelection = FS_SELECTION.flags["BOLD"].clear(os2.fsSelection)
        os2.fsSelection = FS_SELECTION.flags["REGULAR"].clear(os2.fsSelection)
        if os2.version >= 4:
            os2.fsSelection = FS_SELECTION.flags["OBLIQUE"].clear(os2.fsSelection)

        # Set appropriate bits
        if self.style_analyzer.is_italic:
            os2.fsSelection = FS_SELECTION.flags["ITALIC"].set(os2.fsSelection)

        if self.style_analyzer.is_oblique:
            if os2.version >= 4:
                os2.fsSelection = FS_SELECTION.flags["OBLIQUE"].set(os2.fsSelection)
            else:
                # Verbose warning: oblique bit requires OS/2 v4+
                if self.verbose:
                    self.log(
                        f"Font is oblique but OS/2 version {os2.version} < 4, cannot set oblique bit"
                    )

        if self.style_analyzer.is_bold:
            os2.fsSelection = FS_SELECTION.flags["BOLD"].set(os2.fsSelection)

        if (
            not self.style_analyzer.is_bold
            and not self.style_analyzer.is_italic
            and not self.style_analyzer.is_oblique
        ):
            os2.fsSelection = FS_SELECTION.flags["REGULAR"].set(os2.fsSelection)

    def _apply_macstyle(self, head: AnyType) -> None:
        """Set macStyle bits based on style analysis."""
        head.macStyle = 0

        if self.style_analyzer.is_bold:
            head.macStyle = MAC_STYLE.flags["BOLD"].set(head.macStyle)

        if self.style_analyzer.is_italic or self.style_analyzer.is_oblique:
            head.macStyle = MAC_STYLE.flags["ITALIC"].set(head.macStyle)

    def _track_style_flag_changes(
        self, old_fs: int, new_fs: int, old_mac: int, new_mac: int
    ) -> bool:
        """Track all style flag changes with detailed deltas."""
        any_changed = False

        if new_fs != old_fs:
            self._track_bitfield_change("fsSelection", old_fs, new_fs, FS_SELECTION)
            any_changed = True

        if new_mac != old_mac:
            self._track_bitfield_change("macStyle", old_mac, new_mac, MAC_STYLE)
            any_changed = True

        if any_changed:
            # Track info changes
            os2 = self.font["OS/2"]
            self._track_info_changes(
                [
                    ("is_italic", self.style_analyzer.is_italic),
                    ("is_oblique", self.style_analyzer.is_oblique),
                    ("is_bold", self.style_analyzer.is_bold),
                    (
                        "is_regular",
                        FS_SELECTION.flags["REGULAR"].is_set(os2.fsSelection),
                    ),
                ]
            )

        return any_changed
