import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.driving import (
    DAY,
    DIGITS,
    ENABLE,
    FACTS,
    FROZEN,
    S1,
    S10,
    W,
    a_clock,
    read_back,
    written,
)

EXAMPLE_YEAR = 1993

MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def a_day(text: str) -> tuple[int, int, int]:
    if "-" in text:
        year, month, day = (int(part) for part in text.split("-"))
        return year, month, day
    month_name, day_text = text.split()
    return EXAMPLE_YEAR, MONTH_NAMES.index(month_name) + 1, int(day_text)


def a_second_before_midnight(year: int, month: int, day: int) -> tuple[int, ...]:
    short = year % 100
    return (9, 5, 9, 5, 3, 2, day % 10, day // 10, month % 10, month // 10, short % 10, short // 10)


def a_second_after(date: tuple[int, int, int]) -> tuple[int, int, int]:
    hand = [FROZEN]
    chip = a_clock(hand)
    written(chip, S1, *a_second_before_midnight(*date))
    hand[0] += 1
    chip.write(ENABLE, 0x00)
    moment = chip.moment()
    return moment.year, moment.month, moment.day


def the_top_held(row: dict[str, object]) -> int:
    chip = a_clock([FROZEN])
    address = int(str(row["address"]))
    top = row["countRange"]
    assert isinstance(top, list)
    written(chip, address, top[1])
    return int(chip.digit(address))


def weekdays_counted(days: int) -> list[int]:
    hand = [FROZEN]
    chip = a_clock(hand)
    written(chip, S1, *DIGITS[:12], 0)
    counted = []
    for _ in range(days):
        hand[0] += DAY
        chip.write(ENABLE, 0x00)
        counted.append(chip.digit(W))
    return counted


class PrintedBehaviourTest(unittest.TestCase):
    def test_a_digit_carries_into_the_next_one_at_ten(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, 9, 0, *DIGITS[2:])
        hand[0] += 1

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        carried = (chip.digit(S1), chip.digit(S10))
        self.assertEqual("bcd" if carried == (0, 1) else "binary", FACTS["encoding"]["value"])

    def test_an_impossible_value_the_manual_warns_against_can_still_be_set(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, 0x0C)

        # Act
        answered = read_back(chip, S1)

        # Assert
        self.assertEqual(answered == 0x0C, FACTS["outOfRangeValuesNotSpecified"]["value"])

    def test_each_printed_impossible_date_corrects_to_the_printed_one(self) -> None:
        # Arrange
        examples = FACTS["impossibleDateCorrection"]["examples"]

        # Act
        corrected = [a_second_after(a_day(example["set"])) for example in examples]

        # Assert
        self.assertEqual(corrected, [a_day(example["corrects"]) for example in examples])

    def test_february_gains_a_day_in_a_leap_year_and_only_then(self) -> None:
        # Arrange
        eves = ((2024, 2, 28), (2023, 2, 28))

        # Act
        found = [a_second_after(eve) for eve in eves]

        # Assert
        self.assertEqual(
            found == [(2024, 2, 29), (2023, 3, 1)], FACTS["leapYearCompensation"]["value"]
        )

    def test_every_counted_register_holds_the_top_of_its_printed_range(self) -> None:
        # Arrange
        counted = [row for row in FACTS["registerTable"]["rows"] if row["countRange"]]

        # Act
        held = [the_top_held(row) for row in counted]

        # Assert
        self.assertEqual(held, [row["countRange"][1] for row in counted])

    def test_the_weekday_counts_up_to_six_and_back_to_zero(self) -> None:
        # Arrange
        low, high = FACTS["weekdayCountsZeroToSix"]["value"]

        # Act
        counted = weekdays_counted(high - low + 1)

        # Assert
        self.assertEqual(counted, [*range(low + 1, high + 1), low])


if __name__ == "__main__":
    unittest.main()
