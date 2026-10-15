from __future__ import annotations

from typing import override

MONTHS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

EPOCH_YEAR = 1900

EPOCH_WEEKDAY = 1

WEEK = 7

DAY = 86400

MASK = 0xFFFFFFFF


class Moment:
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
    if year % 4:
        return False
    if year % 100:
        return True
    return year % 400 == 0


def days_in(year: int, month: int) -> int:
    length = MONTHS[(month - 1) % 12]
    if length == 28 and is_leap(year):
        return 29
    return length


def weekday(year: int, month: int, day: int) -> int:
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
        found = MONTHS[self.month % 12]
        return found + 1 if found == 28 and is_leap(self.year) else found

    def settled(self) -> bool:
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
    counters = _Counters(moment, seconds)
    while counters.second >= 60:
        if counters.settled():
            counters.drain()
            break
        counters.carry()
    return counters.moment()
