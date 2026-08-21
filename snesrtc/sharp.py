"""The Sharp S-RTC, as it answers at two addresses.

One address reads and one address writes, and everything else is a state machine
driven by four-bit values written to the second. The sequence is not addressed:
the chip hands out its thirteen bytes in order, wrapped in a marker at each end,
and a program that loses count reads the wrong field with nothing to tell it so.

Two behaviours are worth naming because they are not obvious from the register
map.

The weekday is not written. A program writes twelve bytes and the chip computes
the thirteenth from the date it was just given, so a cartridge whose date is
right always reports the matching weekday. Once written it is a counter that
advances with the day, never re-derived, so a date changed by a battery fault
takes the weekday with it and the two stay out of step.

The year is stored as three digits with a thousand added, so the range is 1000 to
1999 by the arithmetic and the games use it to mean 1900 to 1999.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import override

from . import calendar
from .store import Store

DATA = 0x2800

CONTROL = 0x2801

READY, COMMAND, READING, WRITING = "ready", "command", "read", "write"

MARKER = 0x0F

LAST_INDEX = 12
"""The weekday, which is the last byte in the sequence and the one nobody writes."""

COMMAND_READ = 0x0D

COMMAND_BEGIN = 0x0E

COMMAND_NOTHING = 0x0F

COMMAND_WRITE = 0x00

COMMAND_CLEAR = 0x04

YEAR_BASE = 1000

STAMP_LIMIT = 0x1_0000_0000


def _now() -> int:
    import time

    return int(time.time())


class Clock:
    """One S-RTC, answering at its two addresses."""

    model: str

    def __init__(self, store: Store, now: Callable[[], int] = _now, open_bus: int = 0x00) -> None:
        self.store = store
        self.now = now
        self.open_bus = open_bus
        self.mode = READING
        self.index = -1

    def reset(self) -> Clock:
        """What the reset line does, which is less than a power cycle would."""
        self.mode = READING
        self.index = -1
        self.update()
        return self

    def read(self, address: int) -> int:
        if address != DATA:
            return self.open_bus
        if self.mode != READING:
            return 0x00
        if self.index < 0:
            self.update()
            self.index += 1
            return MARKER
        if self.index > LAST_INDEX:
            self.index = -1
            return MARKER
        value = self.store.read(self.index)
        self.index += 1
        return value

    def write(self, address: int, value: int) -> None:
        if address != CONTROL:
            return
        value &= 0x0F
        if value == COMMAND_READ:
            self.mode = READING
            self.index = -1
            return
        if value == COMMAND_BEGIN:
            self.mode = COMMAND
            return
        if value == COMMAND_NOTHING:
            return
        if self.mode == WRITING:
            self.accept(value)
        elif self.mode == COMMAND:
            self.command(value)

    def accept(self, value: int) -> None:
        """One digit of a time being written, and the weekday that follows the last."""
        if not 0 <= self.index < LAST_INDEX:
            return
        self.store.write(self.index, value)
        self.index += 1
        if self.index != LAST_INDEX:
            return
        day = self.store.read(6) + self.store.read(7) * 10
        month = self.store.read(8)
        year = self.store.read(9) + self.store.read(10) * 10 + self.store.read(11) * 100
        self.store.write(self.index, calendar.weekday(year + YEAR_BASE, month, day))
        self.index += 1

    def command(self, value: int) -> None:
        if value == COMMAND_WRITE:
            self.mode = WRITING
            self.index = 0
            return
        if value == COMMAND_CLEAR:
            self.mode = READY
            self.index = -1
            for at in range(LAST_INDEX + 1):
                self.store.write(at, 0)
            return
        self.mode = READY

    def elapsed(self) -> int:
        """How long since the clock was last read, measured the way the chip does.

        The stamp is four bytes, so it runs out roughly every sixty eight years and
        starts again. Subtracting across that point gives a negative answer, and
        taking the long way round instead keeps a cartridge readable through the
        wrap. A stamp ahead of the present cannot be a real interval, so it is
        treated as no time at all rather than as sixty eight years.
        """
        current = self.now() & 0xFFFFFFFF
        stamped = self.store.stamp
        gap = current - stamped if current >= stamped else STAMP_LIMIT - stamped + current
        return 0 if gap > STAMP_LIMIT // 2 else gap

    def update(self) -> None:
        """Advance the stored time to now, then record when now was."""
        gap = self.elapsed()
        if gap > 0:
            self.store_moment(calendar.advance(self.read_moment(), gap))
        self.store.stamp = self.now() & 0xFFFFFFFF

    def read_moment(self) -> calendar.Moment:
        held = self.store
        return calendar.Moment(
            year=held.read(9) + held.read(10) * 10 + held.read(11) * 100 + YEAR_BASE,
            month=held.read(8),
            day=held.read(6) + held.read(7) * 10,
            hour=held.read(4) + held.read(5) * 10,
            minute=held.read(2) + held.read(3) * 10,
            second=held.read(0) + held.read(1) * 10,
            weekday=held.read(12),
        )

    def store_moment(self, moment: calendar.Moment) -> None:
        held = self.store
        year = moment.year - YEAR_BASE
        held.write(0, moment.second % 10)
        held.write(1, moment.second // 10)
        held.write(2, moment.minute % 10)
        held.write(3, moment.minute // 10)
        held.write(4, moment.hour % 10)
        held.write(5, moment.hour // 10)
        held.write(6, moment.day % 10)
        held.write(7, moment.day // 10)
        held.write(8, moment.month)
        held.write(9, year % 10)
        held.write(10, (year // 10) % 10)
        held.write(11, year // 100)
        held.write(12, moment.weekday % calendar.WEEK)

    @override
    def __repr__(self) -> str:
        return f"<S-RTC {self.mode} at {self.index}>"
