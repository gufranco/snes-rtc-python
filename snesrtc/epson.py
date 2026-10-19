from __future__ import annotations

from collections.abc import Callable
from typing import override

from . import calendar, crystal
from .store import Store

ENABLE = 0x4840

DATA = 0x4841

STATUS = 0x4842

INACTIVE, MODE_SELECT, INDEX_SELECT, READING, WRITING = (
    "inactive",
    "mode",
    "index",
    "read",
    "write",
)

WRITE_MODE = 0x03

READ_MODE = 0x0C

READY = 0x80

REGISTERS = 16

NIBBLE = 0x0F

S1, S10, MI1, MI10, H1, H10, D1, D10, MO1, MO10, Y1, Y10, W, CD, CE, CF = range(REGISTERS)

DIGIT_MASK = (
    0xF,
    0x7,
    0xF,
    0x7,
    0xF,
    0x3,
    0xF,
    0x3,
    0xF,
    0x1,
    0xF,
    0xF,
    0x7,
    0xF,
    0xF,
    0xF,
)

OSC_FLAG = 0x8

READ_FLAG = 0x8

READ_FLAG_AT = (MI10, H10, D10, MO10, W)

CALENDAR_READ_FLAG_AT = (D10, MO10)

PM = 0x4

H20 = 0x2

HOLD = 0x1

CAL_HW = 0x2

IRQ_F = 0x4

ADJUST = 0x8

MASK = 0x1

INT_STND = 0x2

PERIOD_SHIFT = 2

PERIOD_BITS = 0x3

RESET = 0x1

STOP = 0x2

HOURS_24 = 0x4

TEST = 0x8

STOPPED = RESET | STOP

HALF_MINUTE = 30

MINUTE = 60

HOUR = 3600

WHOLE_SECONDS_PER_PERIOD = (1, 1, MINUTE, HOUR)

NOON = 12

YEAR_PIVOT = 90

STAMP_LIMIT = 0x1_0000_0000

STAMP_MASK = STAMP_LIMIT - 1

CLOCK_REGISTERS = W + 1

FAST_PERIOD = 0

CRYSTAL_HZ = crystal.CRYSTAL_HZ

WHOLE_SECONDS = crystal.WHOLE_SECONDS


class Chip:
    __slots__ = (
        "crystal",
        "enable",
        "index",
        "mode",
        "model",
        "now",
        "oscillating",
        "state",
        "status",
        "store",
    )

    model: str

    def __init__(
        self, store: Store, now: Callable[[], int] | None = None, rate: int = CRYSTAL_HZ
    ) -> None:
        self.store = store
        self.now = crystal.machine_clock(rate) if now is None else now
        self.crystal = crystal.Crystal(rate)
        self.oscillating = True
        self.state = INACTIVE
        self.mode = WRITE_MODE
        self.index = 0
        self.enable = 0x00
        self.status = 0x00

    def reset(self) -> Chip:
        self.state = INACTIVE
        self.mode = WRITE_MODE
        self.index = 0
        self.enable = 0x00
        self.status = 0x00
        return self

    def seconds(self) -> int:
        return self.crystal.seconds(self.now()) & STAMP_MASK

    def keep_time(self) -> None:
        if not self.crystal.continuous:
            return
        at = self.now()
        if self.crystal.settling(at):
            self.settle_adjust()
        self.update()
        self.fast_tick(at)
        self.expire(at)
        self.crystal.last = at

    @property
    def std_p(self) -> int:
        self.keep_time()
        if self.masked():
            return crystal.OPEN
        if self.store.read(CE) & INT_STND:
            return crystal.LOW if self.store.read(CD) & IRQ_F else crystal.OPEN
        return crystal.LOW if self.crystal.pulsing(self.now()) else crystal.OPEN

    def interrupt_oscillation(self) -> None:
        self.update()
        self.store.write(S10, self.store.read(S10) | OSC_FLAG)
        self.oscillating = False

    def restore_oscillation(self) -> None:
        self.oscillating = True
        self.store.stamp = self.seconds()
        self.crystal.last = self.now()

    def read(self, address: int) -> int:
        self.keep_time()
        if address == ENABLE:
            return self.enable
        if address == DATA:
            return self.read_data()
        if address == STATUS:
            answered = self.status
            self.status &= ~READY & 0xFF
            return answered
        return 0x00

    def read_data(self) -> int:
        if self.state in (INACTIVE, MODE_SELECT):
            return 0x00
        self.status = READY
        value = self.visible(self.index)
        if self.index == CD:
            self.store.write(CD, self.store.read(CD) & ~IRQ_F & NIBBLE)
        self.index = (self.index + 1) % REGISTERS
        return value

    def write(self, address: int, value: int) -> None:
        self.keep_time()
        if address == ENABLE:
            self.write_enable(value)
        elif address == DATA:
            self.write_data(value)

    def write_enable(self, value: int) -> None:
        self.enable = value & 0xFF
        if not self.enable & 1:
            self.state = INACTIVE
            self.update()
            self.clear_read_flag()
            self.store.write(CF, self.store.read(CF) & ~TEST & NIBBLE)
            return
        self.status = READY
        self.state = MODE_SELECT

    def write_data(self, value: int) -> None:
        if self.state == MODE_SELECT:
            if value in (WRITE_MODE, READ_MODE):
                self.status = READY
                self.state = INDEX_SELECT
                self.mode = value
                self.index = 0
            return
        if self.state == INDEX_SELECT:
            self.status = READY
            self.index = value & (REGISTERS - 1)
            self.state = WRITING if self.mode == WRITE_MODE else READING
            return
        if self.state == WRITING:
            self.status = READY
            self.write_register(value & NIBBLE)
            self.index = (self.index + 1) % REGISTERS

    def visible(self, index: int) -> int:
        held = self.store.read(index) & NIBBLE
        if index == H10:
            return held & ~self.fixed_hour_bit() & NIBBLE
        if index == CD and self.masked():
            return held & ~IRQ_F & NIBBLE
        return held

    def write_register(self, value: int) -> None:
        if self.index == CD:
            self.write_control_d(value)
        elif self.index == CE:
            self.write_control_e(value)
        elif self.index == CF:
            self.write_control_f(value)
        elif self.index < CLOCK_REGISTERS and self.crystal.locked(self.now()):
            return
        elif self.index == H10:
            self.store.write(H10, value & ~self.fixed_hour_bit() & NIBBLE)
        else:
            self.store.write(self.index, value)

    def write_control_e(self, value: int) -> None:
        self.store.write(CE, value)
        if value & MASK:
            self.store.write(CD, self.store.read(CD) & ~IRQ_F & NIBBLE)

    def write_control_d(self, value: int) -> None:
        held = self.store.read(CD) & NIBBLE
        settled = (value & ~IRQ_F & ~ADJUST & NIBBLE) | (held & IRQ_F)
        if self.crystal.adjust_at is not None:
            settled |= ADJUST
        if settled & HOLD and not held & HOLD:
            self.update()
        self.store.write(CD, settled)
        if value & ADJUST:
            self.begin_adjust()
        if held & HOLD and not settled & HOLD:
            self.release_hold()

    def begin_adjust(self) -> None:
        lockout = self.crystal.lockout_ticks()
        if not lockout:
            self.adjust_to_nearest_minute()
            return
        self.crystal.adjust_at = self.now() + lockout
        self.store.write(CD, self.store.read(CD) | ADJUST)

    def settle_adjust(self) -> None:
        landed = self.crystal.seconds(self.crystal.adjust_at or 0)
        self.crystal.adjust_at = None
        self.store.write(CD, self.store.read(CD) & ~ADJUST & NIBBLE)
        self.adjust_to_nearest_minute((self.seconds() - landed) & STAMP_MASK)

    def write_control_f(self, value: int) -> None:
        held = self.store.read(CF) & NIBBLE
        settled = value & NIBBLE
        if value & RESET:
            settled &= ~TEST & NIBBLE
        self.update()
        self.store.write(CF, settled)
        if value & RESET and not held & RESET:
            self.put_digit(S1, 0)
            self.put_digit(S10, 0)
            self.crystal.adjust_at = None
            self.store.write(CD, self.store.read(CD) & ~ADJUST & NIBBLE)

    def release_hold(self) -> None:
        if self.elapsed(self.seconds()) > 0:
            self.advance(1)
        self.store.stamp = self.seconds()

    def adjust_to_nearest_minute(self, behind: int = 0) -> None:
        self.update(behind)
        second = self.digit(S1) + self.digit(S10) * 10
        self.put_digit(S1, 0)
        self.put_digit(S10, 0)
        if second >= HALF_MINUTE:
            self.update(behind + MINUTE)

    def digit(self, index: int) -> int:
        return self.store.read(index) & DIGIT_MASK[index]

    def put_digit(self, index: int, value: int) -> None:
        mask = DIGIT_MASK[index]
        kept = self.store.read(index) & ~mask & NIBBLE
        self.store.write(index, kept | (value & mask))

    def read_flag_at(self) -> tuple[int, ...]:
        if self.dated():
            return READ_FLAG_AT
        return tuple(index for index in READ_FLAG_AT if index not in CALENDAR_READ_FLAG_AT)

    def clear_read_flag(self) -> None:
        for index in self.read_flag_at():
            self.store.write(index, self.store.read(index) & ~READ_FLAG & NIBBLE)

    def set_read_flag(self) -> None:
        for index in self.read_flag_at():
            self.store.write(index, self.store.read(index) | READ_FLAG)

    def twenty_four_hour(self) -> bool:
        return bool(self.store.read(CF) & HOURS_24)

    def fixed_hour_bit(self) -> int:
        return PM if self.twenty_four_hour() else H20

    def masked(self) -> bool:
        return bool(self.store.read(CE) & MASK)

    def interrupting(self) -> bool:
        return bool(self.store.read(CE) & INT_STND) and not self.masked()

    def selection(self) -> int:
        return (self.store.read(CE) >> PERIOD_SHIFT) & PERIOD_BITS

    def period(self) -> int:
        return WHOLE_SECONDS_PER_PERIOD[self.selection()]

    def counted_in_seconds(self) -> bool:
        return not (self.crystal.continuous and self.selection() == FAST_PERIOD)

    def increment_at(self, before: calendar.Moment, gap: int) -> int | None:
        if not self.counted_in_seconds():
            return None
        into = (before.minute * MINUTE + before.second) % self.period()
        if into + gap < self.period():
            return None
        return gap - (into + gap) % self.period()

    def advance(self, gap: int) -> None:
        before = self.moment()
        self.store_moment(calendar.advance(before, gap))
        step = self.increment_at(before, gap)
        if step is not None:
            self.raise_at(self.crystal.second_edge(self.now(), gap, step))

    def raise_at(self, edge: int) -> None:
        if self.interrupting():
            self.store.write(CD, self.store.read(CD) | IRQ_F)
            return
        if not self.crystal.continuous or self.masked():
            return
        self.crystal.edge = edge
        if self.crystal.pulsing(self.now()):
            self.store.write(CD, self.store.read(CD) | IRQ_F)

    def fast_tick(self, at: int) -> None:
        if self.counted_in_seconds() or self.stopped() or not self.oscillating:
            return
        edge = self.crystal.fast_edge(at)
        if edge is not None:
            self.raise_at(edge)

    def expire(self, at: int) -> None:
        if self.store.read(CE) & INT_STND or self.crystal.pulsing(at):
            return
        self.store.write(CD, self.store.read(CD) & ~IRQ_F & NIBBLE)

    def dated(self) -> bool:
        return bool(self.store.read(CD) & CAL_HW)

    def stopped(self) -> bool:
        return bool(self.store.read(CF) & STOPPED)

    def elapsed(self, current: int) -> int:
        stamped = self.store.stamp
        gap = current - stamped if current >= stamped else STAMP_LIMIT - stamped + current
        return 0 if gap > STAMP_LIMIT // 2 else gap

    def update(self, offset: int = 0) -> None:
        current = (self.seconds() - offset) & STAMP_MASK
        if not self.oscillating:
            self.store.stamp = current
            return
        if self.store.read(CD) & HOLD:
            return
        gap = 0 if self.stopped() else self.elapsed(current)
        if gap > 0:
            self.advance(gap)
            if self.enable & 1:
                self.set_read_flag()
        self.store.stamp = current

    def hour(self) -> int:
        if self.twenty_four_hour():
            return self.digit(H1) + self.digit(H10) * 10
        shown = self.digit(H1) + (self.digit(H10) & 0x1) * 10
        afternoon = bool(self.store.read(H10) & PM)
        if shown == NOON:
            return NOON if afternoon else 0
        return shown + NOON if afternoon else shown

    def store_hour(self, hour: int) -> None:
        if self.twenty_four_hour():
            self.put_digit(H1, hour % 10)
            self.put_digit(H10, hour // 10)
            self.store.write(H10, self.store.read(H10) & ~PM & NIBBLE)
            return
        shown = hour % NOON or NOON
        self.put_digit(H1, shown % 10)
        self.put_digit(H10, shown // 10)
        flagged = self.store.read(H10) & ~PM & NIBBLE
        self.store.write(H10, flagged | (PM if hour >= NOON else 0))

    def moment(self) -> calendar.Moment:
        year = self.digit(Y1) + self.digit(Y10) * 10
        return calendar.Moment(
            year=year + (1900 if year >= YEAR_PIVOT else 2000),
            month=self.digit(MO1) + self.digit(MO10) * 10,
            day=self.digit(D1) + self.digit(D10) * 10,
            hour=self.hour(),
            minute=self.digit(MI1) + self.digit(MI10) * 10,
            second=self.digit(S1) + self.digit(S10) * 10,
            weekday=self.digit(W),
        )

    def store_moment(self, moment: calendar.Moment) -> None:
        self.put_digit(S1, moment.second % 10)
        self.put_digit(S10, moment.second // 10)
        self.put_digit(MI1, moment.minute % 10)
        self.put_digit(MI10, moment.minute // 10)
        self.store_hour(moment.hour)
        self.put_digit(W, moment.weekday % calendar.WEEK)
        if not self.dated():
            return
        year = moment.year % 100
        self.put_digit(D1, moment.day % 10)
        self.put_digit(D10, moment.day // 10)
        self.put_digit(MO1, moment.month % 10)
        self.put_digit(MO10, moment.month // 10)
        self.put_digit(Y1, year % 10)
        self.put_digit(Y10, (year // 10) % 10)

    @override
    def __repr__(self) -> str:
        return f"<RTC-4513 {self.state} at {self.index}>"
