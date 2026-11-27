"""post.italicAngle is measured on vertical stems only.

The diagonal of an N leans left even in an upright font. Sampling it with H and I wrote a positive angle (around 7
degrees) on upright fonts, because H and I read as 0 and were dropped by the 2 degree floor, leaving N alone.
"""

import math
import sys
from pathlib import Path

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from FontFixer.support.style_analyzer import FontStyleAnalyzer  # noqa: E402

H = [(50, 0), (50, 700), (150, 700), (150, 400), (350, 400), (350, 700), (450, 700), (450, 0), (350, 0), (350, 300), (150, 300), (150, 0)]
I = [(50, 0), (50, 700), (150, 700), (150, 0)]
N = [(50, 0), (50, 700), (160, 700), (440, 230), (440, 700), (550, 700), (550, 0), (440, 0), (160, 470), (160, 0)]


def font(shear_degrees=0.0, glyphs=("H", "I", "N"), style="Regular") -> TTFont:
    shapes = {"H": H, "I": I, "N": N}
    fb = FontBuilder(1000, isTTF=True)
    order = [".notdef", *glyphs]
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({ord(g): g for g in glyphs})
    k = math.tan(math.radians(shear_degrees))
    built = {}
    for name in order:
        pen = TTGlyphPen(None)
        pts = shapes.get(name, I)
        for i, (x, y) in enumerate(pts):
            (pen.moveTo if i == 0 else pen.lineTo)((round(x + y * k), y))
        pen.closePath()
        built[name] = pen.glyph()
    fb.setupGlyf(built)
    fb.setupHorizontalMetrics({g: (700, 50) for g in order})
    fb.setupHorizontalHeader(ascent=900, descent=-250)
    fb.setupNameTable({"familyName": "Probe", "styleName": style})
    fb.setupOS2()
    fb.setupPost()
    return fb.font


def angle(f: TTFont) -> float:
    return FontStyleAnalyzer(f).italic_angle


def test_an_upright_font_measures_zero_even_though_n_has_a_diagonal():
    assert angle(font()) == 0.0


def test_an_upright_font_with_only_n_and_h_measures_zero():
    assert angle(font(glyphs=("H", "N"))) == 0.0


@pytest.mark.parametrize("degrees", [8.0, 12.0, 15.0])
def test_a_sheared_font_measures_its_angle_with_the_right_sign(degrees):
    measured = angle(font(shear_degrees=degrees, style="Italic"))
    assert measured == pytest.approx(-degrees, abs=0.6)  # forward lean is negative


def test_a_backslanted_font_measures_positive():
    assert angle(font(shear_degrees=-10.0, style="Backslanted")) == pytest.approx(10.0, abs=0.6)


def test_a_font_with_only_n_is_not_guessed_from_the_diagonal():
    assert angle(font(glyphs=("N",))) == 0.0


def test_a_named_italic_with_a_shallow_slant_keeps_its_stored_angle():
    f = font(shear_degrees=1.0, style="Italic")
    f["post"].italicAngle = -1.0
    assert angle(f) == pytest.approx(-1.0, abs=0.3)


# ---- H and I disagree: never average them into an angle neither glyph has ----------------------------------

def disagreeing(stored: float, h_shear=12.0, i_shear=31.0) -> TTFont:
    f = font(shear_degrees=h_shear, glyphs=("H", "I"), style="Italic")
    glyf = f["glyf"]
    k = math.tan(math.radians(i_shear))
    pen = TTGlyphPen(None)
    for i, (x, y) in enumerate(I):
        (pen.moveTo if i == 0 else pen.lineTo)((round(x + y * k), y))
    pen.closePath()
    glyf["I"] = pen.glyph()
    f["post"].italicAngle = stored
    return f


def test_when_h_and_i_disagree_the_one_nearest_the_stored_angle_wins():
    assert angle(disagreeing(stored=-12.0)) == pytest.approx(-12.0, abs=0.6)


def test_when_h_and_i_disagree_and_nothing_is_stored_h_wins():
    assert angle(disagreeing(stored=0.0)) == pytest.approx(-12.0, abs=0.6)


# ---- stale Italic names on an upright outline: the outlines decide -----------------------------------------

def test_an_upright_outline_with_stale_italic_names_loses_its_wrong_stored_angle():
    f = font(style="Italic")
    f["post"].italicAngle = 11.93
    assert angle(f) == 0.0


def test_a_real_italic_keeps_its_angle_when_the_names_say_italic():
    f = font(shear_degrees=9.0, style="Italic")
    f["post"].italicAngle = -9.0
    assert angle(f) == pytest.approx(-9.0, abs=0.6)


def test_an_italic_with_nothing_measurable_keeps_its_stored_angle():
    f = font(glyphs=("N",), style="Italic")
    f["post"].italicAngle = -9.0
    assert angle(f) == pytest.approx(-9.0, abs=0.1)
