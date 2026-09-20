"""Rich-styled --help for FontFixer.

Everything below the argparse options (safety panel, handlers, examples, exit
status, docs) is rendered with Rich so it matches the argparse section instead
of looking like leftover plain text. Uses named ANSI colors (not hex) so it
follows the terminal theme, same as argparse's own coloring.
"""

from __future__ import annotations

import argparse
from typing import Iterable, Mapping, Optional, Sequence

from rich.console import Console, Group, RenderableType
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# One place to retheme. Named ANSI colors so they track the terminal palette.
HEADING = "bold blue"  # matches argparse's "options:" style headings
FLAG = "bold green"  # flags and handler names
PROG = "bold magenta"  # program name in example commands
OK, BAD = "green", "red"
INDENT = (0, 0, 0, 2)  # Padding: 2 columns, like argparse sections


def _heading(title: str, note: str = "") -> Text:
    label = f"{title} ({note}):" if note else f"{title}:"
    return Text(label, style=HEADING)


def _grid() -> Table:
    grid = Table.grid(padding=(0, 2))
    grid.add_column(no_wrap=True)
    grid.add_column()  # wraps to terminal width instead of ragged overflow
    return grid


def _section(title: str, body: RenderableType, note: str = "") -> RenderableType:
    return Group(_heading(title, note), Padding(body, INDENT, expand=False))


def safety_panel() -> Panel:
    grid = _grid()
    grid.add_row(Text("Keep originals", style="bold"), Text("-o DIR", style=FLAG))
    grid.add_row(
        Text("Inspect fonts, fix nothing", style="bold"),
        Text("--validate-only", style=FLAG),
    )
    grid.add_row(
        Text("List files only", style="bold"), Text("-n, --dry-run", style=FLAG)
    )

    body = Table.grid()
    body.add_row(
        Text("Fixes overwrite your original fonts by default. There is no backup.")
    )
    body.add_row("")
    body.add_row(grid)
    return Panel.fit(
        body,
        title=Text("Heads up", style="bold yellow"),
        title_align="left",
        border_style="yellow",
        padding=(0, 2),
    )


def handlers_section(
    handlers: Mapping[str, str], note: str = ""
) -> RenderableType:
    grid = _grid()
    for name, desc in handlers.items():
        grid.add_row(Text(name, style=FLAG), Text(desc))
    return _section("handlers", grid, note)


def _command(cmd: str) -> Text:
    out = Text()
    for i, tok in enumerate(cmd.split(" ")):
        if i:
            out.append(" ")
        style = PROG if i == 0 else FLAG if tok.startswith("-") else ""
        out.append(tok, style=style)
    return out


def examples_section(examples: Iterable[tuple[str, str]]) -> RenderableType:
    grid = _grid()
    for cmd, desc in examples:
        grid.add_row(_command(cmd), Text(desc, style="dim"))
    return _section("examples", grid)


def exit_status_section(codes: Mapping[str, str]) -> RenderableType:
    grid = _grid()
    for code, desc in codes.items():
        grid.add_row(Text(code, style=OK if code == "0" else BAD), Text(desc))
    return _section("exit status", grid)


def docs_section(url: str) -> RenderableType:
    line = Text()
    line.append("docs: ", style=HEADING)
    line.append(url, style=f"underline link {url}")
    return line


class RichHelp(argparse.Action):
    """-h/--help with safety panel after description, then Rich footer sections."""

    def __init__(
        self,
        option_strings,
        dest=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        help=None,
        console: Optional[Console] = None,
        footer: Sequence[RenderableType] = (),
        panel: Optional[RenderableType] = None,
    ):
        super().__init__(
            option_strings, dest=dest, default=default, nargs=0, help=help
        )
        self._console = console
        self._footer = list(footer)
        self._panel = panel

    def __call__(self, parser, namespace, values, option_string=None):
        console = self._console or Console()
        panel = self._panel if self._panel is not None else safety_panel()
        text = parser.format_help()
        desc = parser.description or ""

        # out() prints raw text: no markup parsing (so "[-o DIR]" is safe).
        head, found, tail = text.partition(desc) if desc else (text, "", "")
        if found:
            console.out(head + found, highlight=False)
            console.print()
            console.print(panel)
            console.print()
            console.out(tail.lstrip("\n"), highlight=False, end="")
        else:
            console.print(panel)
            console.print()
            console.out(text, highlight=False, end="")

        for section in self._footer:
            console.print()
            console.print(section)
        parser.exit()
