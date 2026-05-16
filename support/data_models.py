"""
Data models for font fixing operations.

This module contains dataclasses and data structures used throughout
the FontFixer tool for tracking results and handler specifications.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Any, ClassVar
import traceback


@dataclass(frozen=True)
class HandlerSpec:
    """Specification for a font table handler."""

    full_name: str  # "OS/2"
    short_name: str  # "os2"
    description: str  # "OS/2 table (version, fsType...)"

    # Class-level registry
    _registry: ClassVar[dict[str, "HandlerSpec"]] = {}

    def __post_init__(self):
        HandlerSpec._registry[self.short_name] = self

    @classmethod
    def get(cls, short_name: str) -> Optional["HandlerSpec"]:
        """Get handler spec by short name."""
        return cls._registry.get(short_name)

    @classmethod
    def all_short_names(cls) -> list[str]:
        """Get all registered short names."""
        return list(cls._registry.keys())


# Define all handlers
HANDLER_OS2 = HandlerSpec(
    "OS/2", "os2", "OS/2 table (version, fsType, monospace, fsSelection)"
)
HANDLER_STYLE = HandlerSpec(
    "post+hhea+OS/2+head (style consistency)",
    "style",
    "Style consistency (italic angle, fsSelection, macStyle)",
)
HANDLER_GLYPH = HandlerSpec(
    "glyf/CFF + cmap + hmtx (glyphs)", "glyph", "Glyph fixes (.notdef, nbsp)"
)
HANDLER_KERN = HandlerSpec(
    "kern+GPOS (kerning)", "kern", "Kerning cleanup (remove legacy kern if GPOS exists)"
)
HANDLER_NAME = HandlerSpec(
    "name (naming)",
    "name",
    "Name table cleanup (Windows English only, remove problematic IDs)",
)

# All handler names (for backward compatibility during transition)
ALL_HANDLERS = [
    HANDLER_OS2.full_name,
    HANDLER_STYLE.full_name,
    HANDLER_GLYPH.full_name,
    HANDLER_KERN.full_name,
    HANDLER_NAME.full_name,
]


def _get_handler_spec_by_full_name(full_name: str) -> Optional[HandlerSpec]:
    """Get HandlerSpec by full_name (for backward compatibility)."""
    for spec in HandlerSpec._registry.values():
        if spec.full_name == full_name:
            return spec
    return None


@dataclass
class FontFixResult:
    """Result of font validation/fixing operation."""

    file: str
    success: bool = False
    was_modified: bool = False

    # Handler tracking
    handlers_run: list[str] = field(default_factory=list)
    handlers_changed: list[str] = field(default_factory=list)
    handlers_unchanged: list[str] = field(default_factory=list)

    # Detailed results
    validations: dict[str, dict[str, Any]] = field(default_factory=dict)
    changes: dict[str, dict[str, Any]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    # Quarantine info
    quarantined: bool = False
    quarantine_path: Optional[str] = None

    # Output info
    output_path: Optional[str] = None

    def add_error(self, error: str, include_traceback: bool = False):
        """Add error message with optional traceback."""
        self.errors.append(error)
        if include_traceback:
            self.errors.append(traceback.format_exc())

    def add_exception(
        self, exc: Exception, context: str = "", include_traceback: bool = False
    ):
        """Add formatted exception as error."""
        error_type = type(exc).__name__
        error_str = str(exc) if str(exc) else "No error message provided"

        if context:
            msg = f"{context}: {error_type}: {error_str}"
        else:
            msg = f"{error_type}: {error_str}"

        self.add_error(msg, include_traceback)

    def mark_handler_run(self, handler_name: str, changed: bool):
        """Record handler execution result.

        Appends to ``handlers_run`` and routes the name to ``handlers_changed`` or
        ``handlers_unchanged``. Call this only; do not append to ``handlers_run`` separately.
        """
        self.handlers_run.append(handler_name)
        if changed:
            self.handlers_changed.append(handler_name)
        else:
            self.handlers_unchanged.append(handler_name)

    def to_dict(self) -> dict:
        """Convert to dictionary for legacy compatibility."""
        return asdict(self)
