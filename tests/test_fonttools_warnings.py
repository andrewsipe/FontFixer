"""fontTools writes its warnings as a font is read; FontFixer collects them so each one is reported under its own font."""

import logging

from support.utilities import capture_fonttools_warnings


def test_a_fonttools_warning_is_collected_not_printed(capfd):
    with capture_fonttools_warnings() as warnings:
        logging.getLogger("fontTools.ttLib.tables._v_m_t_x").warning("Glyph 'space' has a huge advance height (63100)")
    assert warnings == ["Glyph 'space' has a huge advance height (63100)"]
    assert "huge advance" not in capfd.readouterr().err


def test_a_repeated_warning_is_listed_once_with_its_count():
    with capture_fonttools_warnings() as warnings:
        for _ in range(3):
            logging.getLogger("fontTools.ttLib").warning("Coverage is not sorted")
    assert warnings == ["Coverage is not sorted (x3)"]


def test_logging_is_restored_afterwards():
    logger = logging.getLogger("fontTools")
    before = (list(logger.handlers), logger.propagate)
    with capture_fonttools_warnings():
        pass
    assert (list(logger.handlers), logger.propagate) == before
