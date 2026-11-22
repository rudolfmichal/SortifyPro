from datetime import date

import pytest

from core.patterns import (
    COPY_SUFFIX_RE, DATE_IN_NAME_RE, SIZE_RE, compile_exclude_pattern,
    extract_date, is_copy_name, original_stem, parse_size,
)


@pytest.mark.parametrize("name,expected", [
    ("IMG_20240315_101010.jpg", date(2024, 3, 15)),
    ("raport_2023-05-17.pdf", date(2023, 5, 17)),
    ("scan.2022.12.01.png", date(2022, 12, 1)),
    ("bez_daty.txt", None),
    ("plik_20240231.txt", None),      # nie ma 31 lutego
    ("numer_1234567890123.txt", None),  # za długa liczba
])
def test_extract_date(name, expected):
    assert extract_date(name) == expected


def test_named_groups():
    m = DATE_IN_NAME_RE.search("x_2024-03-15")
    assert (m["year"], m["month"], m["day"]) == ("2024", "03", "15")
    m = COPY_SUFFIX_RE.fullmatch("faktura - Kopia (2)")
    assert m["base"] == "faktura" and "Kopia" in m["marker"]
    m = SIZE_RE.fullmatch("1,5 GB")
    assert m["value"] == "1,5" and m["unit"] == "GB"


@pytest.mark.parametrize("stem,copy,base", [
    ("foto (1)", True, "foto"),
    ("foto - Kopia", True, "foto"),
    ("foto - copy (3)", True, "foto"),
    ("foto_copy2", True, "foto"),
    ("foto", False, "foto"),
    ("foto (a)", False, "foto (a)"),
])
def test_copy_names(stem, copy, base):
    assert is_copy_name(stem) is copy
    assert original_stem(stem) == base


@pytest.mark.parametrize("text,expected", [
    ("500", 500), ("1 KB", 1024), ("2MB", 2 * 1024**2),
    ("1,5 GB", int(1.5 * 1024**3)), ("0.5 kb", 512),
])
def test_parse_size(text, expected):
    assert parse_size(text) == expected


@pytest.mark.parametrize("bad", ["", "abc", "-5 MB", "5 XB"])
def test_parse_size_invalid(bad):
    with pytest.raises(ValueError):
        parse_size(bad)


def test_compile_exclude_pattern():
    assert compile_exclude_pattern("") is None
    pattern = compile_exclude_pattern(r"^thumbs\.db$")
    assert pattern.search("thumbs.db")
    with pytest.raises(ValueError):
        compile_exclude_pattern("([")
