"""
Bitfield specification and manipulation.

This module provides classes for working with OpenType bitfield flags,
including fsSelection and macStyle bitfields.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class BitfieldSpec:
    """Specification for OpenType bitfield flags."""

    name: str
    bit_position: int
    description: str = ""

    def is_set(self, value: int) -> bool:
        """Check if this bit is set in value."""
        return bool(value & (1 << self.bit_position))

    def set(self, value: int) -> int:
        """Return value with this bit set."""
        return value | (1 << self.bit_position)

    def clear(self, value: int) -> int:
        """Return value with this bit cleared."""
        return value & ~(1 << self.bit_position)


@dataclass
class BitfieldGroup:
    """Collection of related bitfield flags."""

    name: str
    flags: Dict[str, BitfieldSpec]

    def get_changed_flags(self, old_value: int, new_value: int) -> tuple[list, list]:
        """Return (added_flags, removed_flags) as readable names."""
        changed_bits = old_value ^ new_value
        added = []
        removed = []

        for flag_name, spec in self.flags.items():
            if spec.is_set(changed_bits):
                if spec.is_set(new_value):
                    added.append(flag_name)
                else:
                    removed.append(flag_name)

        return added, removed

    def format_change(self, old_value: int, new_value: int) -> str:
        """Return human-readable change description."""
        added, removed = self.get_changed_flags(old_value, new_value)
        parts = [f"added {f}" for f in added] + [f"removed {f}" for f in removed]
        delta = ", ".join(parts) if parts else "no change"
        return f"0x{old_value:04X} -> 0x{new_value:04X} [{delta}]"


# Define bitfield groups
FS_SELECTION = BitfieldGroup(
    "fsSelection",
    {
        "ITALIC": BitfieldSpec("ITALIC", 0, "Italic font style"),
        "BOLD": BitfieldSpec("BOLD", 5, "Bold font weight"),
        "REGULAR": BitfieldSpec("REGULAR", 6, "Regular style"),
        "USE_TYPO_METRICS": BitfieldSpec("USE_TYPO_METRICS", 7, "Use typo metrics"),
        "WWS": BitfieldSpec("WWS", 8, "WWS family conformance"),
        "OBLIQUE": BitfieldSpec("OBLIQUE", 9, "Oblique style"),
    },
)

MAC_STYLE = BitfieldGroup(
    "macStyle",
    {
        "BOLD": BitfieldSpec("BOLD", 0, "Bold weight"),
        "ITALIC": BitfieldSpec("ITALIC", 1, "Italic style"),
    },
)
