"""Rich-styled --help for FontFixer.

Registers as the -h/--help action so a safety panel is inserted after the
description. Flag names are built from Text/Table (not markup strings) so
values like [-o DIR] are never misread as Rich markup.
"""

from __future__ import annotations

import argparse
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def safety_panel() -> Panel:
    """The 'files are overwritten' notice."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(no_wrap=True)
    grid.add_column()
    grid.add_row(Text("Keep originals", style="bold"), Text("-o DIR", style="cyan"))
    grid.add_row(
        Text("Inspect fonts, fix nothing", style="bold"),
        Text("--validate-only", style="cyan"),
    )
    grid.add_row(
        Text("List files only", style="bold"), Text("-n, --dry-run", style="cyan")
    )

    body = Table.grid()
    body.add_row(
        Text("Fixes overwrite your original fonts by default. There is no backup.")
    )
    body.add_row("")
    body.add_row(grid)

    return Panel.fit(
        body,
        title="[bold yellow]Heads up[/]",
        title_align="left",
        border_style="yellow",
        padding=(0, 2),
    )


class RichHelp(argparse.Action):
    """-h/--help that shows argparse help with the safety panel after the description."""

    def __init__(
        self,
        option_strings,
        dest=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        help=None,
        console: Optional[Console] = None,
    ):
        super().__init__(
            option_strings, dest=dest, default=default, nargs=0, help=help
        )
        self._console = console

    def __call__(self, parser, namespace, values, option_string=None):
        console = self._console or Console()
        text = parser.format_help()
        desc = parser.description or ""

        head, found, tail = text.partition(desc) if desc else (text, "", "")
        if found:
            console.out(head + found, highlight=False)
            console.print()
            console.print(safety_panel())
            console.print()
            console.out(tail.lstrip("\n"), highlight=False, end="")
        else:
            console.print(safety_panel())
            console.out(text, highlight=False, end="")
        parser.exit()
