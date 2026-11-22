"""Style flags follow the label: Oblique is slanted, so it gets ITALIC as well as OBLIQUE.

fontnameid gives an Oblique-named face ID2 Italic and sets fsSelection ITALIC and macStyle italic. FontFixer
must write the same flags, or the two tools undo each other. A face named Regular keeps Regular flags
whatever its angle (Italic is a linked alternative to a Regular; a script is not an Italic).
"""

import subprocess
import sys
from pathlib import Path

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
FS_ITALIC, FS_BOLD, FS_REGULAR, FS_OBLIQUE = 0x01, 0x20, 0x40, 0x200


def _font(path: Path, style: str, *, version=4, angle=0.0) -> Path:
    fb = FontBuilder(1000, isTTF=True)
    order = [".notdef", "H"]
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({72: "H"})
    pen = TTGlyphPen(None)
    for pt in ((50, 0), (50, 700), (450, 700), (450, 0)):
        (pen.moveTo if pt == (50, 0) else pen.lineTo)(pt)
    pen.closePath()
    fb.setupGlyf({".notdef": pen.glyph(), "H": pen.glyph()})
    fb.setupHorizontalMetrics({g: (500, 50) for g in order})
    fb.setupHorizontalHeader(ascent=900, descent=-250)
    fb.setupNameTable({"familyName": "Probe", "styleName": style})
    fb.setupOS2(version=version)
    fb.setupPost()
    fb.font["post"].italicAngle = angle
    fb.font["head"].modified = 3_000_000_000
    fb.save(path)
    return path


def _fix(path: Path) -> tuple[int, int]:
    result = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, %r); from FontFixer.main import main; sys.argv=['fontfixer','--handlers','style',%r]; main()" % (str(ROOT.parent), str(path))],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode in (0, 1), result.stdout[-500:] + result.stderr[-500:]
    f = TTFont(path, recalcTimestamp=False)
    return f["OS/2"].fsSelection, f["head"].macStyle


@pytest.mark.parametrize("version", [4, 3])
def test_an_oblique_name_sets_italic_and_macstyle(tmp_path, version):
    fs, mac = _fix(_font(tmp_path / "a.ttf", "Oblique", version=version))
    assert fs & FS_ITALIC and mac & 2
    assert not fs & FS_REGULAR
    assert bool(fs & FS_OBLIQUE) == (version >= 4)  # the bit exists only from OS/2 v4


def test_bold_oblique_sets_bold_italic(tmp_path):
    fs, mac = _fix(_font(tmp_path / "a.ttf", "Bold Oblique"))
    assert fs & FS_ITALIC and fs & FS_BOLD and fs & FS_OBLIQUE and mac == 3


def test_an_italic_name_sets_italic_but_not_oblique(tmp_path):
    fs, mac = _fix(_font(tmp_path / "a.ttf", "Italic"))
    assert fs & FS_ITALIC and not fs & FS_OBLIQUE and mac & 2


def test_a_slanted_font_named_regular_keeps_regular_flags(tmp_path):
    fs, mac = _fix(_font(tmp_path / "a.ttf", "Regular", angle=-9.0))
    assert not fs & FS_ITALIC and not mac & 2
