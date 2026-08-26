"""How fast a clock answers, and a floor it must not fall through.

Not a benchmark for its own sake. Reading a register is the call every other
question here is built on, and a differential run drives millions of them. The
way that stops being usable is gradual: a lookup grows an allocation, a field
becomes a comprehension, and a year later a run nobody changed takes an hour. A
floor that fails loudly is cheaper than noticing.

The Sharp part is the one measured, because it is the slower of the two by a
factor of two and a half: its whole state arrives as one sequence a caller reads
byte by byte, where the Epson part is addressed and answers one register. Timing
the faster one would set a floor the slower one could fall through.

The floor is deliberately far below what the clock does today. It is there to
catch something several times slower, not to police the noise between one runner
and another, because a shared runner's variance is larger than any change worth
arguing about.

Every figure is a median across repeats rather than a mean, because one
scheduling hiccup moves a mean and moves a median much less, and the runtime
version is printed beside it because it is the single thing that changes these
numbers most.

Run it outside the coverage step. A tracer costs about ten times what this does,
so a floor measured under one measures the tracer.
"""

from __future__ import annotations

import statistics
import sys
import time
from typing import TYPE_CHECKING

import snesrtc

if TYPE_CHECKING:
    from collections.abc import Sequence

FLOOR = 500_000
"""Reads per second this must beat, an order of magnitude below what it does."""

CALLS = 20_000
"""Reads per repeat. Enough that the host's timer resolution does not decide."""

REPEATS = 5
"""How many repeats the median is taken across."""

MODEL = "s-rtc"
"""The slower of the two parts, so the floor holds for both."""

ADDRESS = 0x2800
"""The address that hands back the sequence, one byte per read."""


class Timed:
    """One measured run, and what it is allowed to say about itself."""

    __slots__ = ("calls", "seconds", "what")

    def __init__(self, what: str, calls: int, seconds: Sequence[float]) -> None:
        self.what = what
        self.calls = calls
        self.seconds = list(seconds)

    def median(self) -> float:
        return statistics.median(self.seconds)

    def rate(self) -> float:
        """Calls per second, or zero when the clock could not see the work.

        A run that measured zero seconds is a reading about the clock rather
        than about the code, and reporting it as unbounded speed would let a
        machine with a coarse timer pass a floor it never met.
        """
        taken = self.median()
        return self.calls / taken if taken > 0 else 0.0

    def beats(self, floor: int) -> bool:
        return self.rate() >= floor


def measure(calls: int = CALLS, repeats: int = REPEATS) -> Timed:
    """Read the sequence out of the slower part, over and over, and time it."""
    clock = snesrtc.models.lookup(MODEL).build()
    seconds = []
    for _ in range(repeats):
        started = time.perf_counter()
        for _ in range(calls):
            clock.read(ADDRESS)
        seconds.append(time.perf_counter() - started)
    return Timed("read", calls, seconds)


def lines_for(found: Timed, floor: int = FLOOR) -> list[str]:
    """What the run reports, whether it passed or not."""
    runtime = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    lines = [
        f"  {found.what}: {found.rate():,.0f} per second"
        f" (median of {len(found.seconds)}) on Python {runtime}",
        f"  floor: {floor:,} per second",
    ]
    if not found.beats(floor):
        lines.append(f"  below the floor: {found.rate():,.0f} is under {floor:,}")
    return lines


def main(calls: int = CALLS, repeats: int = REPEATS, floor: int = FLOOR) -> int:
    found = measure(calls, repeats)
    for line in lines_for(found, floor):
        print(line)
    return 0 if found.beats(floor) else 1


if __name__ == "__main__":
    raise SystemExit(main())
