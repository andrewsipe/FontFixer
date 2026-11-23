"""With -j N, each font's messages stay together under its own header; nothing prints before the first header."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_oblique_flags import ROOT, _font  # noqa: E402


def run_fixer(folder: Path, *extra: str) -> str:
    code = (
        "import sys; sys.path.insert(0, %r); from FontFixer.main import main; "
        "sys.argv=['fontfixer', %s]; main()" % (str(ROOT.parent), ", ".join(repr(a) for a in (*extra, str(folder))))
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    return result.stdout + result.stderr


def blocks(text: str):
    """Split the per-file part of the output into [header, lines...] groups."""
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if "Processing with" in l)
    end = next((i for i, l in enumerate(lines) if "Finished" in l), len(lines))
    body = lines[start + 1 : end]
    groups, current, before = [], None, []
    for line in body:
        if re.search(r"\bPARSING\b", line):
            current = [line]
            groups.append(current)
        elif current is None:
            if line.strip():
                before.append(line)
        else:
            current.append(line)
    return before, groups


@pytest.fixture
def many_fonts(tmp_path):
    for i, style in enumerate(["Regular", "Bold", "Italic", "Oblique", "Light", "Black", "Thin", "Medium"]):
        _font(tmp_path / f"Probe{i}-{style}.ttf", style, version=3)
    return tmp_path


@pytest.mark.parametrize("jobs", ["2", "4"])
def test_nothing_prints_before_the_first_file_header(many_fonts, jobs):
    before, groups = blocks(run_fixer(many_fonts, "-j", jobs, "--handlers", "os2,style,glyph"))
    assert before == [], before[:5]
    assert len(groups) == 8


@pytest.mark.parametrize("jobs", ["1", "2", "4"])
def test_each_block_has_one_save_and_it_names_the_same_file(many_fonts, jobs):
    _, groups = blocks(run_fixer(many_fonts, "-j", jobs, "--handlers", "os2,style,glyph"))
    for g in groups:
        name = re.search(r"\|\s*(\S+\.ttf)", g[0]).group(1)
        saves = [l for l in g if "SAVED TO" in l]
        assert len(saves) == 1 and name in saves[0], g


def test_parallel_and_sequential_print_the_same_set_of_changes(many_fonts, tmp_path_factory):
    # same fonts, same handlers: the multiset of change lines must match whatever the worker count
    def change_lines(text):
        _, groups = blocks(text)
        return sorted(l.strip() for g in groups for l in g[1:] if l.strip().startswith(("-", "UPDATED", "NO CHANGE")))

    seq_dir = tmp_path_factory.mktemp("seq")
    par_dir = tmp_path_factory.mktemp("par")
    for i, style in enumerate(["Regular", "Bold", "Italic", "Oblique"]):
        _font(seq_dir / f"Probe{i}-{style}.ttf", style, version=3)
        _font(par_dir / f"Probe{i}-{style}.ttf", style, version=3)
    assert change_lines(run_fixer(seq_dir, "-j", "1")) == change_lines(run_fixer(par_dir, "-j", "3"))
