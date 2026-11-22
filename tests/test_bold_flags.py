"""The BOLD flags follow the word Bold in the style, not usWeightClass.

fontnameid sets Bold only for the word Bold and ignores usWeightClass (it is not always 700: a Semibold is often
700 too). FontFixer must agree, or running FontFixer after fontnameid brings the flags back.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).parent))
from test_oblique_flags import FS_BOLD, FS_ITALIC, ROOT, _font  # noqa: E402


def _flags_after_fix(path: Path, *, weight: int, fs_bold_set: bool) -> tuple[int, int]:
    f = TTFont(path, recalcTimestamp=False)
    f["OS/2"].usWeightClass = weight
    if fs_bold_set:
        f["OS/2"].fsSelection |= FS_BOLD
        f["head"].macStyle |= 1
    f.save(path)
    subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, %r); from FontFixer.main import main; sys.argv=['fontfixer','--handlers','style',%r]; main()" % (str(ROOT.parent), str(path))],
        capture_output=True, text=True, timeout=120,
    )
    g = TTFont(path, recalcTimestamp=False)
    return g["OS/2"].fsSelection, g["head"].macStyle


@pytest.mark.parametrize("style", ["Semibold", "Ultrabold", "Regular", "Black"])
def test_weight_700_without_the_word_bold_clears_bold(tmp_path, style):
    fs, mac = _flags_after_fix(_font(tmp_path / "a.ttf", style), weight=700, fs_bold_set=True)
    assert not fs & FS_BOLD and not mac & 1


@pytest.mark.parametrize("weight", [400, 700])
def test_the_word_bold_sets_bold_whatever_the_weight(tmp_path, weight):
    fs, mac = _flags_after_fix(_font(tmp_path / "a.ttf", "Bold"), weight=weight, fs_bold_set=False)
    assert fs & FS_BOLD and mac & 1


def test_bold_italic(tmp_path):
    fs, mac = _flags_after_fix(_font(tmp_path / "a.ttf", "Bold Italic"), weight=700, fs_bold_set=False)
    assert fs & FS_BOLD and fs & FS_ITALIC and mac == 3


def test_a_leftover_mac_record_does_not_decide_bold(tmp_path):
    path = _font(tmp_path / "a.ttf", "Semibold")
    f = TTFont(path, recalcTimestamp=False)
    f["name"].setName("Semi Bold", 2, 1, 0, 0)  # Mac record, left over from an old tool
    f.save(path)
    fs, mac = _flags_after_fix(path, weight=600, fs_bold_set=True)
    assert not fs & FS_BOLD and not mac & 1
