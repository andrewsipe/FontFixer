"""
Name table handler.

This handler cleans up name tables by keeping only Windows English records
and removing problematic nameIDs.
"""

from typing import Dict, Any, Tuple

try:
    from fontTools.ttLib import TTFont
except ImportError:
    TTFont = None  # Type hint fallback

from .base_handler import TableHandler
from ..data_models import HANDLER_NAME
from ..name_table_utils import keep_windows_english_only, delete_specific_nameids
from ..decorators import conditional_fix


class NameTableHandler(TableHandler):
    """
    Handles name table cleanup.

    Responsibilities:
    - Keep only Windows English names
    - Remove specific problematic nameIDs
    """

    def get_table_name(self) -> str:
        return HANDLER_NAME.full_name

    def validate(self) -> Dict[str, Dict[str, Any]]:
        """Validate name table state."""
        if "name" not in self.font:
            self._track_validation("table_exists", False, "name table missing")
            return self.validations

        self.validate_condition(
            "only_windows_english",
            lambda: self._validate_windows_english_only(),
            "name table platform",
        )
        self.validate_condition(
            "no_problematic_ids",
            lambda: self._validate_problematic_ids(),
            "name table IDs",
        )

        return self.validations

    def _validate_windows_english_only(self) -> Tuple[bool, str]:
        """Helper: validate only Windows English names."""
        name_table = self.font["name"]
        non_windows_count = sum(
            1
            for rec in name_table.names
            if not (rec.platformID == 3 and rec.platEncID == 1 and rec.langID == 0x409)
        )
        is_valid = non_windows_count == 0
        return (
            is_valid,
            f"Current: {non_windows_count} non-Windows-English name(s), Expected: 0",
        )

    def _validate_problematic_ids(self) -> Tuple[bool, str]:
        """Helper: validate no problematic nameIDs."""
        name_table = self.font["name"]
        problematic_ids = {13, 14, 18, 19, 200, 201, 202, 203, 55555}
        problematic_count = sum(
            1 for rec in name_table.names if rec.nameID in problematic_ids
        )
        is_valid = problematic_count == 0
        return (
            is_valid,
            f"Current: {problematic_count} problematic nameID(s), Expected: 0",
        )

    def fix(self) -> bool:
        """Clean up name table."""
        any_changed = False

        if not self.validations.get("only_windows_english", {}).get("valid", True):
            any_changed |= self._keep_windows_english_only()

        if not self.validations.get("no_problematic_ids", {}).get("valid", True):
            any_changed |= self._delete_problematic_ids()

        return any_changed

    @conditional_fix("only_windows_english")
    def _keep_windows_english_only(self) -> bool:
        """Keep only Windows English names."""
        original_count = len(self.font["name"].names) if "name" in self.font else 0
        removed = keep_windows_english_only(self.font)

        if removed > 0:
            self._track_change(
                "total_names", original_count, original_count - removed, removed > 0
            )
            self._track_change("removed_names", 0, removed, removed > 0)
            return True

        return False

    @conditional_fix("no_problematic_ids")
    def _delete_problematic_ids(self) -> bool:
        """Delete problematic nameIDs."""
        ids_to_remove = {13, 14, 18, 19, 200, 201, 202, 203, 55555}
        specific_removed = delete_specific_nameids(self.font, ids_to_remove)

        if specific_removed > 0:
            self._track_change(
                "count_removed", 0, specific_removed, specific_removed > 0
            )
            self._track_change(
                "nameIDs_removed",
                "present",
                ", ".join(map(str, sorted(ids_to_remove))),
                specific_removed > 0,
                info_only=True,
            )
            return True

        return False
