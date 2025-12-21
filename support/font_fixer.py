"""
Font fixer orchestrator.

This module provides the FontFixer class that orchestrates font validation
and correction using table handlers.
"""

from pathlib import Path
from typing import Optional, Dict

try:
    from fontTools.ttLib import TTFont, TTLibError
except ImportError:
    TTFont = None  # Type hint fallback
    TTLibError = Exception

from .data_models import FontFixResult
from .corruption_detection import CorruptionDetector
from .handlers import (
    OS2TableHandler,
    StyleConsistencyHandler,
    GlyphHandler,
    KernHandler,
    NameTableHandler,
)

try:
    import FontCore.core_console_styles as cs

    console = cs.get_console()
except ImportError:
    # Fallback if FontCore not available
    console = None


class FontFixer:
    """Orchestrates font validation and correction using table handlers."""

    def __init__(
        self,
        verbose: bool = False,
        enabled_handlers: Optional[list] = None,
        quarantine_enabled: bool = True,
    ):
        """
        Initialize font fixer.

        Args:
            verbose: Enable verbose logging
            enabled_handlers: List of handler full names to run, None means all
            quarantine_enabled: Enable automatic quarantine of corrupted fonts
        """
        self.verbose = verbose
        # enabled_handlers is a list of handler names (HANDLER_OS2.full_name, etc.) to run, None means all
        self.enabled_handlers = enabled_handlers
        self.quarantine_enabled = quarantine_enabled
        self.corruption_detector = CorruptionDetector(verbose, quarantine_enabled)

    def log(self, message: str):
        """Print verbose messages."""
        if self.verbose:
            try:
                cs.StatusIndicator("info").add_message(message).emit(console)
            except (NameError, ImportError):
                # Fallback if FontCore not available
                print(f"[INFO] {message}")

    def _build_fix_details_from_changes(self, changes: dict) -> list:
        """Build detailed fix information from changes dictionary."""
        details_parts = []

        for prop_name, info in changes.items():
            old_val = info.get("old")
            new_val = info.get("new")
            changed = info.get("changed", False)
            info_only = info.get("info_only", False)

            # Skip info_only properties in non-verbose mode
            if info_only and not self.verbose:
                continue

            # Skip unchanged properties in non-verbose mode
            if not changed and not self.verbose:
                continue

            if changed:
                # Check if new_val already contains delta information in brackets
                if "[" in str(new_val) and "]" in str(new_val):
                    # Delta information already embedded, show as-is
                    details_parts.append(f"- {prop_name}: {old_val} -> {new_val}")
                else:
                    # Standard format
                    details_parts.append(f"- {prop_name}: {old_val} -> {new_val}")
            else:
                # Unchanged property, show in verbose mode with checkmark
                details_parts.append(
                    f"- {prop_name}: {new_val} [success]✓ OK[/success]"
                )

        return details_parts

    def log_handler_result(
        self, handler_name: str, changed: bool, changes: Dict = None
    ):
        """Log the result of a handler execution."""
        if not changed:
            return  # Don't show unchanged handlers here - will show in consolidated message

        try:
            indicator = cs.StatusIndicator("updated", dry_run=False).add_message(
                handler_name
            )

            # Add each detail line as an indented item
            if changes:
                details = self._build_fix_details_from_changes(changes)
                for detail_line in details:
                    indicator.add_item(detail_line)

            indicator.emit(console)
        except (NameError, ImportError):
            # Fallback if FontCore not available
            if changed:
                print(f"[UPDATED] {handler_name}")

    def fix_font(
        self,
        font_path: Path,
        output_dir: Optional[Path] = None,
        validate_only: bool = False,
        quarantine_dir: Optional[Path] = None,
        input_root: Optional[Path] = None,
    ) -> FontFixResult:
        """
        Apply all fixes to a single font file.

        Returns FontFixResult with status and details.

        Handler Execution Order (CRITICAL - DO NOT CHANGE):
        ===================================================

        The handlers MUST execute in this specific order due to dependencies:

        1. OS2TableHandler (FIRST)
           - Upgrades OS/2 table to version 4
           - Enables OS/2 v4-specific features (USE_TYPO_METRICS, WWS flags, OBLIQUE bit)
           - Must run first because StyleConsistencyHandler depends on OS/2 v4 being current

        2. StyleConsistencyHandler (SECOND - depends on #1)
           - Validates and fixes style consistency across post, hhea, OS/2, and head tables
           - Uses OS/2 v4-specific flags (OBLIQUE bit requires v4+)
           - Will fail validation if OS/2 version < 4, so OS2TableHandler must upgrade first

        3. GlyphHandler (Independent)
           - Fixes .notdef glyph structure and nbsp (U+00A0) presence/width
           - No dependencies on other handlers

        4. KernHandler (Independent)
           - Removes legacy kern table when GPOS exists
           - No dependencies on other handlers

        5. NameTableHandler (LAST - independent)
           - Cleans up name table (Windows English only, removes problematic nameIDs)
           - Runs last as it's a cleanup operation that doesn't affect other handlers

        If the order is changed:
        - StyleConsistencyHandler may fail if OS/2 is still v0-v3
        - Style flags may be incorrectly set if OS/2 version upgrade happens after style fixes
        - No other handlers have dependencies, but this order is tested and proven stable
        """
        result = FontFixResult(file=str(font_path))

        font = None
        try:
            # Open font once
            font = TTFont(font_path, recalcBBoxes=True, recalcTimestamp=False)
            original_flavor = font.flavor  # Store original flavor

            # Validate glyph bounding boxes are within signed 16-bit range
            # This catches issues early before processing handlers
            if "glyf" in font:
                problematic_glyphs = self.corruption_detector.validate_glyph_bounds(
                    font
                )
                if problematic_glyphs:
                    # Close font and reopen without recalcBBoxes to preserve original bounds
                    font.close()
                    if self.verbose:
                        self.log(
                            f"Detected {len(problematic_glyphs)} glyph(s) with out-of-range bounds, "
                            f"reopening without recalcBBoxes: {', '.join(problematic_glyphs[:5])}"
                            + (
                                f" and {len(problematic_glyphs) - 5} more"
                                if len(problematic_glyphs) > 5
                                else ""
                            )
                        )
                    font = TTFont(font_path, recalcBBoxes=False, recalcTimestamp=False)
                    font.flavor = original_flavor

            # Create all handlers in dependency order
            # CRITICAL: This order must be preserved
            # 1. OS2 must run first (upgrades table version, enables v4 features)
            # 2. Style depends on OS/2 version being current
            # 3. Glyph, Kern, Name are independent but run after foundation is solid
            handlers = [
                OS2TableHandler(font, self.verbose),
                StyleConsistencyHandler(font, self.verbose),  # Depends on OS/2 v4
                GlyphHandler(font, self.verbose),
                KernHandler(font, self.verbose),
                NameTableHandler(font, self.verbose),
            ]

            # Filter handlers if specific ones are enabled
            if self.enabled_handlers:
                handlers = [
                    h for h in handlers if h.get_table_name() in self.enabled_handlers
                ]

            any_changed = False

            # Run each handler
            for handler in handlers:
                try:
                    handler_name = handler.get_table_name()
                    result.handlers_run.append(handler_name)

                    # Validate
                    handler_validations = handler.validate()
                    result.validations[handler_name] = handler_validations

                    # Fix (skip if validate_only)
                    if validate_only:
                        handler_changed = False
                    else:
                        handler_changed = handler.fix()
                    if handler_changed:
                        any_changed = True
                        handler_changes = handler.get_changes()
                        result.changes[handler_name] = handler_changes
                        result.mark_handler_run(handler_name, True)

                        # Log handler result
                        self.log_handler_result(handler_name, True, handler_changes)
                    else:
                        result.mark_handler_run(handler_name, False)

                except Exception as e:
                    handler_name = handler.get_table_name()
                    result.add_exception(
                        e,
                        f"Handler '{handler_name}' failed",
                        include_traceback=self.verbose,
                    )

            # Check if any handler detected fatal corruption during validation
            has_fatal_corruption = False
            for handler_name, validations in result.validations.items():
                for check_name, validation in validations.items():
                    if check_name in ["table_readable"] and not validation.get(
                        "valid", True
                    ):
                        has_fatal_corruption = True
                        break
                if has_fatal_corruption:
                    break

            if has_fatal_corruption:
                # Quarantine immediately without attempting save
                result.add_error("Font has corrupted tables detected during validation")
                result.success = False
                result.was_modified = False

                if input_root and quarantine_dir:
                    quarantine_path = self.corruption_detector.quarantine_font(
                        font_path, quarantine_dir, input_root
                    )
                    if quarantine_path:
                        result.quarantined = True
                        result.quarantine_path = str(quarantine_path)

                # Skip attempting to save this font
                any_changed = False

            # Only save if fixes were actually applied
            if any_changed:
                # Determine output path
                if output_dir:
                    output_path = output_dir / font_path.name
                    # Handle path collisions using tilde format
                    if output_path.exists() and output_path != font_path:
                        stem = output_path.stem
                        suffix = output_path.suffix
                        counter = 1
                        while output_path.exists():
                            output_path = output_dir / f"{stem}~{counter:03d}{suffix}"
                            counter += 1
                    # Create parent directories if needed
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    output_path = font_path

                # Restore flavor before saving
                font.flavor = original_flavor

                # Detect if this is a variable font for enhanced error detection
                is_variable = self.corruption_detector.is_variable_font(font)
                if is_variable and self.verbose:
                    self.log(
                        "Detected variable font, using enhanced corruption detection"
                    )

                # Attempt to save with improved error handling
                with self.corruption_detector.corruption_handler(
                    font_path,
                    result,
                    "while saving",
                    quarantine_dir,
                    input_root,
                    font=font,
                ):
                    font.save(str(output_path))
                    result.success = True
                    result.was_modified = True
                    result.output_path = str(output_path)
            else:
                result.success = True
                result.was_modified = False

        except TTLibError as e:
            # Font loading or table access error
            error_str = str(e) if str(e) else "No error message provided"
            context = "during font loading"

            if self.corruption_detector.is_corruption_error(
                TTLibError, error_str, exc=e, context=context, font=font
            ):
                # Handle corruption directly
                if self.quarantine_enabled and input_root and quarantine_dir:
                    qpath = self.corruption_detector.quarantine_font(
                        font_path, quarantine_dir, input_root
                    )
                    if qpath:
                        result.quarantined = True
                        result.quarantine_path = str(qpath)
                    elif self.verbose:
                        self.log(
                            f"Warning: Failed to quarantine {font_path} (TTLibError)"
                        )
                result.add_error(
                    f"Font corruption detected {context}: {type(e).__name__}: {error_str}",
                    include_traceback=self.verbose,
                )
            else:
                result.add_error(
                    f"Font table error {context}: {type(e).__name__}: {error_str}",
                    include_traceback=self.verbose,
                )
            result.success = False
        except Exception as e:
            # Build error message with context
            error_type = type(e).__name__
            error_str = str(e) if str(e) else "No error message provided"

            # Determine context - where did the error occur?
            try:
                if "any_changed" in locals() and any_changed:
                    if "output_path" in locals():
                        context = f"while saving to {output_path.name}"
                    else:
                        context = "while saving font"
                elif font is not None:
                    context = "during font processing"
                else:
                    context = "during font loading"
            except (NameError, KeyError):
                # Fallback if variable checks fail
                context = "during font processing"

            # Check if corruption-related (pass exception object and context for enhanced detection)
            if self.corruption_detector.is_corruption_error(
                type(e), error_str, exc=e, context=context, font=font
            ):
                # Handle corruption directly
                if self.quarantine_enabled and input_root and quarantine_dir:
                    qpath = self.corruption_detector.quarantine_font(
                        font_path, quarantine_dir, input_root
                    )
                    if qpath:
                        result.quarantined = True
                        result.quarantine_path = str(qpath)
                    elif self.verbose:
                        self.log(
                            f"Warning: Failed to quarantine {font_path} (Exception: {error_type})"
                        )
                result.add_error(
                    f"Font corruption detected {context}: {error_type}: {error_str}",
                    include_traceback=(isinstance(e, AssertionError) or self.verbose),
                )
            else:
                result.add_error(
                    f"Fatal error {context}: {error_type}: {error_str}",
                    include_traceback=(isinstance(e, AssertionError) or self.verbose),
                )
            result.success = False
        finally:
            # Ensure font is always closed to prevent resource leaks
            if font is not None:
                try:
                    font.close()
                except Exception:
                    # Ignore errors during close - font may already be closed or corrupted
                    pass

        return result
