"""The Epson RTC-4513, as the SPC7110 presents it at three addresses.

This is a different chip from the Sharp part and a different protocol, not a
revision of it. Where the Sharp clock hands out a fixed sequence, this one is
addressed: a session is opened by enabling the chip, choosing read mode or write
mode, and naming an index, after which reads and writes walk forward from there
and wrap at sixteen.

Everything here that concerns the chip itself is held to the manufacturer's own
application manual, transcribed fact by fact into ``conformance/hardware.json``
and gated by ``conformance/hardware.test.py``. Everything here that concerns how
the SPC7110 turns the chip's three-wire serial interface into three cartridge
addresses rests on a recording from an independent implementation, because Epson
never described a Super Nintendo cartridge and nobody else described this part.
``conformance/divergences.json`` names every place the two disagree.

Three of the sixteen registers are controls rather than time. The manual calls
them CD, CE and CF, and their bits are named here as it names them rather than
as an implementation guessed at them. The thirteen clock registers are four bits
wide but six of them carry a digit narrower than that, with the spare bits
holding an oscillator flag, a read flag, an AM/PM flag or free RAM, so a model
that treats every register as a four-bit digit reads a program's flag back as
part of the time.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import override

from . import calendar
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
"""The manual's write mode setting code, sent as the first nibble of a session."""

READ_MODE = 0x0C
"""The manual's read mode setting code.

The manual is explicit that these two codes select a direction rather than an
addressing scheme, and that anything else is ignored: "If the mode setting code
is set to something other than 'C' or '3', subsequent data are disregarded and
the DATA port remains in the input mode."
"""

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
"""Which bits of each register carry the BCD digit, from the manual's own table.

The count range column settles this independently of the bit names: a register
whose count stops at 5 cannot be using four bits, and one whose count stops at 1
is using a single bit. The spare bits are the oscillator flag on S10, the read
flag on MI10, H10, D10, MO10 and W, the AM/PM flag on H10, and free RAM on D10
and MO10 that the manual invites a program to use.
"""

OSC_FLAG = 0x8
"""S10 bit 3. Records an oscillation interruption, which is how a low battery shows."""

READ_FLAG = 0x8
"""Bit 3 of MI10, H10, D10, MO10 and W. Set when a second ticks during an open session."""

READ_FLAG_AT = (MI10, H10, D10, MO10, W)

PM = 0x4
"""H10 bit 2, one for PM and zero for AM, and meaningful only in twelve-hour notation."""

HOLD = 0x1

CAL_HW = 0x2

IRQ_F = 0x4

ADJUST = 0x8

RESET = 0x1

STOP = 0x2

HOURS_24 = 0x4

TEST = 0x8

STOPPED = RESET | STOP
"""The two bits the manual describes as stopping the clock. HOLD is not one of them."""

HALF_MINUTE = 30

MINUTE = 60

NOON = 12

YEAR_PIVOT = 90
"""Where a two digit year is taken to change century.

The manual gives the year as two BCD digits and never names a century, so this
is a convention carried over from the reference implementation rather than a
manufacturer fact. It is recorded as such in divergences.json under
epson-century-window, and it decides only which years are leap years, because
the digits themselves are what a program reads back.
"""

STAMP_LIMIT = 0x1_0000_0000


def _now() -> int:
    import time

    return int(time.time())


class Clock:
    """One RTC-4513, answering at the three addresses the SPC7110 maps it to."""

    __slots__ = ("enable", "index", "mode", "model", "now", "state", "status", "store")

    model: str

    def __init__(self, store: Store, now: Callable[[], int] = _now) -> None:
        self.store = store
        self.now = now
        self.state = INACTIVE
        self.mode = WRITE_MODE
        self.index = 0
        self.enable = 0x00
        self.status = 0x00

    def reset(self) -> Clock:
        self.state = INACTIVE
        self.mode = WRITE_MODE
        self.index = 0
        self.enable = 0x00
        self.status = 0x00
        return self

    def read(self, address: int) -> int:
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
        """One register, after which the address walks on and wraps at sixteen.

        Reading CD clears IRQ-F, which the manual describes as maintained "until
        the CD register has been read, and then returns to '0'".
        """
        if self.state in (INACTIVE, MODE_SELECT):
            return 0x00
        self.status = READY
        value = self.store.read(self.index) & NIBBLE
        if self.index == CD:
            self.store.write(CD, self.store.read(CD) & ~IRQ_F & NIBBLE)
        self.index = (self.index + 1) % REGISTERS
        return value

    def write(self, address: int, value: int) -> None:
        if address == ENABLE:
            self.write_enable(value)
        elif address == DATA:
            self.write_data(value)

    def write_enable(self, value: int) -> None:
        """Opening or closing the chip, which is the CE pin as the SPC7110 drives it.

        Closing catches the stored time up, clears the read flag and clears the
        test bit. The manual gives the last two directly: the fr flag "is set to
        '0' when the CE input becomes Low", and the TEST bit "is cleared by
        setting CE to Low".

        The catch-up itself is not a manufacturer behaviour and could not be. A
        real part counts continuously and has nothing to catch up; the catch-up
        exists only because this model learns the time from a reading taken at
        intervals. That it happens on the way out rather than the way in is
        settled by the recording alone, and is written down in divergences.json under
        epson-catch-up-placement, and it means a session reads the time as the
        previous session left it.
        """
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
        """One byte into the data port, which means something different at each step.

        The mode code is compared as a whole byte rather than as a nibble. On the
        part that distinction cannot arise, because the serial interface carries
        four bits and there is nothing above them; it is a property of how the
        SPC7110 turns a byte on the cartridge bus into a nibble at the chip, and
        no document describes that wrapper. The recording is the only evidence
        there is, and it compares the whole byte, so a write of 0x5C selects
        nothing even though its low nibble is the read mode code.
        """
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

    def write_register(self, value: int) -> None:
        """One register written, with the rules the manual attaches to each control.

        The clock registers take the value as it stands. The three control
        registers do not: IRQ-F cannot be written at all, the adjust bit does
        work and then clears itself, and HOLD, RESET and STOP each act on the
        edge that sets or clears them rather than on the value alone.
        """
        if self.index == CD:
            self.write_control_d(value)
        elif self.index == CF:
            self.write_control_f(value)
        else:
            self.store.write(self.index, value)

    def write_control_d(self, value: int) -> None:
        """Control register D: the adjust bit, the read-only flag, the range bit, HOLD.

        The manual on IRQ-F: "A write instruction for the IRQ-F bit is not
        executed." The written bit is therefore dropped and the held one kept.

        The adjust bit is held at one for 125 microseconds and then clears
        itself. This model has no sub-second time base, so the adjustment
        happens at once and the bit is stored clear, which is what a program
        polling for it to revert would eventually see. The lockout on writes to
        S1 through W during that window is not modelled, and divergences.json
        records why under epson-thirty-second-adjust-lockout-unmodelled.
        """
        held = self.store.read(CD) & NIBBLE
        settled = (value & ~IRQ_F & ~ADJUST & NIBBLE) | (held & IRQ_F)
        if settled & HOLD and not held & HOLD:
            self.update()
        self.store.write(CD, settled)
        if value & ADJUST:
            self.adjust_to_nearest_minute()
        if held & HOLD and not settled & HOLD:
            self.release_hold()

    def write_control_f(self, value: int) -> None:
        """Control register F: TEST, the notation bit, STOP and RESET.

        A RESET zeroes the seconds, stops the clock and forces TEST to zero, all
        three of which the manual states in one paragraph. It also cancels an
        adjustment still in flight: "if '1' is written to the RESET bit before
        the 30-second ADJ bit has reverted to '0', 30-second adjustment is not
        performed, and the 30-second ADJ bit is cleared to '0'". The adjustment
        never is in flight here, because this model performs it at once, so the
        cancellation has nothing to cancel and only the bit clearing is visible.

        The catch-up runs before the register changes, not after. On the part the
        counters run right up to the instant a stop bit is asserted, so a model
        that writes the bit first and then asks whether to catch up finds itself
        already stopped and throws the elapsed time away. That ordering also
        settles the reverse case: clearing a stop bit catches up while the clock
        is still halted, which discards the stopped interval and restarts the
        accounting from now, exactly as a halted counter does.
        """
        held = self.store.read(CF) & NIBBLE
        settled = value & NIBBLE
        if value & RESET:
            settled &= ~TEST & NIBBLE
        self.update()
        self.store.write(CF, settled)
        if value & RESET and not held & RESET:
            self.put_digit(S1, 0)
            self.put_digit(S10, 0)
            self.store.write(CD, self.store.read(CD) & ~ADJUST & NIBBLE)

    def release_hold(self) -> None:
        """The one second HOLD suppressed, handed back when HOLD is cleared.

        The manual: "This bit stops the 1-second digit incrementation. The clock
        continues to run, and the first incrementation after HOLD was set to '1'
        is compensated for when the hold condition is released (+1 second)." Only
        the first is compensated, which is why the manual's own procedure for
        writing the clock under HOLD warns that it "must be performed within 1
        second. Otherwise the seconds are lost."

        So a hold that spans a tick gives that one second back and a longer hold
        gives back the same one second, losing the rest. A hold that spans no
        tick gives nothing back.
        """
        if self.elapsed(self.now() & 0xFFFFFFFF) > 0:
            self.store_moment(calendar.advance(self.moment(), 1))
        self.store.stamp = self.now() & 0xFFFFFFFF

    def adjust_to_nearest_minute(self) -> None:
        """The 30-second adjustment, exactly as the manual defines it.

        "When this bit is written to, the seconds are reset to 00 of the current
        minute if currently less than 30, or to 00 of the next minute if
        currently 30 or more."
        """
        self.update()
        second = self.digit(S1) + self.digit(S10) * 10
        self.put_digit(S1, 0)
        self.put_digit(S10, 0)
        if second >= HALF_MINUTE:
            self.update(MINUTE)

    def digit(self, index: int) -> int:
        """The BCD digit a register carries, without the flags sharing it."""
        return self.store.read(index) & DIGIT_MASK[index]

    def put_digit(self, index: int, value: int) -> None:
        """A digit written, leaving the flags and free RAM in the register alone."""
        mask = DIGIT_MASK[index]
        kept = self.store.read(index) & ~mask & NIBBLE
        self.store.write(index, kept | (value & mask))

    def clear_read_flag(self) -> None:
        for index in READ_FLAG_AT:
            self.store.write(index, self.store.read(index) & ~READ_FLAG & NIBBLE)

    def set_read_flag(self) -> None:
        for index in READ_FLAG_AT:
            self.store.write(index, self.store.read(index) | READ_FLAG)

    def twenty_four_hour(self) -> bool:
        """Which notation the hour registers are in, from CF bit 2.

        The manual: "'1' means 24-hour and '0' means 12-hour notation." The
        register file powers up undefined, so a cartridge whose CF bit 2 happens
        to be clear runs in twelve-hour notation until a program sets it. That is
        the state the manual's power-on procedure exists to escape.
        """
        return bool(self.store.read(CF) & HOURS_24)

    def dated(self) -> bool:
        """Whether the date counters run, from CAL/HW in CD.

        "When this bit is '1': clock range is seconds to 10 years, and weekdays.
        When this bit is '0': clock range is seconds to 10 hours, and weekdays.
        When the bit is '0', the six registers D1 to Y10 can be used as 4-bit
        RAM."
        """
        return bool(self.store.read(CD) & CAL_HW)

    def stopped(self) -> bool:
        """Whether the counter is halted, which only STOP and RESET do.

        HOLD is deliberately absent. The manual's first sentence about it says
        the clock continues to run, and treating it as a stop is the single
        divergence here most likely to be visible in a shipped title, because
        setting the clock is what a game uses these bits for.
        """
        return bool(self.store.read(CF) & STOPPED)

    def elapsed(self, current: int) -> int:
        """How long since the clock was last read, measured the way the chip does."""
        stamped = self.store.stamp
        gap = current - stamped if current >= stamped else STAMP_LIMIT - stamped + current
        return 0 if gap > STAMP_LIMIT // 2 else gap

    def update(self, offset: int = 0) -> None:
        """Catch the stored time up, unless a control register says it is stopped.

        An offset does not add time here. It backdates the moment being recorded,
        so the clock is left one minute behind where it would have been and gains
        that much on the next catch-up. Adding the offset directly would land a
        minute away from what the chip does when the adjustment rounds upward.

        While HOLD is set the visible digits do not move, so the catch-up is
        skipped and the stamp is left where it is. Releasing HOLD is what settles
        the accounting, and it hands back exactly the one second the manual says
        is compensated.
        """
        if self.store.read(CD) & HOLD:
            return
        current = (self.now() - offset) & 0xFFFFFFFF
        gap = 0 if self.stopped() else self.elapsed(current)
        if gap > 0:
            self.store_moment(calendar.advance(self.moment(), gap))
            self.set_read_flag()
        self.store.stamp = current

    def hour(self) -> int:
        """The hour on a twenty four hour dial, whichever notation the chip is in.

        In twelve-hour notation the manual fixes h20 at zero and never increments
        it, so the tens digit is the single h10 bit and the hour runs 12, 1 to
        11, twice, with PM/AM saying which half. Twelve a.m. is zero and twelve
        p.m. is noon.
        """
        if self.twenty_four_hour():
            return self.digit(H1) + self.digit(H10) * 10
        shown = self.digit(H1) + (self.digit(H10) & 0x1) * 10
        afternoon = bool(self.store.read(H10) & PM)
        if shown == NOON:
            return NOON if afternoon else 0
        return shown + NOON if afternoon else shown

    def store_hour(self, hour: int) -> None:
        """The hour written back in whichever notation the chip is in.

        The manual on twenty four hour notation: "A write attempt to the PM/AM
        bit is disregarded, and the bit will always read '0'." So the flag is
        cleared rather than preserved when the chip is in that notation.
        """
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
        """The stored time, read through the digit fields rather than whole registers."""
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
        """The time written back, leaving flags, free RAM and dormant counters alone.

        With CAL/HW clear the manual makes D1 through Y10 free RAM, so the date
        is not written back at all and only the weekday follows the day. Those
        six registers hold whatever the program put in them.
        """
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
