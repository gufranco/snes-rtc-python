import collections
import hashlib
import json
import re
import sys
import zlib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from snesrtc import epson

ROOT = Path(__file__).resolve().parent

RECORDED = "cartridge.json"

PORTS = {epson.ENABLE: "ENABLE", epson.DATA: "DATA", epson.STATUS: "STATUS"}

STORE_ABSOLUTE = 0x8D

LOAD_ABSOLUTE = 0xAD

OPENING = bytes((0x78, 0xA8, 0xA9, 0x01, 0x8D, 0x40, 0x48))

CALL_LONG = 0x22

LOAD_X_IMMEDIATE = 0xA2

LOAD_A_IMMEDIATE = 0xA9

CONTROL_NAMES = {0x0D: "CD", 0x0E: "CE", 0x0F: "CF"}

DATA_STORES = (0x8D, 0x8E, 0x8C, 0x9C)

CLOSING = bytes((LOAD_A_IMMEDIATE, 0x00, STORE_ABSOLUTE, 0x40, 0x48))

SESSION_REACH = 0x80

YEAR_FOLD = re.compile(rb"\x85\x00\x38\xe9(.)\xb0\x05\xa5\x00\x18\x69(.)\x18\x69(.)\x60", re.S)

YEAR_BASE = re.compile(rb"\xc2\x20\x29\xff\x00\x18\x69(..)", re.S)

LOAD_LONG_X = 0xBF

PUSH_X = 0xDA

CLOCK_DIGITS = 13

CENTURY = 100

HIROM_BANK = 0x3F

CONTROL_BITS: dict[str, tuple[tuple[int, str], ...]] = {
    "CD": (
        (epson.HOLD, "HOLD"),
        (epson.CAL_HW, "CAL_HW"),
        (epson.IRQ_F, "IRQ_F"),
        (epson.ADJUST, "ADJUST"),
    ),
    "CE": (),
    "CF": (
        (epson.RESET, "RESET"),
        (epson.STOP, "STOP"),
        (epson.HOURS_24, "HOURS_24"),
        (epson.TEST, "TEST"),
    ),
}


def digests_of(image: bytes) -> dict[str, str]:
    return {
        "crc32": f"{zlib.crc32(image):08x}",
        "md5": hashlib.md5(image).hexdigest(),
        "sha1": hashlib.sha1(image).hexdigest(),
        "sha256": hashlib.sha256(image).hexdigest(),
    }


def touching(image: bytes) -> dict[tuple[int, str], int]:
    found: collections.Counter[tuple[int, str]] = collections.Counter()
    for at in range(len(image) - 2):
        if image[at] not in (STORE_ABSOLUTE, LOAD_ABSOLUTE):
            continue
        address = image[at + 1] | image[at + 2] << 8
        if address in PORTS:
            found[(address, "write" if image[at] == STORE_ABSOLUTE else "read")] += 1
    return dict(found)


def write_routine(image: bytes) -> int | None:
    at = image.find(OPENING)
    return at if at >= 0 else None


def written(image: bytes, where: int) -> list[tuple[int, int]]:
    target = bytes((CALL_LONG, where & 0xFF, (where >> 8) & 0xFF, 0xC0))
    found = []
    for at in range(len(image) - len(target)):
        if image[at : at + len(target)] != target:
            continue
        if at < 5 or image[at - 2] != LOAD_A_IMMEDIATE:
            continue
        for back in (4, 5):
            if image[at - back] == LOAD_X_IMMEDIATE:
                found.append((image[at - back + 1], image[at - 1]))
                break
    return found


def opening(mode: int) -> bytes:
    return bytes((LOAD_A_IMMEDIATE, mode, STORE_ABSOLUTE, 0x41, 0x48))


def data_stores(span: bytes) -> int:
    return sum(
        1
        for at in range(len(span) - 2)
        if span[at] in DATA_STORES and span[at + 1 : at + 3] == bytes((0x41, 0x48))
    )


def openings(image: bytes, mode: int) -> list[int]:
    found = []
    start = image.find(opening(mode))
    while start >= 0:
        found.append(start)
        start = image.find(opening(mode), start + 1)
    return found


def sessions(image: bytes, mode: int) -> list[dict[str, int]]:
    found = []
    for start in openings(image, mode):
        close = image.find(CLOSING, start, start + SESSION_REACH)
        if close >= 0:
            span = image[start + len(opening(mode)) : close]
            found.append({"at": start, "dataWrites": data_stores(span)})
    return found


def unclosed(image: bytes, mode: int) -> int:
    return len(openings(image, mode)) - len(sessions(image, mode))


def reading(digits: "Sequence[int]", window: dict[str, int]) -> str:
    def pair(at: int) -> int:
        return digits[at] + digits[at + 1] * 10

    year = pair(epson.Y1)
    year += window["base"] + (0 if year >= window["pivot"] else CENTURY)
    return (
        f"{year:04d}-{pair(epson.MO1):02d}-{pair(epson.D1):02d}"
        f" {pair(epson.H1):02d}:{pair(epson.MI1):02d}:{pair(epson.S1):02d}"
    )


def findings(image: bytes, where: int) -> dict[str, Any]:
    window = century(image)
    digits = loaded(image, where)
    found: dict[str, Any] = {
        "readSessions": [
            {"at": f"{one['at']:#08x}", "dataWrites": one["dataWrites"]}
            for one in sessions(image, epson.READ_MODE)
        ],
        "unclosedOpenings": {
            "read": unclosed(image, epson.READ_MODE),
            "write": unclosed(image, epson.WRITE_MODE),
        },
        "century": None if window is None else {**window, "foldAt": f"{window['foldAt']:#08x}"},
    }
    if digits is not None and window is not None:
        found["loadedOnInitialisation"] = {"digits": digits, "reads": reading(digits, window)}
    return found


def century(image: bytes) -> dict[str, int] | None:
    fold = YEAR_FOLD.search(image)
    if fold is None:
        return None
    pivot, carry, again = (one[0] for one in fold.groups())
    base = YEAR_BASE.match(image, fold.end())
    if base is None or again != pivot or pivot + carry != CENTURY:
        return None
    first = int.from_bytes(base.group(1), "little")
    return {
        "foldAt": fold.start(),
        "pivot": pivot,
        "base": first,
        "first": first + pivot,
        "last": first + CENTURY + pivot - 1,
    }


def loaded(image: bytes, where: int) -> list[int] | None:
    call = bytes((PUSH_X, CALL_LONG, where & 0xFF, (where >> 8) & 0xFF, 0xC0))
    at = image.find(call)
    if at < 4 or image[at - 4] != LOAD_LONG_X:
        return None
    table = ((image[at - 1] & HIROM_BANK) << 16) | image[at - 2] << 8 | image[at - 3]
    return list(image[table : table + CLOCK_DIGITS])


def controls(pairs: "Sequence[tuple[int, int]]") -> list[dict[str, Any]]:
    said = []
    for index, value in pairs:
        name = CONTROL_NAMES.get(index)
        if name is None:
            continue
        said.append(
            {
                "register": name,
                "value": f"{value:#04x}",
                "bits": [bit for mask, bit in CONTROL_BITS[name] if value & mask],
            }
        )
    return said


def recorded(where: Path | str | None = None) -> dict[str, Any]:
    path = Path(where) if where is not None else ROOT / RECORDED
    if not path.is_file():
        return {}
    found: dict[str, Any] = json.loads(path.read_text())
    return found


def main(argv: Sequence[str], say: Callable[[str], object] = print) -> int:
    if len(argv) < 2:
        say("usage: cartridge.py <cartridge> <out.json>")
        return 2

    source, out = Path(argv[0]), Path(argv[1])
    if not source.is_file():
        say(f"  no such file: {source}")
        return 2

    image = source.read_bytes()
    where = write_routine(image)
    if where is None:
        say(f"  no clock routine was found in {source.name}")
        return 1

    pairs = written(image, where)
    named = controls(pairs)
    found: dict[str, Any] = {
        "note": (
            "What the shipped program does to the clock, read out of its own code "
            "without running any of it. No cartridge byte is recorded here."
        ),
        "readFrom": {"name": source.name, "bytes": len(image), **digests_of(image)},
        "routineAt": f"{where:#08x}",
        "ports": {
            f"{address:#06x} {kind}": count
            for (address, kind), count in sorted(touching(image).items())
        },
        "modes": {"write": f"{epson.WRITE_MODE:#04x}", "read": f"{epson.READ_MODE:#04x}"},
        "writes": [{"index": f"{index:#04x}", "value": f"{value:#04x}"} for index, value in pairs],
        "controls": named,
        **findings(image, where),
    }
    out.write_text(json.dumps(found, indent=2) + "\n")

    say(
        f"  clock routine at {where:#08x}; {len(pairs)} constant writes,"
        f" {len(named)} of them to a control register"
    )
    for one in named:
        bits = one["bits"]
        assert isinstance(bits, list)
        say(f"    {one['register']} = {one['value']}  {' '.join(bits) or 'nothing set'}")
    summarise(found, say)
    return 0


def summarise(found: dict[str, Any], say: Callable[[str], object]) -> None:
    writes = sorted({one["dataWrites"] for one in found["readSessions"]})
    say(f"  {len(found['readSessions'])} read sessions, data writes in each: {writes}")
    window = found["century"]
    if window is None:
        say("  no year fold was found")
        return
    say(f"  years read as {window['first']} to {window['last']}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
