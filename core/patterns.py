"""Regular expressions used by Sortify Pro.

Patterns
    * :data:`DATE_IN_NAME_RE`  - extracts a date from a file name
      (named groups ``year``, ``month``, ``day``),
    * :data:`COPY_SUFFIX_RE`   - recognises "copy" markers such as
      ``photo (1)`` or ``photo - Kopia`` (named groups ``base``, ``marker``),
    * :data:`SIZE_RE`          - validates a human written size such as
      ``2 MB`` (named groups ``value``, ``unit``).

Every pattern is a raw string and is compiled once.
"""
from __future__ import annotations

import re
from datetime import date

# Files frequently carry the capture date in the name: IMG_20240315_101500.jpg,
# 2024-03-15 trip.png, photo_2024.03.15.jpg ...
DATE_IN_NAME_RE = re.compile(
    r"""
    (?<!\d)                                  # not in the middle of a number
    (?P<year>(?:19|20)\d{2})
    [-_.]?
    (?P<month>0[1-9]|1[0-2])
    [-_.]?
    (?P<day>0[1-9]|[12]\d|3[01])
    (?!\d)
    """,
    re.VERBOSE,
)

# "report (1)", "report - Kopia", "report - Copy (2)", "report_copy3"
COPY_SUFFIX_RE = re.compile(
    r"""
    ^(?P<base>.+?)
    (?P<marker>
        \s*-\s*(?:kopia|copy)(?:\s*\(\d+\))?
      | \s*\(\d+\)
      | _(?:kopia|copy)\d*
    )$
    """,
    re.VERBOSE | re.IGNORECASE,
)

SIZE_RE = re.compile(
    r"\s*(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>[KMGT]?B?)\s*",
    re.IGNORECASE,
)

#: Files that are never interesting for duplicate / space analysis.
DEFAULT_EXCLUDE_PATTERN = r"^(thumbs\.db|desktop\.ini|\.ds_store)$"

_UNIT_FACTORS = {
    "": 1, "B": 1,
    "K": 1024, "KB": 1024,
    "M": 1024**2, "MB": 1024**2,
    "G": 1024**3, "GB": 1024**3,
    "T": 1024**4, "TB": 1024**4,
}


def extract_date(filename: str) -> date | None:
    """Return the first *valid* calendar date found in ``filename``.

    ``None`` is returned when there is no date or it is impossible
    (for example ``20240231``).
    """
    for match in DATE_IN_NAME_RE.finditer(filename):
        try:
            return date(
                int(match["year"]), int(match["month"]), int(match["day"])
            )
        except ValueError:
            continue
    return None


def is_copy_name(stem: str) -> bool:
    """Return ``True`` if a file stem looks like an automatically made copy."""
    return COPY_SUFFIX_RE.fullmatch(stem) is not None


def original_stem(stem: str) -> str:
    """Strip a trailing copy marker: ``"photo (1)"`` -> ``"photo"``."""
    match = COPY_SUFFIX_RE.fullmatch(stem)
    return match["base"] if match else stem


def parse_size(text: str) -> int:
    """Parse ``"500"``, ``"2 MB"`` or ``"1,5 GB"`` into a number of bytes.

    Raises:
        ValueError: the text is not a valid size.
    """
    match = SIZE_RE.fullmatch(text)
    if match is None:
        raise ValueError(
            f"Nieprawidłowy rozmiar: {text.strip()!r} (przykład: 500 KB, 2 MB)"
        )
    value = float(match["value"].replace(",", "."))
    return int(value * _UNIT_FACTORS[match["unit"].upper()])


def compile_exclude_pattern(text: str) -> re.Pattern[str] | None:
    """Compile a user supplied "exclude file names" pattern.

    An empty text means "exclude nothing" and returns ``None``.

    Raises:
        ValueError: the text is not a valid regular expression.
    """
    text = text.strip()
    if not text:
        return None
    try:
        return re.compile(text, re.IGNORECASE)
    except re.error as error:
        raise ValueError(f"Nieprawidłowe wyrażenie regularne: {error}") from error
