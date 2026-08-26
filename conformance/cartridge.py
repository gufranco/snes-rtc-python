"""Read the clock routine out of the one cartridge that carries this part.

Every disagreement this package records against the reference is a place where
the manufacturer's manual says one thing and an emulator does another, and the
package follows the manual. Two of them named a way to settle the question that
is not a logic analyser: read what the shipped program actually does.

That is what this does. The cartridge is ordinary 65816 code and nothing here
runs any of it. What it finds is the routine that moves one nibble to the part,
every caller of that routine whose index and value are constants, and which
control-register bits those values set.

**Why the search is sound.** The part answers at three fixed addresses, and an
absolute access to one of them is unambiguous whatever the data bank holds. The
oracle was calibrated before it was used: the cartridge carrying the clock makes
seventy eight such accesses, and two cartridges carrying the same decompressor
without a clock make none at all.

**What is recorded.** The sequence of index and value pairs, the control bits
they set, and four digests of the cartridge. No cartridge byte is carried here.

Usage: python3 conformance/cartridge.py <cartridge> <out.json>
"""

import collections
import hashlib
import json
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
"""`sei` `tay` `lda #$01` `sta $4840`, which is how the write routine begins.

Four instructions rather than one byte, because a single opcode occurs everywhere
and this sequence occurs once. What it says is the routine's whole contract: it
runs with interrupts off, takes the value in the accumulator and the index in X,
and opens a session before doing anything else.
"""

CALL_LONG = 0x22

LOAD_X_IMMEDIATE = 0xA2

LOAD_A_IMMEDIATE = 0xA9

CONTROL_NAMES = {0x0D: "CD", 0x0E: "CE", 0x0F: "CF"}

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
    """The four a manifest publishes, so a reader can cross-check any of them."""
    return {
        "crc32": f"{zlib.crc32(image):08x}",
        "md5": hashlib.md5(image).hexdigest(),
        "sha1": hashlib.sha1(image).hexdigest(),
        "sha256": hashlib.sha256(image).hexdigest(),
    }


def touching(image: bytes) -> dict[tuple[int, str], int]:
    """Every absolute access to one of the three addresses the part answers at."""
    found: collections.Counter[tuple[int, str]] = collections.Counter()
    for at in range(len(image) - 2):
        if image[at] not in (STORE_ABSOLUTE, LOAD_ABSOLUTE):
            continue
        address = image[at + 1] | image[at + 2] << 8
        if address in PORTS:
            found[(address, "write" if image[at] == STORE_ABSOLUTE else "read")] += 1
    return dict(found)


def write_routine(image: bytes) -> int | None:
    """Where the routine that moves one nibble to the part begins."""
    at = image.find(OPENING)
    return at if at >= 0 else None


def written(image: bytes, where: int) -> list[tuple[int, int]]:
    """Every call to that routine whose index and value are both constants.

    A caller sets the index in X and the value in the accumulator, both with an
    immediate load, and then calls. A caller that computes either is passed over
    rather than guessed at: this reports what the program certainly writes, never
    what it might.

    The index load is two bytes or three depending on the width the index
    register is carrying, which is not in the instruction, so both are tried. The
    value load is always two, because the routine takes the value in the
    accumulator one byte at a time.
    """
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


def controls(pairs: "Sequence[tuple[int, int]]") -> list[dict[str, Any]]:
    """Which control registers those writes reach, and which bits they set."""
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
    """The reading this repository carries, or nothing if it is not there."""
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
