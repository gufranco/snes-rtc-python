import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesrtc import calendar


class LeapTest(unittest.TestCase):
    def test_a_year_divisible_by_four_is_long(self) -> None:
        self.assertTrue(calendar.is_leap(2024))

    def test_a_century_is_not(self) -> None:
        self.assertFalse(calendar.is_leap(1900))

    def test_but_every_fourth_century_is(self) -> None:
        self.assertTrue(calendar.is_leap(2000))

    def test_an_ordinary_year_is_not(self) -> None:
        self.assertFalse(calendar.is_leap(2023))


class LengthTest(unittest.TestCase):
    def test_the_months_are_the_lengths_everyone_knows(self) -> None:
        self.assertEqual(
            [calendar.days_in(2023, month) for month in range(1, 13)],
            [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31],
        )

    def test_february_gains_a_day_in_a_long_year(self) -> None:
        self.assertEqual(calendar.days_in(2024, 2), 29)

    def test_a_month_number_past_the_end_wraps_rather_than_failing(self) -> None:
        self.assertEqual(calendar.days_in(2023, 13), 31)


class WeekdayTest(unittest.TestCase):
    def test_the_epoch_the_chip_counts_from_was_a_monday(self) -> None:
        self.assertEqual(calendar.weekday(1900, 1, 1), 1)

    def test_a_date_whose_weekday_is_a_matter_of_record(self) -> None:
        self.assertEqual(calendar.weekday(2008, 1, 1), 2)

    def test_the_day_after_saturday_is_sunday(self) -> None:
        self.assertEqual(calendar.weekday(2026, 8, 15), 6)
        self.assertEqual(calendar.weekday(2026, 8, 16), 0)

    def test_a_year_before_the_epoch_is_pulled_forward_to_it(self) -> None:
        self.assertEqual(calendar.weekday(1800, 1, 1), calendar.weekday(1900, 1, 1))

    def test_a_month_outside_the_year_is_pulled_inside_it(self) -> None:
        self.assertEqual(calendar.weekday(2008, 0, 1), calendar.weekday(2008, 1, 1))
        self.assertEqual(calendar.weekday(2008, 13, 1), calendar.weekday(2008, 12, 1))

    def test_a_day_outside_the_month_is_pulled_inside_it(self) -> None:
        self.assertEqual(calendar.weekday(2008, 1, 0), calendar.weekday(2008, 1, 1))
        self.assertEqual(calendar.weekday(2008, 1, 99), calendar.weekday(2008, 1, 31))

    def test_a_leap_day_is_counted_when_walking_past_it(self) -> None:
        self.assertNotEqual(calendar.weekday(2024, 3, 1), calendar.weekday(2023, 3, 1))


class AdvanceTest(unittest.TestCase):
    def test_a_moment_that_does_not_move_stays_put(self) -> None:
        started = calendar.Moment(2026, 8, 18, 12, 30, 15, 1)

        self.assertEqual(calendar.advance(started, 0), started)

    def test_seconds_roll_into_a_minute(self) -> None:
        moved = calendar.advance(calendar.Moment(2026, 8, 18, 12, 30, 50, 1), 15)

        self.assertEqual((moved.minute, moved.second), (31, 5))

    def test_minutes_roll_into_an_hour(self) -> None:
        moved = calendar.advance(calendar.Moment(2026, 8, 18, 12, 59, 50, 1), 15)

        self.assertEqual((moved.hour, moved.minute), (13, 0))

    def test_hours_roll_into_a_day_and_move_the_weekday_with_them(self) -> None:
        moved = calendar.advance(calendar.Moment(2026, 8, 18, 23, 59, 50, 1), 15)

        self.assertEqual((moved.day, moved.hour, moved.weekday), (19, 0, 2))

    def test_days_roll_into_a_month(self) -> None:
        moved = calendar.advance(calendar.Moment(2026, 8, 31, 23, 59, 59, 1), 1)

        self.assertEqual((moved.month, moved.day), (9, 1))

    def test_months_roll_into_a_year(self) -> None:
        moved = calendar.advance(calendar.Moment(2026, 12, 31, 23, 59, 59, 4), 1)

        self.assertEqual((moved.year, moved.month, moved.day), (2027, 1, 1))

    def test_february_holds_a_twenty_ninth_in_a_long_year(self) -> None:
        moved = calendar.advance(calendar.Moment(2024, 2, 28, 23, 59, 59, 3), 1)

        self.assertEqual((moved.month, moved.day), (2, 29))

    def test_and_does_not_in_an_ordinary_one(self) -> None:
        moved = calendar.advance(calendar.Moment(2023, 2, 28, 23, 59, 59, 2), 1)

        self.assertEqual((moved.month, moved.day), (3, 1))

    def test_the_weekday_cycles_through_seven_and_returns(self) -> None:
        started = calendar.Moment(2026, 8, 18, 0, 0, 0, 2)

        moved = calendar.advance(started, 7 * 86400)

        self.assertEqual(moved.weekday, started.weekday)

    def test_a_long_jump_lands_where_the_calendar_says(self) -> None:
        moved = calendar.advance(calendar.Moment(2000, 1, 1, 0, 0, 0, 6), 366 * 86400)

        self.assertEqual((moved.year, moved.month, moved.day), (2001, 1, 1))

    def test_two_moments_holding_the_same_reading_are_interchangeable(self) -> None:
        first = calendar.Moment(2026, 8, 18, 12, 0, 0, 2)
        second = calendar.Moment(2026, 8, 18, 12, 0, 0, 2)

        self.assertEqual({first, second}, {first})

    def test_a_moment_reports_itself_as_something_readable(self) -> None:
        self.assertIn("2026", repr(calendar.Moment(2026, 8, 18, 12, 0, 0, 2)))


if __name__ == "__main__":
    unittest.main()
