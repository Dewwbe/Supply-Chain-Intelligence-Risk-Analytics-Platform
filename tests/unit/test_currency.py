import pytest
from etl.transform.currency import convert_to_aed


def test_convert_usd_uses_official_peg():
    assert convert_to_aed(100, "USD") == pytest.approx(367.25)


def test_convert_aed_is_identity():
    assert convert_to_aed(50, "AED") == 50


def test_convert_brl_uses_configured_rate():
    assert convert_to_aed(100, "BRL") == pytest.approx(99.0)


def test_unknown_currency_raises():
    with pytest.raises(ValueError, match="XYZ"):
        convert_to_aed(10, "XYZ")
