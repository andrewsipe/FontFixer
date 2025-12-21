"""
Name table manipulation utilities.

This module provides functions for cleaning and modifying OpenType name tables.
"""

try:
    from fontTools.ttLib import TTFont
except ImportError:
    TTFont = None  # Type hint fallback

from .constants import PLATFORM_WINDOWS, ENCODING_UNICODE_BMP, LANG_ENGLISH_US


def keep_windows_english_only(font: TTFont) -> int:
    """
    Keep only Windows English/Latin name records (platformID=3, platEncID=1, langID=0x409).
    Remove all other platform-specific name records.

    This ensures consistent name table behavior across platforms and reduces
    font file size by eliminating redundant name data.

    Args:
        font: TTFont object to modify

    Returns:
        Number of name records removed

    Note:
        Windows platform (platformID=3) with Unicode BMP encoding (platEncID=1)
        and US English language (langID=0x409) is the modern standard for
        cross-platform font compatibility.
    """
    if "name" not in font:
        return 0

    name_table = font["name"]
    original_count = len(name_table.names)

    # Keep only Windows Unicode BMP English US records
    # platformID=3 (Windows), platEncID=1 (Unicode BMP), langID=0x409 (English US)
    kept = [
        rec
        for rec in name_table.names
        if (
            rec.platformID == PLATFORM_WINDOWS
            and rec.platEncID == ENCODING_UNICODE_BMP
            and rec.langID == LANG_ENGLISH_US
        )
    ]

    name_table.names = kept
    return original_count - len(name_table.names)


def delete_specific_nameids(font: TTFont, name_ids: set[int]) -> int:
    """
    Remove name records with specified nameIDs.

    This function removes problematic nameIDs that can cause issues in certain
    font processing workflows or applications.

    Args:
        font: TTFont object to modify
        name_ids: Set of nameIDs to remove

    Returns:
        Number of name records removed

    Note:
        Commonly removed nameIDs include: 13 (License), 14 (License Info URL),
        18 (Compatible Full), 19 (Sample Text), 200-203 (WWS), and 55555 (custom).
    """
    if "name" not in font:
        return 0

    name_table = font["name"]
    before_count = len(name_table.names)
    name_table.names = [rec for rec in name_table.names if rec.nameID not in name_ids]
    return before_count - len(name_table.names)
