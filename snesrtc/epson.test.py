import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesrtc import epson, store

FROZEN = 1_000_000_000

DATE = (0, 0, 0, 3, 2, 1, 8, 1, 8, 0, 6, 2)
"""Half past twelve on the eighteenth of August 2026, one digit per byte, low first.

This chip keeps the year as two digits and reads them as 1990 through 2089, so
twenty six is 2026 rather than 1926.
"""


def clock(at=FROZEN, **options):
    held = store.Store(cleared=True)
    held.stamp = at
    return epson.Clock(held, now=lambda: at, **options)


def open_session(chip, mode=epson.LINEAR, index=0):
    chip.write(epson.ENABLE, 0x01)
    chip.write(epson.DATA, mode)
    chip.write(epson.DATA, index)


def set_time(chip, digits):
    open_session(chip)
    for digit in digits:
        chip.write(epson.DATA, digit)


class SessionTest(unittest.TestCase):
    def test_a_chip_that_was_never_enabled_answers_nothing(self):
        chip = clock()

        self.assertEqual(chip.read(epson.DATA), 0x00)

    def test_enabling_it_is_not_enough_on_its_own(self):
        chip = clock()

        chip.write(epson.ENABLE, 0x01)

        self.assertEqual(chip.read(epson.DATA), 0x00)

    def test_a_mode_and_an_index_open_it_for_reading(self):
        chip = clock()
        open_session(chip)

        self.assertEqual(chip.read(epson.DATA), chip.store.read(0))

    def test_clearing_the_enable_bit_closes_it_again(self):
        chip = clock()
        open_session(chip)

        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.read(epson.DATA), 0x00)

    def test_a_mode_the_chip_does_not_know_leaves_the_session_unopened(self):
        chip = clock()
        chip.write(epson.ENABLE, 0x01)

        chip.write(epson.DATA, 0x07)

        self.assertEqual(chip.read(epson.DATA), 0x00)

    def test_the_enable_register_reads_back_what_was_put_there(self):
        chip = clock()

        chip.write(epson.ENABLE, 0x01)

        self.assertEqual(chip.read(epson.ENABLE), 0x01)

    def test_an_address_the_chip_does_not_answer_gives_nothing_back(self):
        chip = clock()

        self.assertEqual(chip.read(0x4843), 0x00)

    def test_and_writing_to_one_changes_nothing(self):
        chip = clock()
        before = list(chip.store.bytes)

        chip.write(0x4843, 0x0F)

        self.assertEqual(chip.store.bytes, before)


class ReadTest(unittest.TestCase):
    def test_reading_walks_forward_through_the_bytes(self):
        chip = clock()
        set_time(chip, DATE)
        open_session(chip)

        answered = [chip.read(epson.DATA) for _ in range(12)]

        self.assertEqual(answered, list(DATE))

    def test_the_index_wraps_at_sixteen_rather_than_running_off(self):
        chip = clock()
        open_session(chip, index=15)
        chip.read(epson.DATA)

        chip.read(epson.DATA)

        self.assertEqual(chip.index, 1)

    def test_a_session_can_start_partway_along(self):
        chip = clock()
        set_time(chip, DATE)
        open_session(chip, index=4)

        self.assertEqual(chip.read(epson.DATA), DATE[4])


class StatusTest(unittest.TestCase):
    def test_the_status_register_reports_ready_after_a_transfer(self):
        chip = clock()
        open_session(chip)

        self.assertEqual(chip.read(epson.STATUS) & 0x80, 0x80)

    def test_and_reading_it_clears_the_bit(self):
        chip = clock()
        open_session(chip)
        chip.read(epson.STATUS)

        self.assertEqual(chip.read(epson.STATUS) & 0x80, 0x00)


class WriteTest(unittest.TestCase):
    def test_a_written_digit_lands_where_the_index_points(self):
        chip = clock()
        open_session(chip, index=3)

        chip.write(epson.DATA, 0x05)

        self.assertEqual(chip.store.read(3), 0x05)

    def test_only_the_low_four_bits_survive(self):
        chip = clock()
        open_session(chip, index=3)

        chip.write(epson.DATA, 0xF5)

        self.assertEqual(chip.store.read(3), 0x05)

    def test_the_index_moves_on_after_each_one(self):
        chip = clock()
        open_session(chip, index=3)

        chip.write(epson.DATA, 0x05)

        self.assertEqual(chip.index, 4)

    def test_the_indexed_mode_writes_one_byte_and_stops(self):
        chip = clock()
        chip.write(epson.ENABLE, 0x01)
        chip.write(epson.DATA, epson.INDEXED)
        chip.write(epson.DATA, 0x03)

        self.assertEqual(chip.state, epson.INDEX_SELECT)


class ControlTest(unittest.TestCase):
    def test_asking_for_one_more_second_shows_up_on_the_next_catch_up(self):
        chip = clock()
        set_time(chip, DATE)
        open_session(chip, index=13)
        chip.write(epson.DATA, 0x02)

        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.store.read(0), 1)

    def test_and_not_at_the_moment_it_is_asked_for(self):
        chip = clock()
        set_time(chip, DATE)
        open_session(chip, index=13)

        chip.write(epson.DATA, 0x02)

        self.assertEqual(chip.store.read(0), DATE[0])

    def test_rounding_down_clears_the_seconds(self):
        chip = clock()
        set_time(chip, (*DATE[:1], 2, *DATE[2:]))
        open_session(chip, index=13)

        chip.write(epson.DATA, 0x08)

        self.assertEqual((chip.store.read(0), chip.store.read(1)), (0, 0))

    def test_rounding_up_from_past_the_half_minute_carries_into_the_minute(self):
        chip = clock()
        set_time(chip, (0, 4, *DATE[2:]))
        open_session(chip, index=13)
        chip.write(epson.DATA, 0x08)

        chip.write(epson.ENABLE, 0x00)

        self.assertEqual((chip.store.read(2), chip.store.read(3)), (1, 3))

    def test_stopping_the_clock_clears_the_seconds_with_it(self):
        chip = clock()
        set_time(chip, (5, 2, *DATE[2:]))
        open_session(chip, index=15)

        chip.write(epson.DATA, 0x01)

        self.assertEqual((chip.store.read(0), chip.store.read(1)), (0, 0))

    def test_a_stopped_clock_does_not_move_when_time_passes(self):
        held = store.Store(cleared=True)
        held.stamp = FROZEN
        moment = [FROZEN]
        chip = epson.Clock(held, now=lambda: moment[0])
        set_time(chip, DATE)
        open_session(chip, index=15)
        chip.write(epson.DATA, 0x02)

        moment[0] = FROZEN + 3600
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.store.read(4), DATE[4])

    def test_the_other_stop_flag_stops_it_too(self):
        held = store.Store(cleared=True)
        held.stamp = FROZEN
        moment = [FROZEN]
        chip = epson.Clock(held, now=lambda: moment[0])
        set_time(chip, DATE)
        open_session(chip, index=13)
        chip.write(epson.DATA, 0x01)

        moment[0] = FROZEN + 3600
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual(chip.store.read(4), DATE[4])


class TimeTest(unittest.TestCase):
    def test_a_running_clock_moves_forward_when_the_session_closes(self):
        held = store.Store(cleared=True)
        held.stamp = FROZEN
        moment = [FROZEN]
        chip = epson.Clock(held, now=lambda: moment[0])
        set_time(chip, DATE)

        moment[0] = FROZEN + 65
        chip.write(epson.ENABLE, 0x00)

        self.assertEqual((chip.store.read(2), chip.store.read(0)), (1, 5))

    def test_opening_a_session_shows_the_time_as_the_last_one_left_it(self):
        held = store.Store(cleared=True)
        held.stamp = FROZEN
        moment = [FROZEN]
        chip = epson.Clock(held, now=lambda: moment[0])
        set_time(chip, DATE)

        moment[0] = FROZEN + 65
        open_session(chip)

        self.assertEqual(chip.store.read(2), DATE[2])

    def test_the_year_is_read_as_the_range_this_chip_covers(self):
        chip = clock()
        set_time(chip, (*DATE[:10], 9, 9))

        self.assertEqual(chip.moment().year, 1999)

    def test_and_a_small_year_belongs_to_the_century_after(self):
        chip = clock()
        set_time(chip, DATE)

        self.assertEqual(chip.moment().year, 2026)


class ResetTest(unittest.TestCase):
    def test_a_reset_closes_any_session(self):
        chip = clock()
        open_session(chip)

        chip.reset()

        self.assertEqual(chip.read(epson.DATA), 0x00)

    def test_a_chip_prints_as_its_state_and_its_place(self):
        self.assertIn("inactive", repr(clock()))


class DefaultClockTest(unittest.TestCase):
    def test_a_chip_given_no_clock_reads_the_one_the_machine_has(self):
        reading = epson._now()

        self.assertGreater(reading, 1_600_000_000)


if __name__ == "__main__":
    unittest.main()
