"""nameID 2 follows the italic flags when FontFixer changes them, and the family slant review does not read the free-slope marker as italic."""

from fontTools.ttLib import TTFont

from support.family_slant_review import apply_family_flag_fix, build_review_report
from tests.test_variable_flags import _fix, _variable

FS_ITALIC = 0x01


def _name(path, name_id=2):
    return TTFont(path, recalcTimestamp=False)["name"].getDebugName(name_id)


def test_the_style_handler_writes_nameid_2_with_the_flags(tmp_path):
    path = _variable(tmp_path / "Probe-VariableItalic.ttf", italic_bits=False, stat_ital=1)
    font = TTFont(path, recalcTimestamp=False)
    font["post"].italicAngle = -12.0
    font.save(path)
    fs, _ = _fix(path)
    assert fs & FS_ITALIC and _name(path) == "Italic"


def _marked_free(path):
    font = TTFont(path, recalcTimestamp=False)
    font["name"].setName("Upright Italic", 17, 3, 1, 0x409)
    font.save(path)


def test_the_review_does_not_read_the_free_slope_marker_as_italic(tmp_path):
    upright = _variable(tmp_path / "Probe-VariableUpright.ttf", italic_bits=False)
    italic = _variable(tmp_path / "Probe-VariableItalic.ttf", italic_bits=True)
    free = _variable(tmp_path / "Probe-Variable.ttf", italic_bits=False)
    _marked_free(free)
    report = build_review_report([upright, italic, free])
    assert not report.recommended, [(r.family_key, [f.path.name for f in r.fixes]) for r in report.recommended]


def test_applying_a_slant_fix_writes_nameid_2(tmp_path):
    from support.family_slant_review import FamilyFlagFix

    path = _variable(tmp_path / "Probe-VariableItalic.ttf", italic_bits=False)
    fix = FamilyFlagFix(path=path, style_label="Regular", measured_angle=-12.0, set_italic=True, set_oblique=False,
                        clear_slant_flags=False, note="")
    assert apply_family_flag_fix(fix) and _name(path) == "Italic"
