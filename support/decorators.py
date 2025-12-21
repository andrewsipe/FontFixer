"""
Decorators for font fixing operations.

This module provides decorators used by handlers to control fix execution
based on validation results.
"""

from functools import wraps
from typing import Callable

try:
    from fontTools.ttLib import TTLibError
except ImportError:
    TTLibError = Exception  # Fallback if fonttools not available


def conditional_fix(*validation_keys: str):
    """
    Decorator: Only execute fix if corresponding validation(s) failed.

    Args:
        *validation_keys: One or more validation check names that must fail
                         for this fix to run

    Usage:
        @conditional_fix("version_current")
        def _fix_version(self) -> bool:
            # Only runs if "version_current" validation failed
            ...
    """

    def decorator(fix_method: Callable) -> Callable:
        @wraps(fix_method)
        def wrapper(self) -> bool:
            # Check if ANY of the validations failed
            should_run = any(
                not self.validations.get(key, {}).get("valid", True)
                for key in validation_keys
            )

            if not should_run:
                return False

            try:
                return fix_method(self)
            except (TTLibError, AttributeError, IndexError, ValueError) as e:
                if self.verbose:
                    self.log(f"Skipping {fix_method.__name__} due to error: {e}")
                return False

        return wrapper

    return decorator
