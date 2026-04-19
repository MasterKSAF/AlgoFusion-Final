from __future__ import annotations

from src.modules.runtime_money_words import (
    _format_money_words_ru,
    _money_words_need_rebuild,
    _trim_money_words_ocr_noise,
)


def test_format_money_words_ru() -> None:
    assert _format_money_words_ru(891.27) == "Восемьсот девяносто один руб. 27 коп"


def test_money_words_need_rebuild_on_latin_ocr_garbage() -> None:
    assert _money_words_need_rebuild("NOT TROUBLETEN STOKE руб. 10 KOIT", 891.27) is True


def test_trim_money_words_ocr_noise_after_kopecks() -> None:
    assert _trim_money_words_ocr_noise("Пятьдесят восемь руб. 85 коп 123") == "Пятьдесят восемь руб. 85 коп"
