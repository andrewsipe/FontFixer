"""The family-wide slope decision settles the italic flag; the analyzer otherwise follows names and tables."""

import os
import sys
from pathlib import Path

import pytest
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from FontFixer.support.style_analyzer import FontStyleAnalyzer, set_slope_decisions  # noqa: E402
from tests.test_italic_angle import font  # noqa: E402


@pytest.fixture(autouse=True)
def clear_decisions():
    yield
    set_slope_decisions({})


def saved(tmp_path, style="Regular", name="Probe-Regular.ttf"):
    f = font(style=style)
    path = tmp_path / name
    f.save(path)
    return TTFont(path), os.path.abspath(path)


def test_an_upright_decision_clears_the_italic_flags_a_stale_name_would_set(tmp_path):
    f, path = saved(tmp_path, style="Italic")
    assert FontStyleAnalyzer(f).is_italic  # the name alone says italic
    set_slope_decisions({path: "upright"})
    a = FontStyleAnalyzer(f)
    assert not a.is_italic and not a.is_oblique


def test_an_italic_decision_sets_the_italic_flag_when_the_names_say_nothing(tmp_path):
    f, path = saved(tmp_path, style="Regular")
    assert not FontStyleAnalyzer(f).is_italic
    set_slope_decisions({path: "italic"})
    assert FontStyleAnalyzer(f).is_italic


def test_a_font_with_no_decision_follows_its_names(tmp_path):
    f, _ = saved(tmp_path, style="Italic")
    set_slope_decisions({"/somewhere/else.ttf": "upright"})
    assert FontStyleAnalyzer(f).is_italic
