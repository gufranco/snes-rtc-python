import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesrtc import calendar, sharp, store

FROZEN = 1_000_000_000


def clock(at: int = FROZEN, **options: Any) -> sharp.Clock:
    held = store.Store(cleared=True)
    held.stamp = at
    return sharp.Clock(held, now=lambda: at, **options)


def set_time(chip: sharp.Clock, digits: tuple[int, ...]) -> None:
    chip.write(sharp.CONTROL, 0x0E)
    chip.write(sharp.CONTROL, 0x00)
    for digit in digits:
        chip.write(sharp.CONTROL, digit)


DATE = (0, 0, 0, 3, 2, 1, 8, 1, 8, 6, 9, 9)
"""Half past twelve on the eighteenth of August 1996, one digit per byte, low first.

The year is three digits with a thousand added, so the chip reaches 1000 to 1999
and the games that carry it use the upper end of that.
"""


class ReadTest(unittest.TestCase):
    def test_a_read_before_anything_answers_the_ready_marker(self) -> None:
        chip = clock()

        self.assertEqual(chip.read(sharp.DATA), 0x0F)

    def test_the_thirteen_bytes_then_come_out_in_order(self) -> None:
        chip = clock()
        chip.read(sharp.DATA)

        answered = [chip.read(sharp.DATA) for _ in range(13)]

        self.assertEqual(len(answered), 13)

    def test_and_the_marker_comes_round_again_at_the_end(self) -> None:
        chip = clock()
        chip.read(sharp.DATA)
        for _ in range(13):
            chip.read(sharp.DATA)

        self.assertEqual(chip.read(sharp.DATA), 0x0F)

    def test_the_sequence_then_starts_over(self) -> None:
        chip = clock()
        for _ in range(15):
            chip.read(sharp.DATA)

        self.assertEqual(chip.read(sharp.DATA), 0x0F)

    def test_a_read_while_not_in_reading_mode_answers_nothing(self) -> None:
        chip = clock()
        chip.write(sharp.CONTROL, 0x0E)

        self.assertEqual(chip.read(sharp.DATA), 0x00)

    def test_a_read_of_an_address_the_chip_does_not_answer_gives_the_open_bus(self) -> None:
        chip = clock()
        chip.open_bus = 0x42

        self.assertEqual(chip.read(0x2802), 0x42)


class WriteTest(unittest.TestCase):
    def test_a_written_time_reads_back_as_it_was_written(self) -> None:
        chip = clock()
        set_time(chip, DATE)

        chip.write(sharp.CONTROL, 0x0D)
        chip.read(sharp.DATA)
        answered = [chip.read(sharp.DATA) for _ in range(12)]

        self.assertEqual(answered, list(DATE))

    def test_the_weekday_is_worked_out_rather_than_written(self) -> None:
        chip = clock()
        set_time(chip, DATE)

        chip.write(sharp.CONTROL, 0x0D)
        chip.read(sharp.DATA)
        answered = [chip.read(sharp.DATA) for _ in range(13)]

        self.assertEqual(answered[12], calendar.weekday(1996, 8, 18))

    def test_only_the_low_four_bits_of_a_written_byte_are_kept(self) -> None:
        chip = clock()
        chip.write(sharp.CONTROL, 0x0E)
        chip.write(sharp.CONTROL, 0x00)

        chip.write(sharp.CONTROL, 0xF7)

        self.assertEqual(chip.store.read(0), 0x07)

    def test_writing_past_the_twelfth_byte_is_ignored(self) -> None:
        chip = clock()
        set_time(chip, DATE)

        chip.write(sharp.CONTROL, 0x09)

        self.assertNotEqual(chip.store.read(0), 0x09)

    def test_a_write_outside_writing_mode_changes_nothing(self) -> None:
        chip = clock()
        before = list(chip.store.bytes)

        chip.write(sharp.CONTROL, 0x07)

        self.assertEqual(chip.store.bytes, before)

    def test_a_write_to_an_address_the_chip_does_not_answer_changes_nothing(self) -> None:
        chip = clock()
        before = list(chip.store.bytes)

        chip.write(0x2800, 0x07)

        self.assertEqual(chip.store.bytes, before)


class CommandTest(unittest.TestCase):
    def test_the_reset_command_clears_the_thirteen_time_bytes(self) -> None:
        chip = clock()
        set_time(chip, DATE)

        chip.write(sharp.CONTROL, 0x0E)
        chip.write(sharp.CONTROL, 0x04)

        self.assertEqual([chip.store.read(at) for at in range(13)], [0] * 13)

    def test_a_command_the_chip_does_not_know_leaves_it_idle(self) -> None:
        chip = clock()

        chip.write(sharp.CONTROL, 0x0E)
        chip.write(sharp.CONTROL, 0x07)

        self.assertEqual(chip.read(sharp.DATA), 0x00)

    def test_the_marker_command_is_accepted_and_does_nothing(self) -> None:
        chip = clock()
        before = list(chip.store.bytes)

        chip.write(sharp.CONTROL, 0x0F)

        self.assertEqual(chip.store.bytes, before)

    def test_the_read_command_puts_the_chip_back_at_the_start(self) -> None:
        chip = clock()
        chip.read(sharp.DATA)
        chip.read(sharp.DATA)

        chip.write(sharp.CONTROL, 0x0D)

        self.assertEqual(chip.read(sharp.DATA), 0x0F)


class TimeTest(unittest.TestCase):
    def test_a_clock_read_later_has_moved_forward(self) -> None:
        held = store.Store(cleared=True)
        held.stamp = FROZEN
        moment = [FROZEN]
        chip = sharp.Clock(held, now=lambda: moment[0])
        set_time(chip, DATE)
        chip.write(sharp.CONTROL, 0x0D)
        chip.read(sharp.DATA)

        moment[0] = FROZEN + 65
        chip.write(sharp.CONTROL, 0x0D)
        chip.read(sharp.DATA)

        self.assertEqual((chip.store.read(2), chip.store.read(0)), (1, 5))

    def test_a_clock_read_at_the_same_moment_has_not(self) -> None:
        chip = clock()
        set_time(chip, DATE)
        chip.write(sharp.CONTROL, 0x0D)
        chip.read(sharp.DATA)
        before = list(chip.store.bytes[:13])

        chip.write(sharp.CONTROL, 0x0D)
        chip.read(sharp.DATA)

        self.assertEqual(chip.store.bytes[:13], before)

    def test_a_stamp_from_the_future_is_treated_as_no_time_having_passed(self) -> None:
        chip = clock()
        set_time(chip, DATE)
        chip.store.stamp = FROZEN + 10_000
        chip.write(sharp.CONTROL, 0x0D)
        before = list(chip.store.bytes[:13])

        chip.read(sharp.DATA)

        self.assertEqual(chip.store.bytes[:13], before)

    def test_a_stamp_that_wrapped_past_the_top_is_measured_the_long_way_round(self) -> None:
        chip = clock(at=10)
        set_time(chip, DATE)
        chip.store.stamp = 0xFFFFFFF0
        chip.write(sharp.CONTROL, 0x0D)

        chip.read(sharp.DATA)

        self.assertEqual(chip.store.stamp, 10)

    def test_the_reading_advances_the_stamp_to_now(self) -> None:
        chip = clock()

        chip.read(sharp.DATA)

        self.assertEqual(chip.store.stamp, FROZEN & 0xFFFFFFFF)


class ResetTest(unittest.TestCase):
    def test_a_reset_leaves_the_chip_ready_to_be_read(self) -> None:
        chip = clock()
        chip.write(sharp.CONTROL, 0x0E)

        chip.reset()

        self.assertEqual(chip.read(sharp.DATA), 0x0F)

    def test_a_reset_does_not_clear_what_the_battery_kept(self) -> None:
        chip = clock()
        set_time(chip, DATE)

        chip.reset()

        self.assertEqual(chip.store.read(2), DATE[2])

    def test_a_chip_prints_as_its_mode_and_its_place_in_the_sequence(self) -> None:
        self.assertIn("read", repr(clock()))


class DefaultClockTest(unittest.TestCase):
    def test_a_chip_given_no_clock_reads_the_one_the_machine_has(self) -> None:
        reading = sharp._now()

        self.assertGreater(reading, 1_600_000_000)


if __name__ == "__main__":
    unittest.main()
