"""
Font corruption detection and handling.

This module provides the CorruptionDetector class for detecting font corruption,
validating glyph bounds, and handling quarantine operations.
"""

import re
import struct
import shutil
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Any

try:
    from fontTools.ttLib import TTFont, TTLibError
except ImportError:
    TTFont = None  # Type hint fallback
    TTLibError = Exception

from .constants import SIGNED_16BIT_MIN, SIGNED_16BIT_MAX
from .data_models import FontFixResult


class CorruptionDetector:
    """
    Detects and handles font corruption.

    Provides methods for:
    - Validating glyph bounding boxes
    - Detecting variable fonts
    - Identifying corruption-related exceptions
    - Formatting error messages
    - Quarantining corrupted fonts
    """

    def __init__(self, verbose: bool = False, quarantine_enabled: bool = True):
        """
        Initialize corruption detector.

        Args:
            verbose: Enable verbose logging
            quarantine_enabled: Enable automatic quarantine of corrupted fonts
        """
        self.verbose = verbose
        self.quarantine_enabled = quarantine_enabled

    def validate_glyph_bounds(self, font: TTFont) -> list[str]:
        """
        Check if any glyph has bounding box coordinates outside signed 16-bit range.

        Args:
            font: The TTFont object to check

        Returns:
            List of glyph names with out-of-range bounds, empty if all valid
        """
        problematic_glyphs = []
        if "glyf" not in font:
            return problematic_glyphs

        try:
            glyf = font["glyf"]
            for glyph_name in font.getGlyphOrder():
                if glyph_name not in glyf:
                    continue

                glyph = glyf[glyph_name]
                # Check if glyph has bounding box data
                if hasattr(glyph, "xMin") and hasattr(glyph, "xMax"):
                    # Check each coordinate
                    if (
                        glyph.xMin < SIGNED_16BIT_MIN
                        or glyph.xMin > SIGNED_16BIT_MAX
                        or glyph.xMax < SIGNED_16BIT_MIN
                        or glyph.xMax > SIGNED_16BIT_MAX
                    ):
                        problematic_glyphs.append(glyph_name)
                        continue

                if hasattr(glyph, "yMin") and hasattr(glyph, "yMax"):
                    if (
                        glyph.yMin < SIGNED_16BIT_MIN
                        or glyph.yMin > SIGNED_16BIT_MAX
                        or glyph.yMax < SIGNED_16BIT_MIN
                        or glyph.yMax > SIGNED_16BIT_MAX
                    ):
                        if glyph_name not in problematic_glyphs:
                            problematic_glyphs.append(glyph_name)

        except Exception as e:
            # If validation fails, log but don't block processing
            if self.verbose:
                self.log(f"Error validating glyph bounds: {e}")

        return problematic_glyphs

    @staticmethod
    def is_variable_font(font: Optional[Any]) -> bool:
        """
        Detect if a font is a variable font by checking for variable font tables.

        Variable font tables:
        - fvar: Required for variable fonts (font variations)
        - gvar: Glyph variations (TrueType outlines)
        - cvar: CVT variations (TrueType hinting)
        - avar: Axis variations (axis mapping)
        - HVAR: Horizontal metrics variations
        - VVAR: Vertical metrics variations
        - MVAR: Metrics variations

        Note: STAT table is not variable-specific - newer static fonts may contain it.

        Args:
            font: TTFont object or None

        Returns:
            True if font is variable (has fvar table, or other var tables indicating variable font), False otherwise
        """
        if font is None:
            return False
        try:
            # fvar is the definitive indicator of a variable font
            if "fvar" in font:
                return True

            # Other variable font tables (typically exist alongside fvar)
            # If they exist without fvar, the font is problematic but still variable-like
            var_tables = ["gvar", "cvar", "avar", "HVAR", "VVAR", "MVAR"]
            return any(table in font for table in var_tables)
        except Exception:
            return False

    def is_corruption_error(
        self,
        exc_type: type,
        error_str: str,
        exc: Optional[Exception] = None,
        context: str = "",
        font: Optional[Any] = None,
    ) -> bool:
        """
        Determine if exception type/message indicates corruption.

        Enhanced to inspect tracebacks and consider context (especially save operations
        for variable fonts).

        Args:
            exc_type: Exception type
            error_str: Error message string
            exc: Optional exception object for traceback inspection
            context: Context string (e.g., "while saving", "during font loading")
            font: Optional TTFont object to check if variable font

        Returns:
            True if exception indicates font corruption, False otherwise
        """
        corruption_patterns = {
            AssertionError: ["gvar", "TupleVariation", "table", "glyph", "font"],
            TTLibError: ["*"],  # All TTLibError = corruption
            IndexError: ["table", "glyph"],
            ValueError: ["table", "struct", "format h", "xmax", "xmin", "ymax", "ymin"],
            struct.error: ["*"],
            AttributeError: ["table", "font", "glyph", "OS/2", "cmap"],
        }

        patterns = corruption_patterns.get(exc_type, [])
        if "*" in patterns:
            return True

        # Check error message for keywords
        error_lower = error_str.lower()
        if any(keyword in error_lower for keyword in patterns):
            return True

        # If error message is generic/empty, inspect traceback
        if exc is not None and (
            not error_str or error_str == "No error message provided"
        ):
            try:
                tb_str = "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                )
                tb_lower = tb_str.lower()

                # Check traceback for font-related keywords
                font_keywords = [
                    "gvar",
                    "fvar",
                    "tuplevariation",
                    "table",
                    "glyph",
                    "font",
                    "ttfont",
                    "ttlib",
                    "cmap",
                    "os/2",
                    "hmtx",
                    "vmtx",
                ]
                if any(keyword in tb_lower for keyword in font_keywords):
                    return True
            except Exception:
                pass

        # Special handling for save-time errors
        if "saving" in context.lower() or "save" in context.lower():
            # For variable fonts, any error during save is likely corruption
            if font is not None and self.is_variable_font(font):
                # Variable fonts are more sensitive - treat save errors as corruption
                if exc_type in (IndexError, AssertionError, AttributeError, ValueError):
                    return True

            # For any font, if error occurs during save and matches suspicious types
            # and traceback shows font table operations, treat as corruption
            if exc is not None and exc_type in (
                IndexError,
                AssertionError,
                AttributeError,
            ):
                try:
                    tb_str = "".join(
                        traceback.format_exception(type(exc), exc, exc.__traceback__)
                    )
                    tb_lower = tb_str.lower()
                    # Check if traceback shows font table operations
                    if any(
                        keyword in tb_lower
                        for keyword in [
                            "ttfont",
                            "ttlib",
                            "table",
                            "compile",
                            "getTableData",
                        ]
                    ):
                        return True
                except Exception:
                    pass

        return False

    @staticmethod
    def format_bounds_overflow_error(error_str: str) -> Optional[str]:
        """
        Format bounding box overflow errors with clearer explanation.

        Args:
            error_str: The original error message

        Returns:
            Formatted error message if this is a bounds overflow error, None otherwise
        """
        error_lower = error_str.lower()
        # Check if this is a bounding box overflow error
        if "format h" in error_lower and any(
            coord in error_lower for coord in ["xmax", "xmin", "ymax", "ymin"]
        ):
            # Try to extract the value and coordinate name
            # Pattern: "Value 33416 does not fit in format h for xMax"
            match = re.search(
                r"Value\s+(\d+)\s+does\s+not\s+fit\s+in\s+format\s+h\s+for\s+(\w+)",
                error_str,
                re.IGNORECASE,
            )
            if match:
                value = match.group(1)
                coord = match.group(2)
                return (
                    f"Glyph bounding box overflow (requires glyph coordinate modification to fix): "
                    f"Value {value} does not fit in signed 16-bit range for {coord}. "
                    f"This font needs glyph-level coordinate adjustment, which is beyond this script's scope."
                )
            else:
                # Fallback if regex doesn't match
                return (
                    f"Glyph bounding box overflow (requires glyph coordinate modification to fix): {error_str}. "
                    f"This font needs glyph-level coordinate adjustment, which is beyond this script's scope."
                )
        return None

    def quarantine_font(
        self, font_path: Path, quarantine_dir: Optional[Path], input_root: Path
    ) -> Optional[Path]:
        """
        Move a corrupted font to quarantine directory.

        Args:
            font_path: Path to the font file to quarantine
            quarantine_dir: Root quarantine directory
            input_root: Root of input directory (for preserving relative paths)

        Returns:
            Path to quarantined file if successful, None otherwise
        """
        # Debug logging
        if self.verbose:
            self.log(
                f"Quarantine check: enabled={self.quarantine_enabled}, dir={quarantine_dir}, input_root={input_root}"
            )

        if not self.quarantine_enabled:
            if self.verbose:
                self.log(f"Quarantine disabled, skipping {font_path}")
            return None

        if quarantine_dir is None:
            if self.verbose:
                self.log(f"Quarantine directory is None, cannot quarantine {font_path}")
            return None

        try:
            # Calculate relative path from input root to preserve directory structure
            try:
                relative_path = font_path.relative_to(input_root)
                if self.verbose:
                    self.log(f"Calculated relative path: {relative_path}")
            except ValueError:
                # Font is not under input root, use just the filename
                relative_path = Path(font_path.name)
                if self.verbose:
                    self.log(
                        f"Font not under input_root, using filename: {relative_path}"
                    )

            # Build quarantine path
            quarantine_path = quarantine_dir / relative_path

            # Handle path collisions using tilde format
            if quarantine_path.exists():
                stem = quarantine_path.stem
                suffix = quarantine_path.suffix
                counter = 1
                while quarantine_path.exists():
                    quarantine_path = (
                        quarantine_path.parent / f"{stem}~{counter:03d}{suffix}"
                    )
                    counter += 1
                if self.verbose:
                    self.log(f"Quarantine path collision, using: {quarantine_path}")

            # Create parent directories
            quarantine_path.parent.mkdir(parents=True, exist_ok=True)
            if self.verbose:
                self.log(f"Created quarantine directory: {quarantine_path.parent}")

            # Move file to quarantine
            shutil.move(str(font_path), str(quarantine_path))

            if self.verbose:
                self.log(f"Successfully quarantined {font_path} to {quarantine_path}")

            return quarantine_path
        except Exception as e:
            if self.verbose:
                self.log(f"Failed to quarantine {font_path}: {e}")
                self.log(f"Quarantine error traceback: {traceback.format_exc()}")
            return None

    @contextmanager
    def corruption_handler(
        self,
        font_path: Path,
        result: FontFixResult,
        context: str = "",
        quarantine_dir: Optional[Path] = None,
        input_root: Optional[Path] = None,
        font: Optional[Any] = None,
    ):
        """
        Context manager for detecting and handling font corruption.

        If a corruption-related exception occurs:
        - Adds formatted error to result
        - Quarantines file if enabled
        - SWALLOWS the exception (does not re-raise)
        - Sets result.success = False

        If a non-corruption exception occurs:
        - Re-raises the exception for caller to handle

        Args:
            font_path: Path to the font file
            result: FontFixResult to update
            context: Context string describing where error occurred
            quarantine_dir: Quarantine directory path
            input_root: Root input directory for relative path calculation
            font: Optional TTFont object for variable font detection

        Usage:
            with detector.corruption_handler(font_path, result, "during saving", ..., font=font):
                font.save(output_path)
                result.success = True  # Only reached if no exception
                result.was_modified = True

            # Check result.success after block - will be False if corrupted
        """
        try:
            yield
        except Exception as e:
            error_str = str(e) if str(e) else "No error message provided"

            # Check if this is corruption (pass exception object and context for enhanced detection)
            is_corrupt = self.is_corruption_error(
                type(e), error_str, exc=e, context=context, font=font
            )

            if is_corrupt:
                # Check if this is a bounding box overflow error that needs special formatting
                bounds_error = CorruptionDetector.format_bounds_overflow_error(
                    error_str
                )
                if bounds_error:
                    # Use the formatted bounds error message
                    context_msg = f" {context}" if context else ""
                    error_msg = f"Font corruption detected{context_msg}: {bounds_error}"
                else:
                    # Build standard error message
                    context_msg = f" {context}" if context else ""
                    error_msg = f"Font corruption detected{context_msg}: {type(e).__name__}: {error_str}"

                # Quarantine if enabled
                if self.quarantine_enabled and input_root and quarantine_dir:
                    qpath = self.quarantine_font(font_path, quarantine_dir, input_root)
                    if qpath:
                        result.quarantined = True
                        result.quarantine_path = str(qpath)
                        error_msg += f" (quarantined to {qpath})"
                    elif self.verbose:
                        # Log quarantine failure for debugging
                        self.log(
                            f"Warning: Failed to quarantine {font_path} (quarantine_dir={quarantine_dir}, input_root={input_root})"
                        )

                result.add_error(error_msg, include_traceback=self.verbose)
                result.success = False

                # Don't re-raise - corruption is handled
            else:
                # Not corruption - re-raise for caller to handle
                raise

    def log(self, message: str):
        """Print verbose messages."""
        if self.verbose:
            # Import here to avoid circular dependency with main
            try:
                import FontCore.core_console_styles as cs

                console = cs.get_console()
                cs.StatusIndicator("info").add_message(message).emit(console)
            except ImportError:
                # Fallback if FontCore not available
                print(f"[INFO] {message}")
