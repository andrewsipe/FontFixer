"""FontFixer table handlers."""

from .base_handler import TableHandler, ChangeBuilder
from .os2_handler import OS2TableHandler
from .style_handler import StyleConsistencyHandler
from .glyph_handler import GlyphHandler
from .kern_handler import KernHandler
from .name_handler import NameTableHandler

__all__ = [
    "TableHandler",
    "ChangeBuilder",
    "OS2TableHandler",
    "StyleConsistencyHandler",
    "GlyphHandler",
    "KernHandler",
    "NameTableHandler",
]
