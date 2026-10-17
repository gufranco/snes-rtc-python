from __future__ import annotations

import re
import unicodedata
from typing import Any

DASHES = (0x2013, 0x2014, 0x2212)

SINGLES = (0x2018, 0x2019, 0x2032)

DOUBLES = (0x201C, 0x201D)

RECOGNISED = "recognisedAs"

RECOGNISER_SLIPS = 2


def flatten(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    for code in DASHES:
        text = text.replace(chr(code), "-")
    for code in SINGLES:
        text = text.replace(chr(code), "'")
    for code in DOUBLES:
        text = text.replace(chr(code), '"')
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def close_reading(quote: str, reading: Any) -> bool:
    if not isinstance(reading, list) or not all(isinstance(one, str) for one in reading):
        return False
    wanted, read = flatten(quote), flatten(" ".join(reading))
    slips = sum(1 for one, other in zip(wanted, read, strict=False) if one != other)
    return bool(reading) and len(wanted) == len(read) and slips <= RECOGNISER_SLIPS
