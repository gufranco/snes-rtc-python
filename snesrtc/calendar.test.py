import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.driving import FROZEN, RECORDED, SHARP_CONTROL, SHARP_DATA
from snesrtc import Chip, Store

CONTROL = 0x2801

YEAR_BASE = 1000

DAY = 86_400


def digits(year: int, month: int, day: int, hour: int, minute: int, second: int) -> list[int]:
    held = year - YEAR_BASE
    return [
        second % 10,
        second // 10,
        minute % 10,
        minute // 10,
        hour % 10,
        hour // 10,
        day % 10,
        day // 10,
        month,
        held % 10,
        (held // 10) % 10,
        held // 100,
    ]


def a_clock_reading(*when: int, weekday: int, hand: list[int]) -> Any:
    held = Store(cleared=True, held=[*digits(*when), weekday])
    return Chip("s-rtc", held, now=lambda: hand[0])


def advanced(*when: int, weekday: int, seconds: int) -> str:
    hand = [0]
    chip = a_clock_reading(*when, weekday=weekday, hand=hand)
    hand[0] = seconds
    chip.update()
    return repr(chip.read_moment())


def weekday_written(year: int, month: int, day: int) -> int:
    chip = Chip("s-rtc", Store(cleared=True), now=lambda: 0)
    chip.write(CONTROL, 0x0E)
    chip.write(CONTROL, 0x00)
    for digit in digits(year, month, day, 0, 0, 0):
        chip.write(CONTROL, digit)
    return int(chip.store.read(12))


def read_back_after(stored: list[int], seconds: int) -> list[int]:
    held = Store(cleared=True, held=stored)
    held.stamp = FROZEN
    chip = Chip("s-rtc", held, now=lambda: FROZEN + seconds)
    chip.write(SHARP_CONTROL, 0x0D)
    return [chip.read(SHARP_DATA) for _ in range(15)]


def month_lengths(year: int) -> list[int]:
    return [
        32 - int(advanced(year, month, 1, 0, 0, 0, weekday=0, seconds=31 * DAY)[9:11])
        for month in range(1, 13)
    ]


class LeapTest(unittest.TestCase):
    def test_a_year_divisible_by_four_is_long(self) -> None:
        # Arrange
        last_of_february = (2024, 2, 28, 23, 59, 59)

        # Act
        moved = advanced(*last_of_february, weekday=3, seconds=1)

        # Assert
        self.assertEqual(moved, "<2024-02-29 00:00:00 weekday=4>")

    def test_a_century_is_not(self) -> None:
        # Arrange
        last_of_february = (1900, 2, 28, 23, 59, 59)

        # Act
        moved = advanced(*last_of_february, weekday=3, seconds=1)

        # Assert
        self.assertEqual(moved, "<1900-03-01 00:00:00 weekday=4>")

    def test_but_every_fourth_century_is(self) -> None:
        # Arrange
        last_of_february = (2000, 2, 28, 23, 59, 59)

        # Act
        moved = advanced(*last_of_february, weekday=1, seconds=1)

        # Assert
        self.assertEqual(moved, "<2000-02-29 00:00:00 weekday=2>")

    def test_an_ordinary_year_is_not(self) -> None:
        # Arrange
        last_of_february = (2023, 2, 28, 23, 59, 59)

        # Act
        moved = advanced(*last_of_february, weekday=2, seconds=1)

        # Assert
        self.assertEqual(moved, "<2023-03-01 00:00:00 weekday=3>")


class LengthTest(unittest.TestCase):
    def test_the_months_are_the_lengths_everyone_knows(self) -> None:
        # Arrange
        year = 2023

        # Act
        lengths = month_lengths(year)

        # Assert
        self.assertEqual(lengths, [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])

    def test_february_gains_a_day_in_a_long_year(self) -> None:
        # Arrange
        year = 2024

        # Act
        lengths = month_lengths(year)

        # Assert
        self.assertEqual(lengths[1], 29)

    def test_a_month_number_past_the_end_wraps_rather_than_failing(self) -> None:
        # Arrange
        thirtieth_of_a_thirteenth_month = (2023, 13, 30, 23, 59, 59)

        # Act
        moved = advanced(*thirtieth_of_a_thirteenth_month, weekday=0, seconds=1)

        # Assert
        self.assertEqual(moved, "<2023-13-31 00:00:00 weekday=1>")


class HeldMonthTest(unittest.TestCase):
    def test_a_month_above_twelve_held_by_the_battery_counts_as_the_reference_does(
        self,
    ) -> None:
        # Arrange
        cases = RECORDED["monthAboveTwelve"]["value"]

        # Act
        found = [read_back_after(one["stored"], one["secondsLater"]) for one in cases]

        # Assert
        self.assertEqual(found, [one["readBack"] for one in cases])


class WeekdayTest(unittest.TestCase):
    def test_the_epoch_the_chip_counts_from_was_a_monday(self) -> None:
        # Arrange
        epoch = (1900, 1, 1)

        # Act
        found = weekday_written(*epoch)

        # Assert
        self.assertEqual(found, 1)

    def test_a_date_whose_weekday_is_a_matter_of_record(self) -> None:
        # Arrange
        new_year = (2008, 1, 1)

        # Act
        found = weekday_written(*new_year)

        # Assert
        self.assertEqual(found, 2)

    def test_the_day_after_saturday_is_sunday(self) -> None:
        # Arrange
        saturday, sunday = (2026, 8, 15), (2026, 8, 16)

        # Act
        found = (weekday_written(*saturday), weekday_written(*sunday))

        # Assert
        self.assertEqual(found, (6, 0))

    def test_a_year_before_the_epoch_is_pulled_forward_to_it(self) -> None:
        # Arrange
        before_the_epoch = (1800, 1, 1)

        # Act
        found = weekday_written(*before_the_epoch)

        # Assert
        self.assertEqual(found, 1)

    def test_a_month_outside_the_year_is_pulled_inside_it(self) -> None:
        # Arrange
        month_zero = (2008, 0, 1)

        # Act
        found = weekday_written(*month_zero)

        # Assert
        self.assertEqual(found, 2)

    def test_a_day_outside_the_month_is_pulled_inside_it(self) -> None:
        # Arrange
        too_early, too_late = (2008, 1, 0), (2008, 1, 99)

        # Act
        found = (weekday_written(*too_early), weekday_written(*too_late))

        # Assert
        self.assertEqual(found, (2, 4))

    def test_a_leap_day_is_counted_when_walking_past_it(self) -> None:
        # Arrange
        after_a_leap_day, after_none = (2024, 3, 1), (2023, 3, 1)

        # Act
        found = (weekday_written(*after_a_leap_day), weekday_written(*after_none))

        # Assert
        self.assertEqual(found, (5, 3))


class AdvanceTest(unittest.TestCase):
    def test_a_moment_that_does_not_move_stays_put(self) -> None:
        # Arrange
        started = (2026, 8, 18, 12, 30, 15)

        # Act
        moved = advanced(*started, weekday=2, seconds=0)

        # Assert
        self.assertEqual(moved, "<2026-08-18 12:30:15 weekday=2>")

    def test_seconds_roll_into_a_minute(self) -> None:
        # Arrange
        started = (2026, 8, 18, 12, 30, 50)

        # Act
        moved = advanced(*started, weekday=2, seconds=15)

        # Assert
        self.assertEqual(moved, "<2026-08-18 12:31:05 weekday=2>")

    def test_minutes_roll_into_an_hour(self) -> None:
        # Arrange
        started = (2026, 8, 18, 12, 59, 50)

        # Act
        moved = advanced(*started, weekday=2, seconds=15)

        # Assert
        self.assertEqual(moved, "<2026-08-18 13:00:05 weekday=2>")

    def test_hours_roll_into_a_day_and_move_the_weekday_with_them(self) -> None:
        # Arrange
        started = (2026, 8, 18, 23, 59, 50)

        # Act
        moved = advanced(*started, weekday=2, seconds=15)

        # Assert
        self.assertEqual(moved, "<2026-08-19 00:00:05 weekday=3>")

    def test_days_roll_into_a_month(self) -> None:
        # Arrange
        started = (2026, 8, 31, 23, 59, 59)

        # Act
        moved = advanced(*started, weekday=1, seconds=1)

        # Assert
        self.assertEqual(moved, "<2026-09-01 00:00:00 weekday=2>")

    def test_months_roll_into_a_year(self) -> None:
        # Arrange
        started = (2026, 12, 31, 23, 59, 59)

        # Act
        moved = advanced(*started, weekday=4, seconds=1)

        # Assert
        self.assertEqual(moved, "<2027-01-01 00:00:00 weekday=5>")

    def test_the_weekday_cycles_through_seven_and_returns(self) -> None:
        # Arrange
        started = (2026, 8, 18, 0, 0, 0)

        # Act
        moved = advanced(*started, weekday=2, seconds=7 * DAY)

        # Assert
        self.assertEqual(moved, "<2026-08-25 00:00:00 weekday=2>")

    def test_a_long_jump_lands_where_the_calendar_says(self) -> None:
        # Arrange
        started = (2000, 1, 1, 0, 0, 0)

        # Act
        moved = advanced(*started, weekday=6, seconds=366 * DAY)

        # Assert
        self.assertEqual(moved, "<2001-01-01 00:00:00 weekday=1>")


class MomentTest(unittest.TestCase):
    def test_two_moments_holding_the_same_reading_are_interchangeable(self) -> None:
        # Arrange
        noon = (2026, 8, 18, 12, 0, 0)
        first = a_clock_reading(*noon, weekday=2, hand=[0]).read_moment()

        # Act
        second = a_clock_reading(*noon, weekday=2, hand=[0]).read_moment()

        # Assert
        self.assertEqual({first, second}, {first})

    def test_and_a_different_reading_is_a_different_moment(self) -> None:
        # Arrange
        first = a_clock_reading(2026, 8, 18, 12, 0, 0, weekday=2, hand=[0]).read_moment()

        # Act
        second = a_clock_reading(2026, 8, 18, 12, 0, 1, weekday=2, hand=[0]).read_moment()

        # Assert
        self.assertNotEqual(first, second)

    def test_a_moment_reports_itself_as_something_readable(self) -> None:
        # Arrange
        chip = a_clock_reading(2026, 8, 18, 12, 0, 0, weekday=2, hand=[0])

        # Act
        shown = repr(chip.read_moment())

        # Assert
        self.assertEqual(shown, "<2026-08-18 12:00:00 weekday=2>")


if __name__ == "__main__":
    unittest.main()
