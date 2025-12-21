"""
OpenType font constants.

This module contains all OpenType specification constants used throughout
the FontFixer tool, including platform IDs, encoding IDs, bit positions,
and numeric limits.
"""

# Name table platform constants
PLATFORM_WINDOWS = 3
ENCODING_UNICODE_BMP = 1
LANG_ENGLISH_US = 0x409

# OS/2 fsSelection bit positions
FS_SELECTION_ITALIC = 0
FS_SELECTION_BOLD = 5
FS_SELECTION_REGULAR = 6
FS_SELECTION_USE_TYPO_METRICS = 7
FS_SELECTION_WWS = 8
FS_SELECTION_OBLIQUE = 9

# head.macStyle bit positions
MAC_STYLE_BOLD = 0
MAC_STYLE_ITALIC = 1

# Standard weight classes
WEIGHT_BOLD = 700

# Signed 16-bit integer limits (used for bounds, caretSlopeRun, etc.)
SIGNED_16BIT_MIN = -32768
SIGNED_16BIT_MAX = 32767
