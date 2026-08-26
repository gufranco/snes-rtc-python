"""Hold both clocks to a recording, over the ground the recording can settle.

Neither chip has a published per-instruction suite. The Sharp part has no
published anything, so the implementation every emulator agrees with is the only
oracle there is for it and this runner is its whole conformance story. The Epson
part does have a manufacturer's application manual, and where that manual speaks
it outranks any recording: those facts are pinned in hardware.json, gated by
hardware.test.py, and tested against the manual in epson.test.py rather than
against the recording here.

That split is what this runner has to respect. A comparison that reported
agreement on ground the manual has already settled differently would be
reporting the recording's answer as though it were the part's. So each script is
compared only up to the first operation that reaches a declared divergence, and
everything after that point is counted apart and named rather than folded into
the agreements or quietly dropped. divergences.json holds the list, and every id
this runner can witness appears in it.

The script is generated rather than written by hand for the same reason a suite
is preferred to a set of examples: a hand-written script exercises the paths its
author thought of. A generated one wanders into command sequences nobody would
write on purpose, which is where a chip's undocumented corners are.

Time is scripted rather than read from the machine. The reference calls the wall
clock, so a driver that let it would disagree with itself between two runs and
the comparison would be worthless.

Usage:
    python3 conformance/reference.py [--runs N] [--from N] [--length N] [--seed N] [--driver PATH]
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesrtc import epson, sharp, store

USAGE = "usage: reference.py [--runs N] [--from N] [--length N] [--seed N] [--driver PATH]"

DEFAULT_DRIVER = str(Path(__file__).resolve().parent / "ref" / "driver")

DIVERGENCES = Path(__file__).resolve().parent / "divergences.json"

RUNS = 200

LENGTH = 4000

START = 1_000_000_000

JUMP = 400_000_000
"""How far a scripted clock change may reach, which is about twelve years."""

SHARP_ADDRESSES = (sharp.DATA, sharp.CONTROL)

EPSON_ADDRESSES = (epson.ENABLE, epson.DATA, epson.STATUS)

UNMAPPED = (0x2802, 0x4843)

DRIVER_TIMEOUT = 300

CONFIGURED_CF = epson.HOURS_24

CONFIGURED_CD = epson.CAL_HW

CONFIGURE = (("store", epson.CF, CONFIGURED_CF), ("store", epson.CD, CONFIGURED_CD))
"""The state the manual's own power-on procedure leaves the Epson chip in.

Every register is undefined at power-on, so a cleared register file is not a
configured chip: it is a chip in twelve hour notation whose date counters are
switched off. The recording assumes twenty four hour notation and a running
calendar unconditionally, so this is the one configuration in which the two can
be compared at all. Both sides are put into it the same way, by writing the two
control registers directly, which the driver supports and neither implementation
treats as a register write.
"""

NARROW = tuple(index for index, mask in enumerate(epson.DIGIT_MASK[:13]) if mask != epson.NIBBLE)
"""The Epson registers whose BCD digit is narrower than the register holding it."""

STAMP_AMBIGUOUS = 0x8000_0000
"""Where the recording stops being a stable oracle about elapsed time.

Both models remember when they were last read in the four bytes the cartridge
keeps for it, and both test for underflow against the range those four bytes
hold. The recording builds the same four bytes and then tests against the maximum
of the host's time_t, so a 64-bit build and a 32-bit build of it disagree about
every interval above half the stamp's range. An answer that depends on the width
of a type on the build machine is a property of the recorder, so it is excluded
rather than allowed to decide.
"""

Operation = tuple[str, int, int]


class Usage(Exception):
    pass


class Options:
    def __init__(
        self,
        runs: int = RUNS,
        length: int = LENGTH,
        driver: str = DEFAULT_DRIVER,
        seed: int | None = None,
        start: int = 0,
    ) -> None:
        self.runs = runs
        self.length = length
        self.driver = driver
        self.seed = seed
        self.start = start

    def seeds(self) -> Sequence[int]:
        """Which scripts to run: a run of them from somewhere, or a single named one.

        Naming one is how a disagreement is reproduced. The runner prints the seed
        of any script that disagreed, and that seed alone can be run again without
        waiting for the ones before it.

        Moving the start is how the schedule covers ground the pipeline never
        reaches. Every push runs the same scripts from zero, so more of them is
        deeper in the same place; a different start is somewhere else.
        """
        if self.seed is not None:
            return (self.seed,)
        return range(self.start, self.start + self.runs)


class Cartridge:
    """One store with both chips on it, which is how the driver is wired too."""

    def __init__(self) -> None:
        self.store = store.Store(cleared=True)
        self.at = START
        self.sharp = sharp.Chip(self.store, now=lambda: self.at)
        self.epson = epson.Chip(self.store, now=lambda: self.at)

    def chip_for(self, address: int) -> sharp.Chip | epson.Chip:
        return self.epson if address in EPSON_ADDRESSES else self.sharp

    def read(self, address: int) -> int:
        return self.chip_for(address).read(address)

    def write(self, address: int, value: int) -> None:
        self.chip_for(address).write(address, value)

    def power(self) -> None:
        for at in range(len(self.store.bytes)):
            self.store.write(at, 0)
        self.sharp.reset()
        self.epson.reset()

    def dump(self) -> str:
        return "".join(f"{value:02X}" for value in self.store.bytes)


def declared() -> set[str]:
    """Every divergence id the project has written down, read from the file itself."""
    holds = json.loads(DIVERGENCES.read_text())
    return {entry["id"] for entry in holds["divergences"]}


def witness(cartridge: Cartridge, operation: Operation) -> set[str]:
    """Which declared divergences this operation reaches, judged before it is applied.

    The judgement is made from outside the model, by looking at the state the
    runner can already see, so that nothing in this file has to be threaded back
    into snesrtc for the sake of being measured. It is deliberately conservative:
    a state that merely makes a divergence reachable counts as reaching it, so
    the comparison stops earlier than strictly necessary rather than later.
    """
    found: set[str] = set()
    verb, first, second = operation
    held = cartridge.store

    if cartridge.at >= STAMP_AMBIGUOUS or (verb == "time" and first >= STAMP_AMBIGUOUS):
        found.add("stamp-width-platform-dependent")

    if verb == "w" and first == epson.DATA and cartridge.epson.state == epson.READING:
        found.add("epson-writes-during-read-mode")

    if verb == "w" and first == epson.DATA and cartridge.epson.state == epson.WRITING:
        found |= _witness_register(held, cartridge.epson.index, second & epson.NIBBLE)

    if verb == "w" and first == epson.ENABLE and not second & 1:
        if held.read(epson.CF) & epson.TEST:
            found.add("epson-test-bit-not-cleared")
        if any(held.read(at) & epson.READ_FLAG for at in epson.READ_FLAG_AT):
            found.add("epson-oscillation-flag-cannot-be-originated")

    reading_control_d = (
        verb == "r"
        and first == epson.DATA
        and cartridge.epson.state != epson.INACTIVE
        and cartridge.epson.index == epson.CD
    )
    if reading_control_d and held.read(epson.CD) & epson.IRQ_F:
        found.add("epson-irqf-not-writable")

    if _catches_up(cartridge, operation):
        found |= _witness_state(held)
        closing = verb == "w" and first == epson.ENABLE
        if not closing and _would_advance(cartridge):
            found.add("epson-oscillation-flag-cannot-be-originated")
    return found


def _would_advance(cartridge: Cartridge) -> bool:
    """Whether a catch-up here moves the seconds, which is what raises the read flag.

    The manual sets fr when the one-second digit increments while CE is high, so
    a catch-up inside an open session raises it and a catch-up on the way out
    does not, because that one ends with CE low and the flag cleared.
    """
    chip = cartridge.epson
    if chip.stopped() or cartridge.store.read(epson.CD) & epson.HOLD:
        return False
    return chip.elapsed(cartridge.at & 0xFFFFFFFF) > 0


def _catches_up(cartridge: Cartridge, operation: Operation) -> bool:
    """Whether this operation makes the Epson model recompute the stored time.

    The state divergences are all latent until then. A register holding a flag
    bit the manufacturer names, a cleared notation bit, a cleared range bit: none
    of them changes a single byte until something writes the time back through
    them. Witnessing on the catch-up rather than on the state is what keeps the
    comparison from stopping at the first operation of every script, and it is
    still conservative, because the catch-up is judged before it happens.
    """
    verb, first, second = operation
    if verb == "w" and first == epson.ENABLE and not second & 1:
        return True
    if verb != "w" or first != epson.DATA or cartridge.epson.state != epson.WRITING:
        return False
    if cartridge.epson.index == epson.CF:
        return True
    if cartridge.epson.index != epson.CD:
        return False
    value = second & epson.NIBBLE
    held = cartridge.store.read(epson.CD)
    return bool(value & epson.ADJUST or (value ^ held) & epson.HOLD)


def _witness_register(held: store.Store, index: int, value: int) -> set[str]:
    """What a value arriving at one Epson control register changes straight away.

    Only the control registers appear here. A digit written to a clock register
    is stored whole by both implementations, so the write itself agrees; what
    the two do differently is read it back, and that is a catch-up matter rather
    than a write matter.
    """
    found: set[str] = set()
    if index != epson.CD:
        return found
    if value & epson.IRQ_F:
        found.add("epson-irqf-not-writable")
    if value & epson.ADJUST:
        found.add("epson-thirty-second-adjust-lockout")
    if value & epson.CAL_HW:
        found.add("epson-cd-bit1-add-second")
    if (value ^ held.read(epson.CD)) & epson.HOLD:
        found.add("epson-hold-discards-elapsed-time")
    return found


def _witness_state(held: store.Store) -> set[str]:
    """What the register file, holding as it does, reaches when the time is written back.

    Each of these is latent until a catch-up. A flag bit sitting in a narrow
    register changes nothing until the time is written back through it, because
    this model preserves the bit and the recording overwrites the whole nibble.
    """
    found: set[str] = set()
    if any(held.read(at) & ~epson.DIGIT_MASK[at] & epson.NIBBLE for at in NARROW):
        found.add("epson-digit-fields-narrower-than-registers")
    if not held.read(epson.CD) & epson.CAL_HW:
        found.add("epson-cd-bit1-add-second")
    if held.read(epson.CD) & epson.HOLD:
        found.add("epson-hold-discards-elapsed-time")
    if not held.read(epson.CF) & epson.HOURS_24:
        found.add("epson-twelve-hour-mode-transient")
    return found


class Part:
    """One clock, the addresses its scripts may touch, and how long they should be."""

    def __init__(self, addresses: tuple[int, ...], longest: int | None = None) -> None:
        self.addresses = addresses
        self.longest = longest

    def length(self, asked: int) -> int:
        return asked if self.longest is None else min(asked, self.longest)


PARTS = {
    "sharp": Part(SHARP_ADDRESSES + UNMAPPED),
    "epson": Part(EPSON_ADDRESSES + UNMAPPED, longest=200),
}
"""Which addresses a script for one part may touch, and how long it is worth being.

The two clocks are driven separately because no cartridge ever carried both. In
this repository and in the recording alike they share one twenty byte store,
which is a convenience of the harness rather than anything a board did, and
letting one part write the other's register file measures the convenience. It
also measures nothing useful: the Sharp part writes a decimal digit into a
register the Epson part reads as three bits and a flag, so a script that drives
both reaches a declared divergence within a few operations every time.

The Epson scripts are capped because a longer one buys nothing. Comparison stops
at the first operation reaching a declared divergence, and measured over hundreds
of scripts that happens after about thirty operations whether the script is two
hundred long or four thousand. Coverage of this part therefore scales with the
number of scripts and not with their length, and the cap turns the difference
into twenty times more scripts for the same work. The Sharp part has no
divergences to reach, so its scripts run to whatever length is asked.
"""


def generate(seed: int, length: int, part: str | None = None) -> list[Operation]:
    """A script of operations, built from a seed so a failing run can be repeated."""
    source = random.Random(seed)
    script: list[Operation] = [("time", START, 0), *CONFIGURE]
    addresses = PARTS[part].addresses if part else SHARP_ADDRESSES + EPSON_ADDRESSES + UNMAPPED

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
        elif len(script) < length - 1 - len(CONFIGURE):
            script.append(("power", 0, 0))
            script.extend(CONFIGURE)

    del script[length - 1 :]
    script.append(("dump", 0, 0))
    return script


def render(script: Sequence[Operation]) -> str:
    """The script as the driver reads it, one operation per line."""
    lines = []
    for verb, first, second in script:
        if verb in ("r", "time", "power", "dump"):
            lines.append(f"{verb} {first}" if verb in ("r", "time") else verb)
        else:
            lines.append(f"{verb} {first} {second}")
    return "\n".join(lines) + "\n"


class Replay:
    """One script through the model, with the point the comparison can reach.

    ``settled`` is how many transcript lines were produced before the first
    operation that reaches a declared divergence. Those lines are the ones the
    recording can be asked about. ``reached`` names what stopped it.
    """

    def __init__(self, transcript: list[str], settled: int, reached: set[str]) -> None:
        self.transcript = transcript
        self.settled = settled
        self.reached = reached

    @property
    def limit(self) -> int | None:
        """How far to compare, or None for all of it including any excess.

        A script that reached nothing is compared to its end, and the comparison
        has to run past the end of the shorter transcript so that a reference
        answering more lines than the model is a failure rather than a silence.
        """
        return self.settled if self.reached else None


def observe(script: Sequence[Operation]) -> Replay:
    """The same script through the model, producing the same shape of transcript."""
    cartridge = Cartridge()
    transcript: list[str] = []
    settled = -1
    reached: set[str] = set()
    settling = 1 + len(CONFIGURE)

    for operation in script:
        if settling:
            settling -= 1
        else:
            found = witness(cartridge, operation)
            if found and settled < 0:
                settled = len(transcript)
            reached |= found
        verb, first, second = operation
        if verb == "power":
            settling = len(CONFIGURE)
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

    return Replay(transcript, len(transcript) if settled < 0 else settled, reached)


def replay(script: Sequence[Operation]) -> list[str]:
    """The transcript alone, for callers that do not care where it stops being settled."""
    return observe(script).transcript


def ask(script: Sequence[Operation], driver: str) -> list[str]:
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


def differences(
    expected: Sequence[str], actual: Sequence[str], limit: int | None = None
) -> list[tuple[int, str | None, str | None]]:
    """Where the two transcripts stop agreeing, by line, over the settled prefix."""
    reach = max(len(expected), len(actual)) if limit is None else limit
    found = []
    for index in range(reach):
        theirs = expected[index] if index < len(expected) else None
        ours = actual[index] if index < len(actual) else None
        if theirs != ours:
            found.append((index, theirs, ours))
    return found


def options(argv: Sequence[str]) -> Options:
    chosen = Options()
    rest = list(argv)
    while rest:
        item = rest.pop(0)
        if item not in ("--runs", "--length", "--driver", "--seed", "--from"):
            raise Usage(USAGE)
        if not rest:
            raise Usage(USAGE)
        value = rest.pop(0)
        if item == "--driver":
            chosen.driver = value
        elif item == "--runs":
            chosen.runs = int(value)
        elif item == "--seed":
            chosen.seed = int(value)
        elif item == "--from":
            chosen.start = int(value)
        else:
            chosen.length = int(value)
    return chosen


class Tally:
    """What a run actually compared, and what it refused to."""

    def __init__(self, part: str = "") -> None:
        self.part = part
        self.scripts = 0
        self.compared = 0
        self.excluded = 0
        self.failed = 0
        self.reached: dict[str, int] = {}

    def add(self, replayed: Replay, produced: int) -> None:
        self.scripts += 1
        self.compared += replayed.settled
        self.excluded += max(0, produced - replayed.settled)
        for name in sorted(replayed.reached):
            self.reached[name] = self.reached.get(name, 0) + 1

    def report(self) -> Iterator[str]:
        where = f"{self.part}: " if self.part else ""
        yield (
            f"{where}{self.scripts} scripts, {self.compared} operations compared, "
            f"{self.excluded} not compared, {self.failed} disagreed"
        )
        for name, count in sorted(self.reached.items()):
            yield f"  not compared past {name}, reached by {count} scripts"


REPORTED_FAILURES = 10
"""How many disagreements one part reports before it stops naming them.

The eleventh adds nothing a reader can act on, and a wrong driver produces one
per script. The run still fails; it just stops printing.
"""


def sweep(part: str, chosen: Options, known: set[str]) -> Tally:
    """One part driven on its own, because no cartridge ever carried both."""
    tally = Tally(part)
    for seed in chosen.seeds():
        script = generate(seed, PARTS[part].length(chosen.length), part)
        replayed = observe(script)
        unknown = replayed.reached - known
        if unknown:
            print(f"FAIL {part} seed {seed}: undeclared divergence {sorted(unknown)}")
            tally.failed += 1
            tally.add(replayed, len(replayed.transcript))
            continue
        theirs = ask(script, chosen.driver)
        found = differences(theirs, replayed.transcript, replayed.limit)
        tally.add(replayed, max(len(theirs), len(replayed.transcript)))
        if not found:
            continue
        tally.failed += 1
        index, expected, actual = found[0]
        print(f"FAIL {part} seed {seed} at line {index}: reference {expected}, model {actual}")
        if tally.failed >= REPORTED_FAILURES:
            return tally
    return tally


def run(argv: Sequence[str]) -> int:
    chosen = options(argv)
    if not Path(chosen.driver).exists():
        print(f"no reference driver at {chosen.driver}; build it first")
        return 2

    known = declared()
    failed = 0
    for part in sorted(PARTS):
        tally = sweep(part, chosen, known)
        failed += tally.failed
        for line in tally.report():
            print(line)
    return 1 if failed else 0


def main(argv: Sequence[str]) -> int:
    try:
        return run(argv)
    except Usage as error:
        print(error)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
