import pytest
from scripts.prepare_db import _quoted_password


def test_quotes_plain_password() -> None:
    assert _quoted_password("simplepass123") == "'simplepass123'"


def test_escapes_single_quotes() -> None:
    assert _quoted_password("weird'pass") == "'weird''pass'"


def test_rejects_backslash() -> None:
    with pytest.raises(ValueError):
        _quoted_password("has\\backslash")


def test_rejects_nul_byte() -> None:
    with pytest.raises(ValueError):
        _quoted_password("has\x00nul")
