"""
Utility functions for font processing.

This module contains pure utility functions used throughout the FontFixer tool.
"""

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
