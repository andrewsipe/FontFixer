#!/usr/bin/env python3
"""
Font Fixer - Modular font validation and correction tool.

A high-performance font validation and correction tool that applies comprehensive
OpenType font fixes in a single pass. Designed to replace sequential ftcli command
workflows with efficient batch processing.
"""

import sys
import argparse
import multiprocessing as mp
import traceback
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple, Dict

from concurrent.futures import ProcessPoolExecutor, as_completed

# Constants
DEFAULT_VERSION = "1.0.0"
TOP_FIXES_TO_DISPLAY = 5
EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_NO_FONTS_FOUND = 1

try:
    import fontTools.ttLib  # noqa: F401
except ImportError:
    print("Error: fonttools library not found.")
    print("Install with: pip install fonttools")
    sys.exit(EXIT_FAILURE)

# Add project root to path for FontCore imports (works for root and subdirectory scripts)
# ruff: noqa: E402


def _find_project_root() -> Path:
    """Locate project root by walking up until FontCore is found."""
    root = Path(__file__).resolve().parent
    while not (root / "FontCore").exists() and root.parent != root:
        root = root.parent
    return root


_project_root = _find_project_root()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    import FontCore.core_console_styles as cs
    from FontCore.core_file_collector import collect_font_files
except ImportError:
    print("Error: FontCore not found.")
    print("FontCore must be available via symlink or in parent directory.")
    sys.exit(EXIT_FAILURE)

try:
    from rich.markup import escape
except ImportError:
    # Fallback if Rich is not available
    def escape(text: str) -> str:
        return text


# Get the themed console singleton
console = cs.get_console()

# Import FontFixer modules (relative for installed package)
from FontFixer.support.font_fixer import FontFixer
from FontFixer.support.data_models import (
    HandlerSpec,
    ALL_HANDLERS,
    _get_handler_spec_by_full_name,
)


@lru_cache(maxsize=None)
def _handler_short_name(full_name: str) -> str:
    """Return short name for a handler full_name; cache for repeated lookups."""
    spec = _get_handler_spec_by_full_name(full_name)
    return spec.short_name if spec else full_name


def get_version() -> str:
    """Return package version; use DEFAULT_VERSION if not installed as package."""
    try:
        from FontFixer import __version__
        return __version__
    except ImportError:
        return DEFAULT_VERSION


fontfixer_version = get_version()


# ============================================================================
# PROCESSING STATISTICS (single-pass aggregation)
# ============================================================================


@dataclass
class ProcessingStats:
    """Aggregated statistics from a processing run (computed in one pass)."""

    updated: int = 0
    unchanged: int = 0
    failed: int = 0
    quarantined: int = 0
    common_fixes: dict[str, int] = field(default_factory=dict)
    handler_changed_counts: dict[str, int] = field(default_factory=dict)
    handler_unchanged_counts: dict[str, int] = field(default_factory=dict)


def _calculate_statistics(results: list[Dict]) -> ProcessingStats:
    """Compute all summary statistics in a single pass over results."""
    stats = ProcessingStats()
    for r in results:
        if not r.get("success", False):
            stats.failed += 1
            if r.get("quarantined", False):
                stats.quarantined += 1
            continue
        if r.get("was_modified", False):
            stats.updated += 1
            for handler, changes in r.get("changes", {}).items():
                for prop, change in changes.items():
                    if change.get("changed"):
                        key = f"{_handler_short_name(handler)}.{prop}"
                        stats.common_fixes[key] = stats.common_fixes.get(key, 0) + 1
        else:
            stats.unchanged += 1
        for handler in r.get("handlers_changed", []):
            name = _handler_short_name(handler)
            stats.handler_changed_counts[name] = (
                stats.handler_changed_counts.get(name, 0) + 1
            )
        for handler in r.get("handlers_unchanged", []):
            name = _handler_short_name(handler)
            stats.handler_unchanged_counts[name] = (
                stats.handler_unchanged_counts.get(name, 0) + 1
            )
    return stats


# ============================================================================
# PROCESSING CONFIGURATION
# ============================================================================


@dataclass
class ProcessingConfig:
    """Configuration for font processing run."""

    input_path: Path
    output_dir: Optional[Path]
    recursive: bool
    num_workers: int
    verbose: bool
    dry_run: bool
    validate_only: bool
    enabled_handlers: Optional[list[str]]
    quarantine_enabled: bool
    quarantine_dir: Optional[Path]
    input_root: Path

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "ProcessingConfig":
        """Create config from parsed arguments."""
        input_root = (
            args.input_path if args.input_path.is_dir() else args.input_path.parent
        )
        quarantine_enabled = not args.no_quarantine
        quarantine_dir = input_root / "_quarantine" if quarantine_enabled else None
        num_workers = mp.cpu_count() if args.jobs == 0 else args.jobs

        enabled_handlers = _parse_handler_selection(args)

        return cls(
            input_path=args.input_path,
            output_dir=args.output_dir,
            recursive=args.recursive,
            num_workers=num_workers,
            verbose=args.verbose,
            dry_run=args.dry_run,
            validate_only=args.validate_only,
            enabled_handlers=enabled_handlers,
            quarantine_enabled=quarantine_enabled,
            quarantine_dir=quarantine_dir,
            input_root=input_root,
        )

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)


# ============================================================================
# ARGUMENT PARSING
# ============================================================================


def _parse_handler_selection(args) -> Optional[list[str]]:
    """Parse --handlers and --skip-handlers arguments."""
    if args.handlers and args.skip_handlers:
        cs.StatusIndicator("error").add_message(
            "--handlers and --skip-handlers cannot be used together"
        ).emit(console)
        sys.exit(EXIT_FAILURE)

    if args.handlers:
        return _parse_enabled_handlers(args.handlers)

    if args.skip_handlers:
        return _parse_skipped_handlers(args.skip_handlers)

    return None  # All handlers enabled


def _parse_enabled_handlers(handlers_str: str) -> list[str]:
    """Parse comma-separated handler list."""
    handler_list = [h.strip().lower() for h in handlers_str.split(",")]
    invalid = [h for h in handler_list if h not in HandlerSpec.all_short_names()]

    if invalid:
        cs.StatusIndicator("error").add_message(
            f"Invalid handler(s): {', '.join(invalid)}. "
            f"Available: {', '.join(HandlerSpec.all_short_names())}"
        ).emit(console)
        sys.exit(EXIT_FAILURE)

    return [HandlerSpec.get(h).full_name for h in handler_list]


def _parse_skipped_handlers(handlers_str: str) -> list[str]:
    """Parse comma-separated skip list."""
    skip_list = [h.strip().lower() for h in handlers_str.split(",")]
    invalid = [h for h in skip_list if h not in HandlerSpec.all_short_names()]

    if invalid:
        cs.StatusIndicator("error").add_message(
            f"Invalid handler(s): {', '.join(invalid)}. "
            f"Available: {', '.join(HandlerSpec.all_short_names())}"
        ).emit(console)
        sys.exit(EXIT_FAILURE)

    all_handlers_set = set(ALL_HANDLERS)
    skip_handlers_set = {HandlerSpec.get(h).full_name for h in skip_list}
    enabled = list(all_handlers_set - skip_handlers_set)

    if not enabled:
        cs.StatusIndicator("error").add_message("Cannot skip all handlers").emit(
            console
        )
        sys.exit(EXIT_FAILURE)

    return enabled


def parse_and_validate_arguments() -> ProcessingConfig:
    """Parse command-line arguments and validate configuration."""
    parser = argparse.ArgumentParser(
        description=f"Apply all font fixes in a single pass using only fonttools (v{fontfixer_version}).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  Process all fonts in a directory (non-recursive):
    %(prog)s fonts/

  Process recursively with 8 parallel workers:
    %(prog)s -r -j 8 fonts/

  Save fixed fonts to a different directory:
    %(prog)s -o output/ fonts/

  Only run specific handlers (comma-separated):
    %(prog)s --handlers os2,style fonts/

  Skip specific handlers:
    %(prog)s --skip-handlers name fonts/

  Preview what would be changed without modifying files:
    %(prog)s --validate-only -V fonts/MyFont.ttf

AVAILABLE HANDLERS:
  Handler      Description
  -----------  ----------------------------------------------------
  os2          OS/2 table version, embedding permissions, monospace
               detection, USE_TYPO_METRICS and WWS flags

  style        Style consistency across post, hhea, OS/2, and head
               tables (italic angle, caret slope, fsSelection, macStyle)

  glyph        Glyph-level fixes: .notdef structure, nbsp (U+00A0)
               presence and width matching space character

  kern         Legacy kern table removal when modern GPOS table exists

  name         Name table cleanup: Windows English records only,
               removal of problematic nameIDs (13,14,18,19,200-203,55555)

DEPENDENCIES:
  This tool requires only fonttools:
    pip install fonttools

For more information, see: https://github.com/fonttools/fonttools
        """,
    )

    parser.add_argument(
        "input_path", type=Path, help="Font file or directory containing font files"
    )

    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Process directories recursively"
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="Output directory (default: overwrite originals)",
    )

    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=1,
        help="Number of parallel workers (default: 1, use 0 for CPU count)",
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Show what would be processed without making changes",
    )

    parser.add_argument(
        "--handlers",
        type=str,
        help="Comma-separated list of handlers to run. Available: os2, style, glyph, kern, name. Default: all",
    )

    parser.add_argument(
        "--skip-handlers",
        type=str,
        help="Comma-separated list of handlers to skip. Available: os2, style, glyph, kern, name",
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate fonts and report issues without applying any fixes",
    )

    parser.add_argument(
        "--no-quarantine",
        action="store_true",
        help="Disable automatic quarantine of corrupted fonts (quarantine enabled by default)",
    )

    args = parser.parse_args()

    return ProcessingConfig.from_args(args)


# ============================================================================
# MULTIPROCESSING WRAPPER
# ============================================================================


def process_font_wrapper(args: Tuple[Path, ProcessingConfig]) -> Dict:
    """Wrapper for multiprocessing (must accept a single pickleable argument)."""
    font_path, config = args
    fixer = FontFixer(
        verbose=config.verbose,
        enabled_handlers=config.enabled_handlers,
        quarantine_enabled=config.quarantine_enabled,
    )
    result = fixer.fix_font(
        font_path,
        config.output_dir,
        config.validate_only,
        config.quarantine_dir,
        config.input_root,
    )
    return result.to_dict()  # Convert to dict for multiprocessing compatibility


def discover_and_validate_fonts(config: ProcessingConfig) -> list[Path]:
    """Find all font files to process."""
    font_files = collect_font_files([config.input_path], config.recursive)
    font_paths = [Path(f) for f in font_files]

    if not font_paths:
        cs.StatusIndicator("error").add_message("No font files found.").emit(console)
        sys.exit(EXIT_NO_FONTS_FOUND)

    return font_paths


def display_preflight_info(config: ProcessingConfig, font_paths: list[Path]):
    """Display header, checklist, and file list."""
    cs.fmt_header("Font Fixer (fonttools)", console=console)
    cs.emit("")

    # Show which handlers will run
    if config.enabled_handlers is None:
        handler_display = HandlerSpec.all_short_names()
    else:
        handler_display = [
            _handler_short_name(h)
            for h in config.enabled_handlers
            if _get_handler_spec_by_full_name(h) is not None
        ]

    # Build operations list with handler descriptions
    operations = []
    for short_name in handler_display:
        spec = HandlerSpec.get(short_name)
        description = spec.description if spec else short_name
        operations.append(f"{short_name}: {description}")

    cs.fmt_preflight_checklist("Font Fixer", operations, console=console)

    # Show file list
    cs.emit("")
    cs.StatusIndicator("info").add_message(
        f"Found {cs.fmt_count(len(font_paths))} font file(s) to process:"
    ).emit(console)
    for path in font_paths:
        cs.emit(f"  - {cs.fmt_file_compact(str(path))}", console=console)

    if config.dry_run:
        cs.emit("")
        cs.StatusIndicator("info", dry_run=True).add_message(
            "No changes will be made"
        ).emit(console)
        sys.exit(EXIT_SUCCESS)


def main():
    """Main entry point."""
    # Parse and validate arguments
    config = parse_and_validate_arguments()

    # Discover fonts
    font_paths = discover_and_validate_fonts(config)

    # Display preflight info
    display_preflight_info(config, font_paths)

    cs.emit("")
    cs.StatusIndicator("info").add_message(
        f"Processing with {cs.fmt_count(config.num_workers)} worker(s)..."
    ).emit(console)
    cs.emit("")

    # Process fonts
    results = process_all_fonts(config, font_paths)

    # Display summary
    display_summary(config, results)


def _display_handler_list(config: ProcessingConfig):
    """Display which handlers will run."""
    if config.enabled_handlers:
        handler_display = [
            _handler_short_name(h)
            for h in config.enabled_handlers
            if _get_handler_spec_by_full_name(h) is not None
        ]
    else:
        handler_display = HandlerSpec.all_short_names()

    cs.StatusIndicator("info").add_message(
        f"Running handlers: {', '.join(handler_display)}"
    ).emit(console)


def _display_result(result: Dict):
    """Display result for a single font."""
    if result["success"]:
        # Show NO CHANGE message for unchanged handlers
        if result.get("handlers_unchanged"):
            unchanged_display = [
                _handler_short_name(h)
                for h in result["handlers_unchanged"]
                if _get_handler_spec_by_full_name(h) is not None
            ]
            cs.StatusIndicator("unchanged").add_message(
                f"Already compliant: {', '.join(unchanged_display)}"
            ).emit(console)

        # Show SAVED status if file was modified
        if result.get("was_modified") and result.get("output_path"):
            cs.StatusIndicator("saved").add_file(
                result["output_path"], filename_only=True
            ).emit(console)
    else:
        # Show quarantine status if file was quarantined
        if result.get("quarantined"):
            cs.StatusIndicator("error").add_file(
                result["file"], filename_only=True
            ).with_explanation(
                f"Quarantined: {result.get('quarantine_path', 'unknown')}; "
                + "; ".join(result["errors"])
            ).emit(console)
        else:
            cs.StatusIndicator("error").add_file(
                result["file"], filename_only=True
            ).with_explanation("; ".join(result["errors"])).emit(console)


def process_all_fonts(config: ProcessingConfig, font_paths: list[Path]) -> list[Dict]:
    """Process all fonts (sequential or parallel)."""
    if config.num_workers == 1:
        return _process_sequential(config, font_paths)
    else:
        return _process_parallel(config, font_paths)


def _process_sequential(config: ProcessingConfig, font_paths: list[Path]) -> list[Dict]:
    """Process fonts one at a time."""
    results = []

    for idx, font_path in enumerate(font_paths, 1):
        cs.StatusIndicator("parsing").add_message(
            f"File {idx} of {len(font_paths)} |"
        ).add_file(str(font_path), filename_only=True).emit(console)

        _display_handler_list(config)

        fixer = FontFixer(
            verbose=config.verbose,
            enabled_handlers=config.enabled_handlers,
            quarantine_enabled=config.quarantine_enabled,
        )

        result = fixer.fix_font(
            font_path,
            config.output_dir,
            config.validate_only,
            config.quarantine_dir,
            config.input_root,
        )

        result_dict = result.to_dict()  # Convert for display and storage
        results.append(result_dict)
        _display_result(result_dict)

    return results


def _process_parallel(config: ProcessingConfig, font_paths: list[Path]) -> list[Dict]:
    """Process fonts in parallel."""
    work_items = [(font_path, config) for font_path in font_paths]

    results = []

    with ProcessPoolExecutor(max_workers=config.num_workers) as executor:
        futures = {
            executor.submit(process_font_wrapper, item): item[0] for item in work_items
        }

        completed = 0
        for future in as_completed(futures):
            font_path = futures[future]
            try:
                result = future.result()
                results.append(result)

                completed += 1
                cs.StatusIndicator("parsing").add_message(
                    f"File {completed} of {len(font_paths)} |"
                ).add_file(str(font_path), filename_only=True).emit(console)

                _display_result(result)
            except Exception as e:
                error_msg = f"{str(font_path)}: {type(e).__name__}: {str(e)}"
                if config.verbose:
                    error_msg = f"{error_msg}\n{traceback.format_exc()}"
                cs.StatusIndicator("error").add_file(
                    str(font_path), filename_only=True
                ).with_explanation(error_msg).emit(console)
                results.append(
                    {
                        "file": str(font_path),
                        "success": False,
                        "errors": [error_msg],
                    }
                )

    return results


def display_summary(config: ProcessingConfig, results: list[Dict]):
    """Display processing summary."""
    stats = _calculate_statistics(results)

    cs.fmt_processing_summary(
        dry_run=False,
        updated=stats.updated,
        unchanged=stats.unchanged,
        errors=stats.failed,
        console=console,
    )

    # Show quarantined count if any files were quarantined
    if stats.quarantined > 0 and config.quarantine_dir:
        cs.emit("", console=console)
        cs.StatusIndicator("info").add_message(
            f"Quarantined {cs.fmt_count(stats.quarantined)} corrupted font file(s) to: {config.quarantine_dir}"
        ).emit(console)

    # Show most common fixes applied
    if stats.updated > 0 and stats.common_fixes:
        _display_common_fixes(stats.common_fixes)

    # Show handler-level statistics
    if stats.handler_changed_counts or stats.handler_unchanged_counts:
        _display_handler_statistics(stats.handler_changed_counts, stats.handler_unchanged_counts)

    # Show failed files if any
    if stats.failed > 0:
        _display_failed_files(results, stats.failed)


def _display_common_fixes(common_fixes: dict[str, int]):
    """Display most common fixes applied (from precomputed stats)."""
    if not common_fixes:
        return
    top_fixes = sorted(
        common_fixes.items(), key=lambda x: x[1], reverse=True
    )[:TOP_FIXES_TO_DISPLAY]
    cs.emit("", console=console)
    cs.StatusIndicator("info").add_message("Most common fixes applied:").emit(
        console
    )
    for fix, count in top_fixes:
        cs.emit(f"  · {fix}: {count} file(s)", console=console)


def _display_handler_statistics(
    handler_changed_counts: dict[str, int],
    handler_unchanged_counts: dict[str, int],
):
    """Display handler-level statistics (from precomputed counts)."""
    if not handler_changed_counts and not handler_unchanged_counts:
        return
    cs.emit("")

    all_handlers = set(handler_changed_counts.keys()) | set(
        handler_unchanged_counts.keys()
    )
    total_updates = sum(handler_changed_counts.values())
    total_stable = sum(handler_unchanged_counts.values())

    indicator = cs.StatusIndicator("success").add_message("Handler Statistics")
    indicator.add_item(
        f"Handlers evaluated: {cs.fmt_count(len(all_handlers))} | "
        f"Made changes: {cs.fmt_count(total_updates)} | "
        f"No changes: {cs.fmt_count(total_stable)}"
    )

    for handler_name in sorted(all_handlers):
        changed = handler_changed_counts.get(handler_name, 0)
        unchanged = handler_unchanged_counts.get(handler_name, 0)

        if changed and unchanged:
            detail = f"{handler_name}: {cs.fmt_count(changed)} updated, {cs.fmt_count(unchanged)} unchanged"
        elif changed:
            detail = f"{handler_name}: {cs.fmt_count(changed)} updated"
        else:
            detail = f"{handler_name}: {cs.fmt_count(unchanged)} unchanged"

        indicator.add_item(detail, indent_level=2)

    indicator.emit(console)


def _display_failed_files(results: list[Dict], failed_count: int):
    """Display list of failed files and exit with appropriate code."""
    cs.emit("")
    cs.StatusIndicator("error").add_message("Failed files:").emit(console)
    for result in results:
        if not result["success"]:
            cs.StatusIndicator("error").add_file(
                str(result["file"]), filename_only=False
            ).with_explanation("; ".join(result["errors"])).emit(console)

    cs.emit("")
    sys.exit(EXIT_SUCCESS if failed_count == 0 else EXIT_FAILURE)


if __name__ == "__main__":
    main()
