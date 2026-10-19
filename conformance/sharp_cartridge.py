import json
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conformance.cartridge import digests_of

ROOT = Path(__file__).resolve().parent

RECORDED = "sharp_cartridge.json"

TAIL = rb"\xc2\x20\xee\x04\xe2\x60"

TO_PORT = rb"\x29\x0f\x8f\x01\x28\x00"

FROM_PORT = rb"\xaf\x00\x28\x00"

STEPS: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    ("command", re.compile(rb"\xe2\x20\xa9(.)" + TO_PORT + TAIL, re.S)),
    ("send", re.compile(rb"\xe2\x20\xad(..)" + TO_PORT + TAIL, re.S)),
    ("take", re.compile(rb"\xe2\x20" + FROM_PORT + rb"\x29\x0f\x8d(..)" + TAIL, re.S)),
    ("marker", re.compile(rb"\xe2\x20" + FROM_PORT + rb"\xc2\x20\x29\x0f\x00\xc9\x0f\x00")),
    ("wait", re.compile(TAIL)),
    ("finish", re.compile(rb"\xc2\x20\x9c\x00\xe2\x9c\x04\xe2\x60")),
    ("finish", re.compile(rb"\xc2\x20\x9c\x04\xe2\x60")),
    ("finish", re.compile(rb"\xc2\x20\x22...\x60", re.S)),
)

BLOCK = 0x10000

SHORTEST_TABLE = 8

DIGITS = ("send", "take")

Step = tuple[str, int]


def steps(image: bytes) -> dict[int, Step]:
    found: dict[int, Step] = {}
    for kind, pattern in STEPS:
        for hit in pattern.finditer(image):
            argument = int.from_bytes(hit.group(1), "little") if hit.groups() else 0
            found.setdefault(hit.start(), (kind, argument))
    return found


def run_at(image: bytes, at: int, known: dict[int, Step]) -> list[Step]:
    block = at & ~(BLOCK - 1)
    run = []
    while at + 1 < len(image):
        target = block | int.from_bytes(image[at : at + 2], "little")
        if target not in known:
            break
        run.append(known[target])
        at += 2
    return run


def table(image: bytes, known: dict[int, Step]) -> tuple[int, list[Step]]:
    best: tuple[int, list[Step]] = (-1, [])
    for block in sorted({at & ~(BLOCK - 1) for at in known}):
        at = block
        while at < min(block + BLOCK, len(image)) - 1:
            run = run_at(image, at, known)
            if len(run) > len(best[1]):
                best = (at, run)
            at += max(2 * len(run), 1)
    return best if len(best[1]) >= SHORTEST_TABLE else (-1, [])


def order(run: Sequence[Step]) -> dict[int, int]:
    taken = [argument for kind, argument in run if kind == "take"]
    return {buffer: index for index, buffer in enumerate(dict.fromkeys(taken))}


def token(kind: str, argument: int, index: dict[int, int]) -> str | None:
    if kind == "command":
        return f"{argument:#04x}"
    if kind in DIGITS:
        return f"{kind} {index.get(argument, -1)}"
    return "marker" if kind == "marker" else None


def scripts(run: Sequence[Step]) -> list[list[str]]:
    index = order(run)
    found: list[list[str]] = []
    held: list[str] = []
    for kind, argument in run:
        if kind == "finish" and held:
            found.append(held)
            held = []
        said = token(kind, argument, index)
        if said is not None:
            held.append(said)
    return found + ([held] if held else [])


def folded(script: Sequence[str]) -> list[str]:
    out: list[str] = []
    for one in script:
        verb, _, number = one.partition(" ")
        last = out[-1].split(" ") if out else []
        if number and last and last[0] == verb and int(last[-1]) + 1 == int(number):
            out[-1] = f"{verb} {last[1]} to {number}"
        elif number:
            out.append(f"{verb} {number} to {number}")
        else:
            out.append(one)
    return out


def recorded(where: Path | str | None = None) -> dict[str, Any]:
    path = Path(where) if where is not None else ROOT / RECORDED
    if not path.is_file():
        return {}
    found: dict[str, Any] = json.loads(path.read_text())
    return found


def reading(image: bytes, name: str) -> dict[str, Any] | None:
    at, run = table(image, steps(image))
    if not run:
        return None
    every = [folded(one) for one in scripts(run)]
    return {
        "note": (
            "The command scripts the shipped program sends the clock and the reading it "
            "expects back, read out of its own code without running any of it. No "
            "cartridge byte is recorded here."
        ),
        "readFrom": {"name": name, "bytes": len(image), **digests_of(image)},
        "tableAt": f"{at:#08x}",
        "scripts": every,
        "commands": sorted({one[1] for one in every if one[0] == "0x0e" and len(one) > 1}),
    }


def main(argv: Sequence[str], say: Callable[[str], object] = print) -> int:
    if len(argv) < 2:
        say("usage: sharp_cartridge.py <cartridge> <out.json>")
        return 2
    source, out = Path(argv[0]), Path(argv[1])
    if not source.is_file():
        say(f"  no such file: {source}")
        return 2
    found = reading(source.read_bytes(), source.name)
    if found is None:
        say(f"  no clock script table was found in {source.name}")
        return 1
    out.write_text(json.dumps(found, indent=2) + "\n")
    say(f"  script table at {found['tableAt']}; {len(found['scripts'])} scripts")
    for one in found["scripts"]:
        say(f"    {', '.join(one)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
