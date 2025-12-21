"""
Base handler class for font table validation and correction.

This module provides the TableHandler abstract base class and ChangeBuilder
helper class that form the foundation for all font table handlers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple, Any, Callable, Union

try:
    from fontTools.ttLib import TTFont, TTLibError
except ImportError:
    TTFont = None  # Type hint fallback
    TTLibError = Exception

from ..bitfield import BitfieldGroup


class TableHandler(ABC):
    """
    Base class for font table validation and correction.

    Each handler manages one or more related OpenType table fixes,
    providing validation and correction capabilities.
    """

    def __init__(self, font: TTFont, verbose: bool = False):
        self.font = font
        self.verbose = verbose
        self.changes = {}  # Track all changes made
        self.validations = {}  # Track validation results

    @abstractmethod
    def validate(self) -> Dict[str, Dict[str, Any]]:
        """
        Validate table state.

        Returns:
            Dictionary mapping check names to validation results.
            Each result contains:
                - 'valid' (bool): Whether the check passes validation standards
                - 'message' (str): Human-readable description of the validation state
        """
        pass

    @abstractmethod
    def fix(self) -> bool:
        """
        Apply corrections based on validation results.

        Returns:
            True if any changes were made, False otherwise.
        """
        pass

    @abstractmethod
    def get_table_name(self) -> str:
        """
        Return the handler name (describes what this handler manages).

        Returns:
            Handler name string.
        """
        pass

    def get_changes(self) -> Dict:
        """Return dict of changes made."""
        return self.changes

    def get_validations(self) -> Dict:
        """Return dict of validation results."""
        return self.validations

    def _track_change(
        self,
        property_name: str,
        old_value,
        new_value,
        changed: bool = None,
        info_only: bool = False,
    ):
        """
        Helper to track a property change.

        Args:
            property_name: Name of the property
            old_value: Original value
            new_value: New value
            changed: Whether value changed (auto-detected if None)
            info_only: If True, this is informational only (not a change)
        """
        if changed is None:
            changed = old_value != new_value

        self.changes[property_name] = {
            "old": old_value,
            "new": new_value,
            "changed": changed,
            "info_only": info_only,
        }

    def _track_bitfield_change(
        self,
        property_name: str,
        old_value: int,
        new_value: int,
        bitfield_group: BitfieldGroup,
    ) -> None:
        """
        Track a bitfield change with formatted description.

        Args:
            property_name: Name of the property
            old_value: Original bitfield value
            new_value: New bitfield value
            bitfield_group: BitfieldGroup instance for formatting
        """
        if old_value == new_value:
            return

        change_desc = bitfield_group.format_change(old_value, new_value)
        # Store formatted description as the new value
        self._track_change(property_name, f"0x{old_value:04X}", change_desc, True)

    def _track_multiple_changes(
        self,
        changes: list[
            Union[
                tuple[str, Any, Any],  # (name, old, new)
                tuple[str, Any, Any, bool],  # (name, old, new, changed)
            ]
        ],
    ) -> None:
        """
        Track multiple changes at once.

        Args:
            changes: List of (property_name, old_value, new_value) or
                     (property_name, old_value, new_value, changed) tuples
        """
        for change in changes:
            if len(change) == 4:
                prop, old, new_val, changed = change
                self._track_change(prop, old, new_val, changed)
            else:
                prop, old, new_val = change
                self._track_change(prop, old, new_val)

    def _track_info_changes(
        self,
        info_items: Union[dict[str, Any], list[tuple[str, Any]]],
    ) -> None:
        """
        Track informational-only properties (no actual changes).

        Args:
            info_items: Dict of {property_name: value} or list of (property_name, value) tuples
        """
        if isinstance(info_items, dict):
            items = info_items.items()
        else:
            items = info_items

        for prop, value in items:
            self._track_change(prop, value, value, False, info_only=True)

    def _track_validation(self, check_name: str, is_valid: bool, message: str = ""):
        """
        Track a validation check result.

        Args:
            check_name: Identifier for this validation check
            is_valid: True if the check passes validation standards
            message: Human-readable description of the validation state
        """
        self.validations[check_name] = {"valid": is_valid, "message": message}

    def validate_field(
        self,
        check_name: str,
        table_name: str,
        field_path: str,  # Can be "version" or nested "panose.bProportion"
        validator: Callable[[Any], Tuple[bool, str]],
        missing_table_msg: Optional[str] = None,
        missing_field_msg: Optional[str] = None,
    ) -> bool:
        """
        Generic field validation with comprehensive error handling.

        Args:
            check_name: Validation check identifier
            table_name: OpenType table name (e.g., "OS/2")
            field_path: Field name or dot-notation path (e.g., "panose.bProportion")
            validator: Function that takes field value and returns (is_valid, message)
            missing_table_msg: Override message when table doesn't exist
            missing_field_msg: Override message when field doesn't exist

        Returns:
            True if validation passed, False otherwise
        """
        # Check table exists
        if table_name not in self.font:
            msg = missing_table_msg or f"{table_name} table missing"
            self._track_validation(check_name, False, msg)
            return False

        try:
            # Navigate field path
            obj = self.font[table_name]
            for part in field_path.split("."):
                if not hasattr(obj, part):
                    msg = (
                        missing_field_msg or f"{table_name}.{field_path} field missing"
                    )
                    self._track_validation(check_name, False, msg)
                    return False
                obj = getattr(obj, part)

            # Run validator
            is_valid, message = validator(obj)
            self._track_validation(check_name, is_valid, message)
            return is_valid

        except (TTLibError, AttributeError, TypeError, IndexError, ValueError) as e:
            msg = f"Cannot validate {table_name}.{field_path}: {str(e)}"
            self._track_validation(check_name, False, msg)
            return False

    def validate_condition(
        self,
        check_name: str,
        condition: Callable[[], Tuple[bool, str]],
        error_context: str = "",
    ) -> bool:
        """
        Validate a complex condition with error handling.

        Args:
            check_name: Validation check identifier
            condition: Function that returns (is_valid, message)
            error_context: Context description for error messages

        Returns:
            True if validation passed, False otherwise
        """
        try:
            is_valid, message = condition()
            self._track_validation(check_name, is_valid, message)
            return is_valid
        except Exception as e:
            msg = f"Validation error{' in ' + error_context if error_context else ''}: {str(e)}"
            self._track_validation(check_name, False, msg)
            return False

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

    def track_changes(self) -> "ChangeBuilder":
        """Start building a change tracking group."""
        return ChangeBuilder(self)


class ChangeBuilder:
    """Fluent API for building complex change tracking."""

    def __init__(self, handler: "TableHandler"):
        self.handler = handler
        self.changes: list[tuple] = []

    def add(
        self,
        name: str,
        old: Any,
        new: Any,
        changed: Optional[bool] = None,
        info_only: bool = False,
    ) -> "ChangeBuilder":
        """Add a change (chainable)."""
        if changed is None:
            changed = old != new
        self.changes.append((name, old, new, changed, info_only))
        return self

    def add_if_changed(self, name: str, old: Any, new: Any) -> "ChangeBuilder":
        """Only add if value actually changed."""
        if old != new:
            self.changes.append((name, old, new, True, False))
        return self

    def add_info(self, name: str, value: Any) -> "ChangeBuilder":
        """Add info-only property."""
        self.changes.append((name, None, value, False, True))
        return self

    def commit(self) -> bool:
        """Commit all changes and return whether any were made."""
        for name, old, new, changed, info_only in self.changes:
            self.handler._track_change(name, old, new, changed, info_only)
        return any(c[3] for c in self.changes)  # Any with changed=True
