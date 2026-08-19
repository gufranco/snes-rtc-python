"""The Epson RTC-4513, as the SPC7110 presents it at three addresses.

This is a different chip from the Sharp part and a different protocol, not a
revision of it. Where the Sharp clock hands out a fixed sequence, this one is
addressed: a session is opened by enabling the chip, choosing a mode, and naming
an index, after which reads and writes walk forward from there and wrap at
sixteen.

Two of the sixteen registers are controls rather than time, and writing to them
does work rather than storing a value. One asks for a second to be added, or for
the minute to be rounded to the nearest, which is how a game offers to set the
clock without making the user wait for the top of the minute. The other stops the
counter, and a stopped counter really does stop: the elapsed time is discarded
rather than accumulated, so a clock stopped for a year comes back a year behind.

The year is two digits, read as 1990 through 2089. There is no window in the
silicon; the range is a convention, and a cartridge holding a year of 89 is a
2089 that a game will render as such.
"""

from . import calendar

ENABLE = 0x4840

DATA = 0x4841

STATUS = 0x4842

INACTIVE, MODE_SELECT, INDEX_SELECT, WRITING = "inactive", "mode", "index", "write"

LINEAR = 0x03
"""Name an index once, then walk forward writing from there."""

INDEXED = 0x0C
"""Name an index for each byte, which the games use for a single register."""

READY = 0x80

REGISTERS = 16

CONTROL_ZERO = 13

CONTROL_TWO = 15

ADD_SECOND = 0x02

ROUND_MINUTE = 0x08

STOP_AND_CLEAR = 0x01

STOP = 0x02

HALF_MINUTE = 30

MINUTE = 60

YEAR_PIVOT = 90

STAMP_LIMIT = 0x1_0000_0000


def _now():
    import time

    return int(time.time())


class Clock:
    """One RTC-4513, answering at the three addresses the SPC7110 maps it to."""

    def __init__(self, store, now=_now):
        self.store = store
        self.now = now
        self.state = INACTIVE
        self.mode = LINEAR
        self.index = 0
        self.enable = 0x00
        self.status = 0x00

    def reset(self):
        self.state = INACTIVE
        self.mode = LINEAR
        self.index = 0
        self.enable = 0x00
        self.status = 0x00
        return self

    def read(self, address):
        if address == ENABLE:
            return self.enable
        if address == DATA:
            return self.read_data()
        if address == STATUS:
            answered = self.status
            self.status &= ~READY & 0xFF
            return answered
        return 0x00

    def read_data(self):
        if self.state in (INACTIVE, MODE_SELECT):
            return 0x00
        self.status = READY
        value = self.store.read(self.index)
        self.index = (self.index + 1) % REGISTERS
        return value

    def write(self, address, value):
        if address == ENABLE:
            self.write_enable(value)
        elif address == DATA:
            self.write_data(value)

    def write_enable(self, value):
        """Opening or closing the chip, with the clock caught up on the way out.

        The catching up happens when the chip is switched off rather than on,
        which reads backwards and is what the part does. A session therefore sees
        the time as it stood when the previous session ended, and a game that
        opens the chip and reads immediately gets a stale second.
        """
        self.enable = value & 0xFF
        if not self.enable & 1:
            self.state = INACTIVE
            self.update()
            return
        self.status = READY
        self.state = MODE_SELECT

    def write_data(self, value):
        if self.state == MODE_SELECT:
            if value in (LINEAR, INDEXED):
                self.status = READY
                self.state = INDEX_SELECT
                self.mode = value
                self.index = 0
            return
        if self.state == INDEX_SELECT:
            self.status = READY
            self.index = value & (REGISTERS - 1)
            if self.mode == LINEAR:
                self.state = WRITING
            return
        if self.state == WRITING:
            self.status = READY
            self.act(value)
            self.store.write(self.index, value & 0x0F)
            self.index = (self.index + 1) % REGISTERS

    def act(self, value):
        """The work a write to a control register does before it is stored."""
        if self.index == CONTROL_ZERO:
            if value & ADD_SECOND:
                self.update(1)
            if value & ROUND_MINUTE:
                self.round_minute()
        elif self.index == CONTROL_TWO:
            self.stop(value)

    def round_minute(self):
        """Drop the seconds, and carry into the minute when past the halfway point."""
        self.update()
        second = self.store.read(0) + self.store.read(1) * 10
        self.store.write(0, 0)
        self.store.write(1, 0)
        if second >= HALF_MINUTE:
            self.update(MINUTE)

    def stop(self, value):
        """Halt the counter, clearing the seconds when asked with the first flag.

        The two flags are tested separately rather than as alternatives, so a
        write that sets both catches the clock up twice. The second catch-up finds
        no time has passed and changes nothing, which is why the difference is
        invisible until a script sets both in one write.
        """
        held = self.store.read(CONTROL_TWO)
        if value & STOP_AND_CLEAR and not held & STOP_AND_CLEAR:
            self.update()
            self.store.write(0, 0)
            self.store.write(1, 0)
        if value & STOP and not held & STOP:
            self.update()

    def stopped(self):
        """Whether either control register says the counter is not running."""
        return bool(self.store.read(CONTROL_ZERO) & 1 or self.store.read(CONTROL_TWO) & 3)

    def elapsed(self, current):
        """How long since the clock was last read, measured the way the chip does."""
        stamped = self.store.stamp
        gap = current - stamped if current >= stamped else STAMP_LIMIT - stamped + current
        return 0 if gap > STAMP_LIMIT // 2 else gap

    def update(self, offset=0):
        """Catch the stored time up, unless a control register says it is stopped.

        An offset does not add time here. It backdates the moment being recorded,
        so the clock is left one second or one minute behind where it would have
        been and gains that much on the next catch-up. Adding the offset directly
        would land two seconds away from what the chip does, which is what a
        script setting the increment flag reveals.
        """
        current = (self.now() - offset) & 0xFFFFFFFF
        gap = 0 if self.stopped() else self.elapsed(current)
        if gap > 0:
            self.store_moment(calendar.advance(self.moment(), gap))
        self.store.stamp = current

    def moment(self):
        """The stored time, with the two digit year read as the range this chip covers."""
        held = self.store
        year = held.read(10) + held.read(11) * 10
        return calendar.Moment(
            year=year + (1900 if year >= YEAR_PIVOT else 2000),
            month=held.read(8) + held.read(9) * 10,
            day=held.read(6) + held.read(7) * 10,
            hour=held.read(4) + held.read(5) * 10,
            minute=held.read(2) + held.read(3) * 10,
            second=held.read(0) + held.read(1) * 10,
            weekday=held.read(12),
        )

    def store_moment(self, moment):
        held = self.store
        year = moment.year % 100
        held.write(0, moment.second % 10)
        held.write(1, moment.second // 10)
        held.write(2, moment.minute % 10)
        held.write(3, moment.minute // 10)
        held.write(4, moment.hour % 10)
        held.write(5, moment.hour // 10)
        held.write(6, moment.day % 10)
        held.write(7, moment.day // 10)
        held.write(8, moment.month % 10)
        held.write(9, moment.month // 10)
        held.write(10, year % 10)
        held.write(11, (year // 10) % 10)
        held.write(12, moment.weekday % calendar.WEEK)

    def __repr__(self):
        return f"<RTC-4513 {self.state} at {self.index}>"
