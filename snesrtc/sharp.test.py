import sys
import time
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesrtc import Chip, Store

FROZEN = 1_000_000_000

DATA = 0x2800

CONTROL = 0x2801

MARKER = 0x0F

DATE = (0, 0, 0, 3, 2, 1, 8, 1, 8, 6, 9, 9)

SUNDAY = 0


def clock(at: int = FROZEN, **options: Any) -> Any:
    held = Store(cleared=True)
    held.stamp = at
    return Chip("s-rtc", held, now=lambda: at, **options)


def set_time(chip: Any, digits: tuple[int, ...]) -> None:
    chip.write(CONTROL, 0x0E)
    chip.write(CONTROL, 0x00)
    for digit in digits:
        chip.write(CONTROL, digit)


def read_from_the_start(chip: Any, count: int) -> list[int]:
    chip.write(CONTROL, 0x0D)
    chip.read(DATA)
    return [chip.read(DATA) for _ in range(count)]


class ReadTest(unittest.TestCase):
    def test_a_read_before_anything_answers_the_ready_marker(self) -> None:
        # Arrange
        chip = clock()

        # Act
        answered = chip.read(DATA)

        # Assert
        self.assertEqual(answered, MARKER)

    def test_the_thirteen_bytes_then_come_out_in_order(self) -> None:
        # Arrange
        chip = clock()
        set_time(chip, DATE)

        # Act
        answered = read_from_the_start(chip, 13)

        # Assert
        self.assertEqual(answered, [*DATE, SUNDAY])

    def test_and_the_marker_comes_round_again_at_the_end(self) -> None:
        # Arrange
        chip = clock()
        chip.read(DATA)
        for _ in range(13):
            chip.read(DATA)

        # Act
        answered = chip.read(DATA)

        # Assert
        self.assertEqual(answered, MARKER)

    def test_the_sequence_then_starts_over(self) -> None:
        # Arrange
        chip = clock()
        for _ in range(15):
            chip.read(DATA)

        # Act
        answered = chip.read(DATA)

        # Assert
        self.assertEqual(answered, MARKER)

    def test_a_read_while_not_in_reading_mode_answers_nothing(self) -> None:
        # Arrange
        chip = clock()
        chip.write(CONTROL, 0x0E)

        # Act
        answered = chip.read(DATA)

        # Assert
        self.assertEqual(answered, 0x00)

    def test_a_read_of_an_address_the_chip_does_not_answer_gives_the_open_bus(self) -> None:
        # Arrange
        chip = clock(open_bus=0x42)

        # Act
        answered = chip.read(0x2802)

        # Assert
        self.assertEqual(answered, 0x42)


class WriteTest(unittest.TestCase):
    def test_a_written_time_reads_back_as_it_was_written(self) -> None:
        # Arrange
        chip = clock()
        set_time(chip, DATE)

        # Act
        answered = read_from_the_start(chip, 12)

        # Assert
        self.assertEqual(answered, list(DATE))

    def test_the_weekday_is_worked_out_rather_than_written(self) -> None:
        # Arrange
        chip = clock()
        set_time(chip, DATE)

        # Act
        answered = read_from_the_start(chip, 13)

        # Assert
        self.assertEqual(answered[12], SUNDAY)

    def test_only_the_low_four_bits_of_a_written_byte_are_kept(self) -> None:
        # Arrange
        chip = clock()
        chip.write(CONTROL, 0x0E)
        chip.write(CONTROL, 0x00)

        # Act
        chip.write(CONTROL, 0xF7)

        # Assert
        self.assertEqual(chip.store.read(0), 0x07)

    def test_writing_past_the_twelfth_byte_is_ignored(self) -> None:
        # Arrange
        chip = clock()
        set_time(chip, DATE)

        # Act
        chip.write(CONTROL, 0x09)

        # Assert
        self.assertEqual(chip.store.read(0), DATE[0])

    def test_a_write_outside_writing_mode_changes_nothing(self) -> None:
        # Arrange
        chip = clock()
        before = list(chip.store.bytes)

        # Act
        chip.write(CONTROL, 0x07)

        # Assert
        self.assertEqual(chip.store.bytes, before)

    def test_a_write_to_an_address_the_chip_does_not_answer_changes_nothing(self) -> None:
        # Arrange
        chip = clock()
        before = list(chip.store.bytes)

        # Act
        chip.write(DATA, 0x07)

        # Assert
        self.assertEqual(chip.store.bytes, before)


class CommandTest(unittest.TestCase):
    def test_the_reset_command_clears_the_thirteen_time_bytes(self) -> None:
        # Arrange
        chip = clock()
        set_time(chip, DATE)
        chip.write(CONTROL, 0x0E)

        # Act
        chip.write(CONTROL, 0x04)

        # Assert
        self.assertEqual([chip.store.read(at) for at in range(13)], [0] * 13)

    def test_a_command_the_chip_does_not_know_leaves_it_idle(self) -> None:
        # Arrange
        chip = clock()
        chip.write(CONTROL, 0x0E)
        chip.write(CONTROL, 0x07)

        # Act
        answered = chip.read(DATA)

        # Assert
        self.assertEqual(answered, 0x00)

    def test_the_marker_command_is_accepted_and_does_nothing(self) -> None:
        # Arrange
        chip = clock()
        before = list(chip.store.bytes)

        # Act
        chip.write(CONTROL, 0x0F)

        # Assert
        self.assertEqual(chip.store.bytes, before)

    def test_the_read_command_puts_the_chip_back_at_the_start(self) -> None:
        # Arrange
        chip = clock()
        chip.read(DATA)
        chip.read(DATA)
        chip.write(CONTROL, 0x0D)

        # Act
        answered = chip.read(DATA)

        # Assert
        self.assertEqual(answered, MARKER)


class TimeTest(unittest.TestCase):
    def test_a_clock_read_later_has_moved_forward(self) -> None:
        # Arrange
        held = Store(cleared=True)
        held.stamp = FROZEN
        moment = [FROZEN]
        chip = Chip("s-rtc", held, now=lambda: moment[0])
        set_time(chip, DATE)
        read_from_the_start(chip, 0)
        moment[0] = FROZEN + 65

        # Act
        read_from_the_start(chip, 0)

        # Assert
        self.assertEqual((chip.store.read(2), chip.store.read(0)), (1, 5))

    def test_a_clock_read_at_the_same_moment_has_not(self) -> None:
        # Arrange
        chip = clock()
        set_time(chip, DATE)
        read_from_the_start(chip, 0)
        before = list(chip.store.bytes[:13])

        # Act
        read_from_the_start(chip, 0)

        # Assert
        self.assertEqual(chip.store.bytes[:13], before)

    def test_a_stamp_from_the_future_is_treated_as_no_time_having_passed(self) -> None:
        # Arrange
        chip = clock()
        set_time(chip, DATE)
        chip.store.stamp = FROZEN + 10_000
        chip.write(CONTROL, 0x0D)
        before = list(chip.store.bytes[:13])

        # Act
        chip.read(DATA)

        # Assert
        self.assertEqual(chip.store.bytes[:13], before)

    def test_a_stamp_that_wrapped_past_the_top_is_measured_the_long_way_round(self) -> None:
        # Arrange
        chip = clock(at=10)
        set_time(chip, DATE)
        chip.store.stamp = 0xFFFFFFF0
        chip.write(CONTROL, 0x0D)

        # Act
        chip.read(DATA)

        # Assert
        self.assertEqual((chip.store.stamp, chip.store.read(0), chip.store.read(1)), (10, 6, 2))

    def test_the_reading_advances_the_stamp_to_now(self) -> None:
        # Arrange
        chip = clock()

        # Act
        chip.read(DATA)

        # Assert
        self.assertEqual(chip.store.stamp, FROZEN & 0xFFFFFFFF)


class ResetTest(unittest.TestCase):
    def test_a_reset_leaves_the_chip_ready_to_be_read(self) -> None:
        # Arrange
        chip = clock()
        chip.write(CONTROL, 0x0E)
        chip.reset()

        # Act
        answered = chip.read(DATA)

        # Assert
        self.assertEqual(answered, MARKER)

    def test_a_reset_does_not_clear_what_the_battery_kept(self) -> None:
        # Arrange
        chip = clock()
        set_time(chip, DATE)

        # Act
        chip.reset()

        # Assert
        self.assertEqual(chip.store.read(2), DATE[2])

    def test_a_chip_prints_as_its_mode_and_its_place_in_the_sequence(self) -> None:
        # Arrange
        chip = clock()

        # Act
        shown = repr(chip)

        # Assert
        self.assertIn("read", shown)


class DefaultClockTest(unittest.TestCase):
    def test_a_chip_given_no_clock_reads_the_one_the_machine_has(self) -> None:
        # Arrange
        chip = Chip("s-rtc", Store(cleared=True))
        before = int(time.time())

        # Act
        reading = chip.now()

        # Assert
        self.assertGreaterEqual(reading, before)
        self.assertLessEqual(reading, int(time.time()))


if __name__ == "__main__":
    unittest.main()
