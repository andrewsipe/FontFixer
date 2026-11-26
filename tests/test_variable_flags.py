"""A variable font's italic flags follow the tables' slope decision, not the names alone (DECISIONS.md, Area 5)."""

import subprocess
import sys
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
FS_ITALIC, FS_REGULAR = 0x01, 0x40


def _variable(path: Path, *, italic_bits: bool, stat_ital=None, style="Regular") -> Path:
    fb = FontBuilder(1000, isTTF=True)
    order = [".notdef", "H"]
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({72: "H"})
    pen = TTGlyphPen(None)
    for i, pt in enumerate(((50, 0), (50, 700), (450, 700), (450, 0))):
        (pen.moveTo if i == 0 else pen.lineTo)(pt)
    pen.closePath()
    fb.setupGlyf({".notdef": pen.glyph(), "H": pen.glyph()})
    fb.setupHorizontalMetrics({g: (500, 50) for g in order})
    fb.setupHorizontalHeader(ascent=900, descent=-250)
    fb.setupNameTable({"familyName": "Probe", "styleName": style})
    fb.setupOS2(version=4)
    fb.setupPost()
    fb.setupFvar([("wght", 100, 400, 900, "Weight")], [])
    if stat_ital is not None:
        fb.setupStat([dict(tag="ital", name="Italic", ordering=0), dict(tag="wght", name="Weight", ordering=1)],
                     [dict(location={"ital": stat_ital}, name="Italic" if stat_ital else "Roman")])
    font = fb.font
    if italic_bits:
        font["OS/2"].fsSelection = (font["OS/2"].fsSelection & ~FS_REGULAR) | FS_ITALIC
        font["head"].macStyle |= 2
    font["post"].italicAngle = -12.0 if italic_bits else 0.0
    font["head"].modified = 3_000_000_000
    fb.save(path)
    return path


def _fix(path: Path):
    result = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, %r); from FontFixer.main import main; sys.argv=['fontfixer','--handlers','style',%r]; main()" % (str(ROOT.parent), str(path))],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode in (0, 1), result.stdout[-500:] + result.stderr[-500:]
    f = TTFont(path, recalcTimestamp=False)
    return f["OS/2"].fsSelection, f["head"].macStyle


def test_an_italic_variable_font_whose_names_do_not_say_italic_keeps_its_italic_flags(tmp_path):
    # STAT and the italic bits say italic; the names say Regular. The tables outvote the names.
    fs, mac = _fix(_variable(tmp_path / "Probe-Variable.ttf", italic_bits=True, stat_ital=1))
    assert fs & FS_ITALIC and mac & 2


def test_an_upright_variable_font_with_stray_italic_bits_is_made_regular(tmp_path):
    fs, mac = _fix(_variable(tmp_path / "Probe-Variable.ttf", italic_bits=True, stat_ital=0))
    assert not fs & FS_ITALIC and not mac & 2 and fs & FS_REGULAR


def test_a_static_font_still_follows_its_names(tmp_path):
    path = tmp_path / "Probe-Regular.ttf"
    _variable(path, italic_bits=True)
    f = TTFont(path)
    del f["fvar"]
    f.save(path)
    fs, mac = _fix(path)
    assert not fs & FS_ITALIC and not mac & 2  # names say Regular
