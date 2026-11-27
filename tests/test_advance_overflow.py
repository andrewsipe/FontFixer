"""An advance stored as unsigned overflow (a negative value read back as 63100) is repaired from the font's own metrics."""

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from support.handlers.glyph_handler import GlyphHandler


def _font(vertical=False):
    fb = FontBuilder(1000, isTTF=True)
    order = [".notdef", "space", "uni00A0", "A", "B", "C"]
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({0x20: "space", 0xA0: "uni00A0", 65: "A", 66: "B", 67: "C"})
    pen = TTGlyphPen(None)
    for i, pt in enumerate(((50, 0), (50, 700), (450, 700), (450, 0))):
        (pen.moveTo if i == 0 else pen.lineTo)(pt)
    pen.closePath()
    glyph = pen.glyph()
    empty = TTGlyphPen(None).glyph()
    fb.setupGlyf({g: (empty if g in ("space", "uni00A0") else glyph) for g in order})
    fb.setupHorizontalMetrics({g: (250 if g in ("space", "uni00A0") else 600, 0) for g in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Probe", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    if vertical:
        fb.setupVerticalMetrics({g: (1000, 0) for g in order})
        fb.setupVerticalHeader(ascent=500, descent=-500)
    return fb.font


def _run(font):
    handler = GlyphHandler(font)
    handler.validate()
    return handler, handler.fix()


def test_a_clean_font_has_nothing_to_fix():
    handler, changed = _run(_font(vertical=True))
    assert handler.validations["advances_valid"]["valid"] and not changed


def test_an_overflowed_advance_height_gets_the_most_common_height():
    font = _font(vertical=True)
    font["vmtx"].metrics["space"] = (63100, 770)
    handler, changed = _run(font)
    assert changed and font["vmtx"].metrics["space"] == (1000, 770)  # the side bearing stays
    assert handler.changes["space_advance_height"]["old"] == 63100


def test_an_overflowed_space_width_takes_the_nbsp_width():
    font = _font()
    font["hmtx"].metrics["space"] = (65000, 0)
    _run(font)
    assert font["hmtx"].metrics["space"][0] == 250


def test_an_overflowed_letter_width_takes_the_median_width():
    font = _font()
    font["hmtx"].metrics["B"] = (64000, 0)
    _run(font)
    assert font["hmtx"].metrics["B"][0] == 600


def test_widths_the_font_really_has_are_left_alone():
    font = _font()
    font["hmtx"].metrics["A"] = (30000, 0)  # wide but not an overflow
    _, changed = _run(font)
    assert not changed and font["hmtx"].metrics["A"][0] == 30000
