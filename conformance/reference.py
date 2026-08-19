"""Hold both clocks to the reference implementations every emulator agrees with.

Neither chip has a published per-instruction suite, so the oracle is the code
itself. A script of reads, writes and clock changes is generated from a seed, run
through a driver compiled around the reference sources, and replayed through the
model here. The two transcripts are compared line for line, and a disagreement is
a defect in this package until it is shown otherwise.

The script is generated rather than written by hand for the same reason a suite
is preferred to a set of examples: a hand-written script exercises the paths its
author thought of. A generated one wanders into command sequences nobody would
write on purpose, which is where a chip's undocumented corners are.

Time is scripted rather than read from the machine. The reference calls the wall
clock, so a driver that let it would disagree with itself between two runs and
the comparison would be worthless.

Usage:
    python3 conformance/reference.py [--runs N] [--length N] [--driver PATH]
"""

import random
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesrtc import epson, sharp, store

USAGE = "usage: reference.py [--runs N] [--length N] [--driver PATH]"

DEFAULT_DRIVER = str(Path(__file__).resolve().parent / "ref" / "driver")

RUNS = 200

LENGTH = 4000

START = 1_000_000_000

JUMP = 400_000_000
"""How far a scripted clock change may reach, which is about twelve years."""

SHARP_ADDRESSES = (sharp.DATA, sharp.CONTROL)

EPSON_ADDRESSES = (epson.ENABLE, epson.DATA, epson.STATUS)

UNMAPPED = (0x2802, 0x4843)

DRIVER_TIMEOUT = 300


class Usage(Exception):
    pass


class Options:
    def __init__(self, runs=RUNS, length=LENGTH, driver=DEFAULT_DRIVER):
        self.runs = runs
        self.length = length
        self.driver = driver


class Cartridge:
    """One store with both chips on it, which is how the driver is wired too."""

    def __init__(self):
        self.store = store.Store(cleared=True)
        self.at = START
        self.sharp = sharp.Clock(self.store, now=lambda: self.at)
        self.epson = epson.Clock(self.store, now=lambda: self.at)

    def chip_for(self, address):
        return self.epson if address in EPSON_ADDRESSES else self.sharp

    def read(self, address):
        return self.chip_for(address).read(address)

    def write(self, address, value):
        self.chip_for(address).write(address, value)

    def power(self):
        for at in range(len(self.store.bytes)):
            self.store.write(at, 0)
        self.sharp.reset()
        self.epson.reset()

    def dump(self):
        return "".join(f"{value:02X}" for value in self.store.bytes)


def generate(seed, length):
    """A script of operations, built from a seed so a failing run can be repeated."""
    source = random.Random(seed)
    script = [("time", START, 0)]
    addresses = SHARP_ADDRESSES + EPSON_ADDRESSES + UNMAPPED

    while len(script) < length - 1:
        roll = source.randrange(100)
        if roll < 45:
            script.append(("w", source.choice(addresses), source.randrange(0x100)))
        elif roll < 85:
            script.append(("r", source.choice(addresses), 0))
        elif roll < 92:
            script.append(
                (
                    "time",
                    script[-1][1] + source.randrange(0, JUMP)
                    if script[-1][0] == "time"
                    else START + source.randrange(0, JUMP),
                    0,
                )
            )
        elif roll < 96:
            script.append(("store", source.randrange(20), source.randrange(0x10)))
        elif roll < 98:
            script.append(("dump", 0, 0))
        else:
            script.append(("power", 0, 0))

    script.append(("dump", 0, 0))
    return script


def render(script):
    """The script as the driver reads it, one operation per line."""
    lines = []
    for verb, first, second in script:
        if verb in ("r", "time", "power", "dump"):
            lines.append(f"{verb} {first}" if verb in ("r", "time") else verb)
        else:
            lines.append(f"{verb} {first} {second}")
    return "\n".join(lines) + "\n"


def replay(script):
    """The same script through the model, producing the same shape of transcript."""
    cartridge = Cartridge()
    transcript = []
    for verb, first, second in script:
        if verb == "time":
            cartridge.at = first
        elif verb == "store":
            cartridge.store.write(first, second)
        elif verb == "power":
            cartridge.power()
        elif verb == "r":
            transcript.append(f"{cartridge.read(first):02X}")
        elif verb == "w":
            cartridge.write(first, second)
        else:
            transcript.append(cartridge.dump())
    return transcript


def ask(script, driver):
    """The same script through the reference, whose answers decide."""
    done = subprocess.run(
        [driver],
        input=render(script),
        capture_output=True,
        text=True,
        check=False,
        timeout=DRIVER_TIMEOUT,
    )
    if done.returncode:
        raise Usage(f"the reference driver failed: {done.stderr.strip()}")
    return done.stdout.splitlines()


def differences(expected, actual):
    """Where the two transcripts stop agreeing, by line."""
    found = []
    for index in range(max(len(expected), len(actual))):
        theirs = expected[index] if index < len(expected) else None
        ours = actual[index] if index < len(actual) else None
        if theirs != ours:
            found.append((index, theirs, ours))
    return found


def options(argv):
    chosen = Options()
    rest = list(argv)
    while rest:
        item = rest.pop(0)
        if item not in ("--runs", "--length", "--driver"):
            raise Usage(USAGE)
        if not rest:
            raise Usage(USAGE)
        value = rest.pop(0)
        if item == "--driver":
            chosen.driver = value
        elif item == "--runs":
            chosen.runs = int(value)
        else:
            chosen.length = int(value)
    return chosen


def run(argv):
    chosen = options(argv)
    if not Path(chosen.driver).exists():
        print(f"no reference driver at {chosen.driver}; build it first")
        return 2

    checked = 0
    failed = 0
    for seed in range(chosen.runs):
        script = generate(seed, chosen.length)
        found = differences(ask(script, chosen.driver), replay(script))
        checked += len(script)
        if not found:
            continue
        failed += 1
        index, theirs, ours = found[0]
        print(f"FAIL seed {seed} at line {index}: reference {theirs}, model {ours}")
        if failed >= 10:
            break

    print(f"{chosen.runs} scripts, {checked} operations, {failed} disagreed")
    return 1 if failed else 0


def main(argv):
    try:
        return run(argv)
    except Usage as error:
        print(error)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
