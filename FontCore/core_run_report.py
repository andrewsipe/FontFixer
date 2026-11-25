"""core_run_report: one place that prints what a tool did, in one order, and decides the exit code.

A tool reports *facts* (a `FileReport` per file); the `RunReporter` prints them with the shared label chips
(`core_console_styles`), counts the outcomes, prints the summary sentence and says what the exit code is. Because the
reporter only prints from the main process, a parallel run (`-j N`) prints one intact block per file instead of
lines that arrive from several workers at once.

Block order, always: the header (`PARSING  File n of N | name`), what changed (one `UPDATED` section per
thing changed, with its detail lines), then the result lines (`NO CHANGE`, `SAVED TO`, `ERROR`, ...).

Outcomes: updated, unchanged, skipped, error. An outcome the reporter does not know counts as an error.
Exit code: 0 when nothing failed, 1 when at least one file errored. (2 is for wrong usage and is the tool's business.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import FontCore.core_console_styles as cs

OUTCOMES = ("updated", "unchanged", "skipped", "error")
DEFAULT_VERBS = {"updated": "Updated", "unchanged": "unchanged", "skipped": "skipped", "error": "problem"}


@dataclass
class Line:
    """One result line in a file block: kind is a status word (unchanged, saved, error, info, warning, ...)."""

    kind: str
    message: Optional[str] = None
    file: Optional[str] = None
    explanation: Optional[str] = None


@dataclass
class FileReport:
    name: str
    outcome: str = "unchanged"
    changes: List[Tuple[str, List[str]]] = field(default_factory=list)  # (what changed, detail lines)
    lines: List[Line] = field(default_factory=list)


class RunReporter:
    def __init__(self, console=None, total: int = 0, verbs: Optional[Dict[str, str]] = None):
        self.console = console if console is not None else cs.get_console()
        self.total = total
        self.verbs = {**DEFAULT_VERBS, **(verbs or {})}
        self.counts: Dict[str, int] = {o: 0 for o in OUTCOMES}

    # ---- printing one file -------------------------------------------------------------------------------
    def header(self, index: int, name: str) -> None:
        cs.StatusIndicator("parsing").add_message(f"File {index} of {self.total} |").add_file(
            name, filename_only=True
        ).emit(self.console)

    def body(self, report: FileReport) -> None:
        for what, details in report.changes:
            indicator = cs.StatusIndicator("updated", dry_run=False).add_message(what)
            for line in details:
                indicator.add_item(line)
            indicator.emit(self.console)
        for line in report.lines:
            indicator = cs.StatusIndicator(line.kind)
            if line.message:
                indicator.add_message(line.message)
            if line.file:
                indicator.add_file(line.file, filename_only=True)
            if line.explanation:
                indicator.with_explanation(line.explanation)
            indicator.emit(self.console)
        outcome = report.outcome if report.outcome in OUTCOMES else "error"
        self.counts[outcome] += 1

    def file(self, index: int, report: FileReport) -> None:
        """Header and body together: what a parallel run does when a font finishes."""
        self.header(index, report.name)
        self.body(report)

    # ---- the end of the run ------------------------------------------------------------------------------
    def sentence(self) -> str:
        c, v = self.counts, self.verbs
        parts = [f"{v['updated']} {c['updated']}", f"{v['unchanged']} {c['unchanged']}"]
        if c["skipped"]:
            parts.append(f"{v['skipped']} {c['skipped']}")
        problems = c["error"]
        noun = v["error"]
        parts.append(f"{problems} {noun}{'' if problems == 1 else 's'}" if problems else f"no {noun}s")
        return ", ".join(parts) + "."

    def summary(self) -> None:
        indicator = cs.StatusIndicator("success" if not self.counts["error"] else "warning")
        indicator.add_message("Finished")
        indicator.add_item(self.sentence())
        indicator.emit(self.console)

    def exit_code(self) -> int:
        return 1 if self.counts["error"] else 0


__all__ = ["FileReport", "Line", "RunReporter", "OUTCOMES"]
