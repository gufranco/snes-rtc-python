import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesrtc import epson, store

FROZEN = 1_000_000_000

DATE = (0, 0, 0, 3, 2, 1, 8, 1, 8, 0, 6, 2)
"""Half past twelve on the eighteenth of August 2026, one digit per byte, low first.

This chip keeps the year as two digits. The manual attaches no century to them,
so the range this package reads them over is a convention recorded in
divergences.json rather than a manufacturer fact.
"""

CONFIGURED = epson.HOURS_24
"""Control register F as the manual's power-on procedure leaves it.

The manual is explicit that at power-on every register is undefined, so a chip
that has not been through the procedure is not in twenty four hour notation and
its date counters are not necessarily running. Tests that mean to exercise a
configured chip say so here rather than relying on a cleared store, because a
cleared store is a chip whose notation bit happens to be zero.
"""

DATED = epson.CAL_HW


def clock(at: int = FROZEN, control_f: int = CONFIGURED, control_d: int = DATED) -> epson.Clock:
    held = store.Store(cleared=True)
    held.stamp = at
    held.write(epson.CF, control_f)
    held.write(epson.CD, control_d)
    return epson.Clock(held, now=lambda: at)


def moving(start: int = FROZEN) -> tuple[epson.Clock, list[int]]:
    held = store.Store(cleared=True)
    held.stamp = start
    held.write(epson.CF, CONFIGURED)
    held.write(epson.CD, DATED)
    hand = [start]
    return epson.Clock(held, now=lambda: hand[0]), hand


def open_session(chip: epson.Clock, mode: int = epson.WRITE_MODE, index: int = 0) -> None:
    chip.write(epson.ENABLE, 0x01)
    chip.write(epson.DATA, mode)
    chip.write(epson.DATA, index)


def set_time(chip: epson.Clock, digits: tuple[int, ...]) -> None:
    open_session(chip)
    for digit in digits:
        chip.write(epson.DATA, digit)


class SessionTest(unittest.TestCase):
    def test_a_chip_that_was_never_enabled_answers_nothing(self) -> None:
        chip = clock()

        self.assertEqual(chip.read(epson.DATA), 0x00)

    def test_enabling_it_is_not_enough_on_its_own(self) -> None:
        chip = clock()

        chip.write(epson.ENABLE, 0x01)

        self.assertEqual(chip.read(epson.DATA), 0x00)

    def test_the_write_mode_code_and_an_index_open_a_session(self) -> None:
        chip = clock()

        open_session(chip)

        self.assertEqual(chip.state, epson.WRITING)

    def test_the_read_mode_code_opens_one_that_only_reads(self) -> None:
        chip = clock()

        open_session(chip, mode=epson.READ_MODE)

        self.assertEqual(chip.state, epson.READING)

    def test_clearing_the_enable_bit_closes_it_again(self) -> None:
        chip = clock()
        open_session(chip)

        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.read(epson.DATA), 0x00)

    def test_a_mode_code_the_manual_does_not_name_leaves_the_session_unopened(self) -> None:
        chip = clock()
        chip.write(epson.ENABLE, 0x01)

        chip.write(epson.DATA, 0x07)

        self.assertEqual(chip.read(epson.DATA), 0x00)

    def test_the_enable_register_reads_back_what_was_put_there(self) -> None:
        chip = clock()

        chip.write(epson.ENABLE, 0x01)

        self.assertEqual(chip.read(epson.ENABLE), 0x01)

    def test_an_address_the_chip_does_not_answer_gives_nothing_back(self) -> None:
        chip = clock()

        self.assertEqual(chip.read(0x4843), 0x00)

    def test_and_writing_to_one_changes_nothing(self) -> None:
        chip = clock()
        before = list(chip.store.bytes)

        chip.write(0x4843, 0x0F)

        self.assertEqual(chip.store.bytes, before)


class ReadTest(unittest.TestCase):
    def test_reading_walks_forward_through_the_registers(self) -> None:
        chip = clock()
        set_time(chip, DATE)
        open_session(chip, mode=epson.READ_MODE)

        answered = [chip.read(epson.DATA) for _ in range(12)]

        self.assertEqual(answered, list(DATE))

    def test_the_address_wraps_after_the_last_register(self) -> None:
        chip = clock()
        open_session(chip, index=15)

        chip.read(epson.DATA)

        self.assertEqual(chip.index, 0)

    def test_a_session_can_start_partway_along(self) -> None:
        chip = clock()
        set_time(chip, DATE)
        open_session(chip, mode=epson.READ_MODE, index=4)

        self.assertEqual(chip.read(epson.DATA), DATE[4])

    def test_a_write_during_a_read_mode_session_is_ignored(self) -> None:
        chip = clock()
        set_time(chip, DATE)
        open_session(chip, mode=epson.READ_MODE, index=4)

        chip.write(epson.DATA, 0x09)

        self.assertEqual(chip.read(epson.DATA), DATE[4])


class StatusTest(unittest.TestCase):
    def test_the_status_register_reports_ready_after_a_transfer(self) -> None:
        chip = clock()
        open_session(chip)

        self.assertEqual(chip.read(epson.STATUS) & 0x80, 0x80)

    def test_and_reading_it_clears_the_bit(self) -> None:
        chip = clock()
        open_session(chip)
        chip.read(epson.STATUS)

        self.assertEqual(chip.read(epson.STATUS) & 0x80, 0x00)


class WriteTest(unittest.TestCase):
    def test_a_written_digit_lands_where_the_address_points(self) -> None:
        chip = clock()
        open_session(chip, index=2)

        chip.write(epson.DATA, 0x05)

        self.assertEqual(chip.store.read(2), 0x05)

    def test_only_the_low_four_bits_survive(self) -> None:
        chip = clock()
        open_session(chip, index=2)

        chip.write(epson.DATA, 0xF5)

        self.assertEqual(chip.store.read(2), 0x05)

    def test_the_address_moves_on_after_each_one(self) -> None:
        chip = clock()
        open_session(chip, index=2)

        chip.write(epson.DATA, 0x05)

        self.assertEqual(chip.index, 3)


class DigitFieldTest(unittest.TestCase):
    """The manual gives six registers a digit narrower than the register.

    The count range column settles it without reading the bit names at all: a
    register that counts to 5 is not holding a four bit digit, and one that
    counts to 1 is holding a single bit.
    """

    def test_the_tens_of_seconds_digit_stops_at_three_bits(self) -> None:
        chip = clock()
        set_time(chip, DATE)
        chip.store.write(epson.S10, 0x8 | 0x4)

        self.assertEqual(chip.moment().second, DATE[0] + 40)

    def test_the_oscillator_flag_is_not_part_of_the_seconds(self) -> None:
        chip = clock()
        set_time(chip, DATE)
        chip.store.write(epson.S10, epson.OSC_FLAG)

        self.assertEqual(chip.moment().second, DATE[0])

    def test_the_tens_of_months_digit_is_one_bit_wide(self) -> None:
        chip = clock()
        set_time(chip, DATE)
        chip.store.write(epson.MO10, 0xF)

        self.assertEqual(chip.moment().month, DATE[8] + 10)

    def test_the_free_ram_beside_the_tens_of_days_is_not_part_of_the_date(self) -> None:
        chip = clock()
        set_time(chip, DATE)
        chip.store.write(epson.D10, 0x4 | 0x1)

        self.assertEqual(chip.moment().day, DATE[6] + 10)

    def test_the_weekday_counter_is_three_bits(self) -> None:
        chip = clock()
        set_time(chip, DATE)
        chip.store.write(epson.W, 0xF)

        self.assertEqual(chip.moment().weekday, 7 & 0x7)

    def test_writing_the_time_back_leaves_free_ram_alone(self) -> None:
        chip, hand = moving()
        set_time(chip, DATE)
        chip.store.write(epson.MO10, chip.store.read(epson.MO10) | 0x4)

        hand[0] = FROZEN + 86_400
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.store.read(epson.MO10) & 0x4, 0x4)


class NotationTest(unittest.TestCase):
    """Twelve hour notation, which control register F bit 2 selects.

    The manual fixes h20 at zero in this notation and never increments it, so
    the hour runs twelve then one to eleven, twice, with the PM flag saying
    which half of the day it is.
    """

    def test_a_configured_chip_reads_hours_on_a_twenty_four_hour_dial(self) -> None:
        chip = clock()
        set_time(chip, DATE)

        self.assertEqual(chip.moment().hour, 12)

    def test_the_afternoon_flag_carries_the_hour_past_noon(self) -> None:
        chip = clock(control_f=0)
        set_time(chip, (0, 0, 0, 0, 3, 0, 8, 1, 8, 0, 6, 2))
        chip.store.write(epson.H10, chip.store.read(epson.H10) | epson.PM)

        self.assertEqual(chip.moment().hour, 15)

    def test_twelve_in_the_morning_is_the_top_of_the_day(self) -> None:
        chip = clock(control_f=0)
        set_time(chip, (0, 0, 0, 0, 2, 1, 8, 1, 8, 0, 6, 2))

        self.assertEqual(chip.moment().hour, 0)

    def test_twelve_in_the_afternoon_is_noon(self) -> None:
        chip = clock(control_f=0)
        set_time(chip, (0, 0, 0, 0, 2, 1, 8, 1, 8, 0, 6, 2))
        chip.store.write(epson.H10, chip.store.read(epson.H10) | epson.PM)

        self.assertEqual(chip.moment().hour, 12)

    def test_the_afternoon_flag_is_set_when_the_time_is_written_back(self) -> None:
        chip, hand = moving()
        chip.store.write(epson.CF, 0)
        set_time(chip, (0, 0, 0, 0, 1, 1, 8, 1, 8, 0, 6, 2))

        hand[0] = FROZEN + 7200
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.store.read(epson.H10) & epson.PM, epson.PM)

    def test_and_cleared_again_in_the_morning(self) -> None:
        chip, hand = moving()
        chip.store.write(epson.CF, 0)
        set_time(chip, (0, 0, 0, 0, 1, 1, 8, 1, 8, 0, 6, 2))
        chip.store.write(epson.H10, chip.store.read(epson.H10) | epson.PM)

        hand[0] = FROZEN + 43_200
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.store.read(epson.H10) & epson.PM, 0)

    def test_the_tens_of_hours_bit_never_rises_in_twelve_hour_notation(self) -> None:
        chip, hand = moving()
        chip.store.write(epson.CF, 0)
        set_time(chip, (0, 0, 0, 0, 1, 1, 8, 1, 8, 0, 6, 2))

        hand[0] = FROZEN + 7200
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.store.read(epson.H10) & 0x2, 0)

    def test_a_write_to_the_afternoon_flag_is_disregarded_on_a_twenty_four_hour_dial(
        self,
    ) -> None:
        chip, hand = moving()
        set_time(chip, DATE)
        chip.store.write(epson.H10, chip.store.read(epson.H10) | epson.PM)

        hand[0] = FROZEN + 60
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.store.read(epson.H10) & epson.PM, 0)


class ClockRangeTest(unittest.TestCase):
    """CAL/HW, which the manual says decides how much of the counter chain runs."""

    def test_a_dated_chip_carries_the_day_over_at_midnight(self) -> None:
        chip, hand = moving()
        set_time(chip, DATE)

        hand[0] = FROZEN + 86_400
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.store.read(epson.D1), DATE[6] + 1)

    def test_an_undated_chip_leaves_the_date_registers_as_the_program_left_them(
        self,
    ) -> None:
        chip, hand = moving()
        chip.store.write(epson.CD, 0)
        set_time(chip, DATE)

        hand[0] = FROZEN + 86_400
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.store.read(epson.D1), DATE[6])

    def test_but_the_weekday_still_counts(self) -> None:
        chip, hand = moving()
        chip.store.write(epson.CD, 0)
        set_time(chip, DATE)
        before = chip.store.read(epson.W)

        hand[0] = FROZEN + 86_400
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.store.read(epson.W), (before + 1) % 7)


class ControlRegisterDTest(unittest.TestCase):
    def test_the_interrupt_flag_cannot_be_written(self) -> None:
        chip = clock()
        open_session(chip, index=epson.CD)

        chip.write(epson.DATA, epson.IRQ_F | epson.CAL_HW)

        self.assertEqual(chip.store.read(epson.CD) & epson.IRQ_F, 0)

    def test_a_held_interrupt_flag_survives_a_write(self) -> None:
        chip = clock(control_d=DATED | epson.IRQ_F)
        open_session(chip, index=epson.CD)

        chip.write(epson.DATA, epson.CAL_HW)

        self.assertEqual(chip.store.read(epson.CD) & epson.IRQ_F, epson.IRQ_F)

    def test_reading_the_register_clears_the_interrupt_flag(self) -> None:
        chip = clock(control_d=DATED | epson.IRQ_F)
        open_session(chip, mode=epson.READ_MODE, index=epson.CD)

        chip.read(epson.DATA)

        self.assertEqual(chip.store.read(epson.CD) & epson.IRQ_F, 0)

    def test_the_adjustment_bit_does_not_latch(self) -> None:
        chip = clock()
        set_time(chip, DATE)
        open_session(chip, index=epson.CD)

        chip.write(epson.DATA, DATED | epson.ADJUST)

        self.assertEqual(chip.store.read(epson.CD) & epson.ADJUST, 0)

    def test_adjusting_below_the_half_minute_drops_the_seconds(self) -> None:
        chip = clock()
        set_time(chip, (*DATE[:1], 2, *DATE[2:]))
        open_session(chip, index=epson.CD)

        chip.write(epson.DATA, DATED | epson.ADJUST)

        self.assertEqual((chip.store.read(epson.S1), chip.store.read(epson.S10)), (0, 0))

    def test_adjusting_from_past_it_carries_into_the_next_minute(self) -> None:
        chip = clock()
        set_time(chip, (0, 4, *DATE[2:]))
        open_session(chip, index=epson.CD)
        chip.write(epson.DATA, DATED | epson.ADJUST)

        chip.write(epson.ENABLE, 0x00)

        self.assertEqual((chip.store.read(epson.MI1), chip.store.read(epson.MI10)), (1, 3))

    def test_the_range_bit_adds_no_time_of_its_own(self) -> None:
        chip = clock()
        set_time(chip, DATE)
        open_session(chip, index=epson.CD)
        chip.write(epson.DATA, epson.CAL_HW)

        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.store.read(epson.S1), DATE[0])


class HoldTest(unittest.TestCase):
    """HOLD, which the manual says freezes the digit while the clock keeps running."""

    def test_a_held_clock_does_not_move_while_it_is_held(self) -> None:
        chip, hand = moving()
        set_time(chip, DATE)
        open_session(chip, index=epson.CD)
        chip.write(epson.DATA, DATED | epson.HOLD)

        hand[0] = FROZEN + 300
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.store.read(epson.MI1), DATE[2])

    def test_releasing_it_hands_back_the_one_second_it_suppressed(self) -> None:
        chip, hand = moving()
        set_time(chip, DATE)
        open_session(chip, index=epson.CD)
        chip.write(epson.DATA, DATED | epson.HOLD)
        hand[0] = FROZEN + 300
        open_session(chip, index=epson.CD)

        chip.write(epson.DATA, DATED)

        self.assertEqual(chip.store.read(epson.S1), DATE[0] + 1)

    def test_and_only_that_one_second_however_long_the_hold_lasted(self) -> None:
        chip, hand = moving()
        set_time(chip, DATE)
        open_session(chip, index=epson.CD)
        chip.write(epson.DATA, DATED | epson.HOLD)
        hand[0] = FROZEN + 86_400
        open_session(chip, index=epson.CD)

        chip.write(epson.DATA, DATED)

        self.assertEqual(chip.store.read(epson.MI1), DATE[2])

    def test_a_hold_that_spans_no_tick_gives_nothing_back(self) -> None:
        chip = clock()
        set_time(chip, DATE)
        open_session(chip, index=epson.CD)
        chip.write(epson.DATA, DATED | epson.HOLD)
        open_session(chip, index=epson.CD)

        chip.write(epson.DATA, DATED)

        self.assertEqual(chip.store.read(epson.S1), DATE[0])

    def test_setting_it_brings_the_digits_current_first(self) -> None:
        chip, hand = moving()
        set_time(chip, DATE)
        hand[0] = FROZEN + 65
        open_session(chip, index=epson.CD)

        chip.write(epson.DATA, DATED | epson.HOLD)

        self.assertEqual(chip.store.read(epson.MI1), DATE[2] + 1)


class ControlRegisterFTest(unittest.TestCase):
    def test_a_reset_zeroes_the_seconds(self) -> None:
        chip = clock()
        set_time(chip, (5, 2, *DATE[2:]))
        open_session(chip, index=epson.CF)

        chip.write(epson.DATA, CONFIGURED | epson.RESET)

        self.assertEqual((chip.store.read(epson.S1), chip.store.read(epson.S10)), (0, 0))

    def test_a_reset_forces_the_test_bit_down(self) -> None:
        chip = clock(control_f=CONFIGURED | epson.TEST)
        open_session(chip, index=epson.CF)

        chip.write(epson.DATA, CONFIGURED | epson.TEST | epson.RESET)

        self.assertEqual(chip.store.read(epson.CF) & epson.TEST, 0)

    def test_closing_the_chip_clears_the_test_bit(self) -> None:
        chip = clock()
        open_session(chip, index=epson.CF)
        chip.write(epson.DATA, CONFIGURED | epson.TEST)

        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.store.read(epson.CF) & epson.TEST, 0)

    def test_a_stopped_clock_does_not_move_when_time_passes(self) -> None:
        chip, hand = moving()
        set_time(chip, DATE)
        open_session(chip, index=epson.CF)
        chip.write(epson.DATA, CONFIGURED | epson.STOP)

        hand[0] = FROZEN + 3600
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.store.read(epson.H1), DATE[4])

    def test_a_reset_stops_it_too(self) -> None:
        chip, hand = moving()
        set_time(chip, DATE)
        open_session(chip, index=epson.CF)
        chip.write(epson.DATA, CONFIGURED | epson.RESET)

        hand[0] = FROZEN + 3600
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.store.read(epson.H1), DATE[4])

    def test_clearing_both_lets_it_run_again(self) -> None:
        chip, hand = moving()
        set_time(chip, DATE)
        open_session(chip, index=epson.CF)
        chip.write(epson.DATA, CONFIGURED | epson.STOP)
        open_session(chip, index=epson.CF)
        chip.write(epson.DATA, CONFIGURED)

        hand[0] = FROZEN + 3600
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.store.read(epson.H1), DATE[4] + 1)


class ReadFlagTest(unittest.TestCase):
    def test_closing_the_chip_clears_the_read_flag(self) -> None:
        chip = clock()
        for index in epson.READ_FLAG_AT:
            chip.store.write(index, chip.store.read(index) | epson.READ_FLAG)

        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(
            [chip.store.read(at) & epson.READ_FLAG for at in epson.READ_FLAG_AT], [0] * 5
        )

    def test_a_second_ticking_during_an_open_session_raises_it(self) -> None:
        chip, hand = moving()
        set_time(chip, DATE)
        chip.write(epson.ENABLE, 0x00)
        hand[0] = FROZEN + 5
        open_session(chip, index=epson.CF)

        chip.write(epson.DATA, CONFIGURED | epson.RESET)

        self.assertEqual(chip.store.read(epson.MI10) & epson.READ_FLAG, epson.READ_FLAG)


class TimeTest(unittest.TestCase):
    def test_a_running_clock_moves_forward_when_the_session_closes(self) -> None:
        chip, hand = moving()
        set_time(chip, DATE)

        hand[0] = FROZEN + 65
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual((chip.store.read(epson.MI1), chip.store.read(epson.S1)), (1, 5))

    def test_opening_a_session_shows_the_time_as_the_last_one_left_it(self) -> None:
        chip, hand = moving()
        set_time(chip, DATE)

        hand[0] = FROZEN + 65
        open_session(chip)

        self.assertEqual(chip.store.read(epson.MI1), DATE[2])

    def test_an_impossible_date_corrects_on_the_next_day(self) -> None:
        chip, hand = moving()
        set_time(chip, (0, 0, 0, 0, 0, 0, 1, 3, 1, 1, 3, 9))

        hand[0] = FROZEN + 86_400
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(
            (
                chip.store.read(epson.D1),
                chip.store.read(epson.D10),
                chip.store.read(epson.MO1),
                chip.store.read(epson.MO10),
            ),
            (1, 0, 2, 1),
        )

    def test_a_leap_day_is_kept_where_the_year_has_one(self) -> None:
        chip, hand = moving()
        set_time(chip, (0, 0, 0, 0, 0, 0, 8, 2, 2, 0, 4, 2))

        hand[0] = FROZEN + 86_400
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual((chip.store.read(epson.D1), chip.store.read(epson.MO1)), (9, 2))

    def test_and_skipped_where_it_does_not(self) -> None:
        chip, hand = moving()
        set_time(chip, (0, 0, 0, 0, 0, 0, 8, 2, 2, 0, 5, 2))

        hand[0] = FROZEN + 86_400
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual((chip.store.read(epson.D1), chip.store.read(epson.MO1)), (1, 3))

    def test_the_year_is_read_as_the_range_this_package_covers(self) -> None:
        chip = clock()
        set_time(chip, (*DATE[:10], 9, 9))

        self.assertEqual(chip.moment().year, 1999)

    def test_and_a_small_year_belongs_to_the_century_after(self) -> None:
        chip = clock()
        set_time(chip, DATE)

        self.assertEqual(chip.moment().year, 2026)


class ResetTest(unittest.TestCase):
    def test_a_reset_closes_any_session(self) -> None:
        chip = clock()
        open_session(chip)

        chip.reset()

        self.assertEqual(chip.read(epson.DATA), 0x00)

    def test_a_chip_prints_as_its_state_and_its_place(self) -> None:
        self.assertIn("inactive", repr(clock()))


class DefaultClockTest(unittest.TestCase):
    def test_a_chip_given_no_clock_reads_the_one_the_machine_has(self) -> None:
        reading = epson._now()

        self.assertGreater(reading, 1_600_000_000)


if __name__ == "__main__":
    unittest.main()
