"""Calendar arithmetic as the cartridge clocks perform it, not as Python would.

Both chips keep the date as separate counters and roll them over one step at a
time. That is not the same thing as converting to a timestamp, adding, and
converting back, and the difference is visible: the weekday is a counter of its
own that advances with the day rather than being derived from the date, so a
cartridge whose weekday was written wrong stays wrong forever, and the games that
read it show the wrong day.

The weekday calculation counts days from the first of January 1900 rather than
using a formula. It is the arithmetic the reference performs, and it is kept
because a formula that agrees on every date anyone happens to test is still a
second description that can drift from the first.

Inputs are clamped rather than rejected. A cartridge holds whatever was written
to it, including a thirty first of February, and the chip answers with something
rather than refusing.
"""

from __future__ import annotations

from typing import override

MONTHS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

EPOCH_YEAR = 1900

EPOCH_WEEKDAY = 1
"""The first of January 1900 was a Monday, and Sunday is zero."""

WEEK = 7

DAY = 86400

MASK = 0xFFFFFFFF


class Moment:
    """One reading of the calendar, with the weekday carried rather than derived."""

    __slots__ = ("day", "hour", "minute", "month", "second", "weekday", "year")

    def __init__(
        self,
        year: int,
        month: int,
        day: int,
        hour: int,
        minute: int,
        second: int,
        weekday: int,
    ) -> None:
        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second
        self.weekday = weekday

    @override
    def __eq__(self, other: object) -> bool:
        return all(getattr(self, name) == getattr(other, name) for name in self.__slots__)

    @override
    def __hash__(self) -> int:
        return hash(tuple(getattr(self, name) for name in self.__slots__))

    @override
    def __repr__(self) -> str:
        return (
            f"<{self.year:04d}-{self.month:02d}-{self.day:02d} "
            f"{self.hour:02d}:{self.minute:02d}:{self.second:02d} weekday={self.weekday}>"
        )


def is_leap(year: int) -> bool:
    """Whether a year carries the extra day, by the rule with both exceptions."""
    if year % 4:
        return False
    if year % 100:
        return True
    return year % 400 == 0


def days_in(year: int, month: int) -> int:
    """How long a month is, counting from one, wrapping rather than failing."""
    length = MONTHS[(month - 1) % 12]
    if length == 28 and is_leap(year):
        return 29
    return length


def weekday(year: int, month: int, day: int) -> int:
    """The day of the week, counted forward from the epoch one day at a time.

    Sunday is zero. Dates before the epoch cannot be counted forward from it, and
    a month or day outside its range is not a date at all, so each is pulled to
    the nearest value that is. The chip has no way to report a refusal.
    """
    year = max(EPOCH_YEAR, year)
    month = max(1, min(12, month))
    day = max(1, min(31, day))

    passed = 0
    for walked in range(EPOCH_YEAR, year):
        passed += 366 if is_leap(walked) else 365
    for walked in range(1, month):
        passed += days_in(year, walked)
    passed += day - 1
    return (passed + EPOCH_WEEKDAY) % WEEK


class _Counters:
    """The chip's counters mid-flight, zero based and thirty two bits wide."""

    __slots__ = ("day", "hour", "minute", "month", "second", "weekday", "year")

    def __init__(self, moment: Moment, seconds: int) -> None:
        self.year = moment.year
        self.month = (moment.month - 1) & MASK
        self.day = (moment.day - 1) & MASK
        self.hour = moment.hour
        self.minute = moment.minute
        self.second = moment.second + seconds
        self.weekday = moment.weekday

    def length(self) -> int:
        """How long the current month is, read through the underflow if there was one."""
        found = MONTHS[self.month % 12]
        return found + 1 if found == 28 and is_leap(self.year) else found

    def settled(self) -> bool:
        """Whether every counter is inside its range, which is not a given.

        A cartridge holds whatever was written to it, and a field outside its
        range does not behave like a larger version of one inside it. While any
        field is out of range the counters are advanced one carry at a time,
        because that is the only way to reproduce what the chip does with them.
        """
        return self.minute < 60 and self.hour < 24 and self.month < 12 and self.day < self.length()

    def turn_day(self) -> None:
        self.day = (self.day + 1) & MASK
        self.weekday = (self.weekday + 1) % WEEK
        if self.day < self.length():
            return
        self.day = 0
        self.month = (self.month + 1) & MASK
        if self.month < 12:
            return
        self.month = 0
        self.year = (self.year + 1) & MASK

    def carry(self) -> None:
        """One sixty second block consumed, exactly as the reference consumes it."""
        self.second -= 60
        self.minute = (self.minute + 1) & MASK
        if self.minute < 60:
            return
        self.minute = 0
        self.hour = (self.hour + 1) & MASK
        if self.hour < 24:
            return
        self.hour = 0
        self.turn_day()

    def drain(self) -> None:
        """Every remaining block at once, which is only sound once settled.

        With each counter inside its range the carries are ordinary odometer
        arithmetic, so the minutes and hours are divided out in one step instead
        of counted. Only the days keep a loop, because the length of a month
        depends on which month it is.
        """
        minutes, self.second = divmod(self.second, 60)
        hours, self.minute = divmod(self.minute + minutes, 60)
        days, self.hour = divmod(self.hour + hours, 24)
        for _ in range(days):
            self.turn_day()

    def moment(self) -> Moment:
        return Moment(
            self.year,
            (self.month + 1) & MASK,
            (self.day + 1) & MASK,
            self.hour,
            self.minute,
            self.second,
            self.weekday,
        )


def advance(moment: Moment, seconds: int) -> Moment:
    """A moment moved forward, rolling each counter into the next as the chip does.

    The counters are thirty two bit unsigned and the chip subtracts one from the
    day and the month before it starts. A cartridge holding a month of zero
    therefore does not roll back to December: it underflows to four billion, and
    the month length is read from that number's remainder, which lands on a thirty
    day month. Wrapping to December instead would be the sensible reading and
    would disagree with every emulator.
    """
    counters = _Counters(moment, seconds)
    while counters.second >= 60:
        if counters.settled():
            counters.drain()
            break
        counters.carry()
    return counters.moment()
