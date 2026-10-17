import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.driving import (
    DIGITS,
    FACTS,
    FROZEN,
    HOUR,
    a_clock,
    opened,
    written,
)
from snesrtc import epson


def hours_moved(*control_f: int) -> int:
    hand = [FROZEN]
    chip = a_clock(hand)
    written(chip, epson.S1, *DIGITS)
    for value in control_f:
        written(chip, epson.CF, value)
    hand[0] += HOUR
    chip.write(epson.ENABLE, 0x00)
    return chip.digit(epson.H1) - DIGITS[epson.H1]


def adjusted(seconds: int, mask: int) -> tuple[int, int, int]:
    chip = a_clock([FROZEN])
    written(chip, epson.S1, seconds % 10, seconds // 10, *DIGITS[2:])
    written(chip, epson.CD, epson.CAL_HW | mask)
    chip.write(epson.ENABLE, 0x00)
    second = chip.digit(epson.S1) + chip.digit(epson.S10) * 10
    return second, chip.digit(epson.MI1), chip.store.read(epson.CD) & mask


class PrintedBehaviourTest(unittest.TestCase):
    def test_releasing_hold_hands_back_one_second_however_long_it_lasted(self) -> None:
        # Arrange
        hold = FACTS["controlRegisterD"]["bits"]["hold"]["mask"]
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, epson.S1, *DIGITS)
        written(chip, epson.CD, epson.CAL_HW | hold)
        hand[0] += 300

        # Act
        written(chip, epson.CD, epson.CAL_HW)

        # Assert
        self.assertEqual(
            (chip.digit(epson.S1), chip.digit(epson.MI1)),
            (DIGITS[epson.S1] + 1, DIGITS[epson.MI1]),
        )

    def test_the_thirty_second_adjust_rounds_to_the_nearer_minute_and_clears(self) -> None:
        # Arrange
        mask = FACTS["controlRegisterD"]["bits"]["thirtySecondAdjust"]["mask"]

        # Act
        rounded = (adjusted(29, mask), adjusted(30, mask))

        # Assert
        self.assertEqual(rounded, ((0, DIGITS[epson.MI1], 0), (0, DIGITS[epson.MI1] + 1, 0)))

    def test_reset_zeroes_the_seconds_and_forces_the_test_bit_down(self) -> None:
        # Arrange
        reset = FACTS["controlRegisterF"]["bits"]["reset"]["mask"]
        chip = a_clock([FROZEN], control_f=epson.HOURS_24 | epson.TEST)
        written(chip, epson.S1, 5, 2, *DIGITS[2:])
        opened(chip, epson.WRITE_MODE, epson.CF)

        # Act
        chip.write(epson.DATA, epson.HOURS_24 | epson.TEST | reset)

        # Assert
        self.assertEqual(
            (chip.digit(epson.S1), chip.digit(epson.S10), chip.store.read(epson.CF) & epson.TEST),
            (0, 0, 0),
        )

    def test_reset_stops_the_clock_until_it_is_cleared(self) -> None:
        # Arrange
        reset = FACTS["controlRegisterF"]["bits"]["reset"]["mask"]

        # Act
        moved = (
            hours_moved(epson.HOURS_24 | reset),
            hours_moved(epson.HOURS_24 | reset, epson.HOURS_24),
        )

        # Assert
        self.assertEqual(moved, (0, 1))

    def test_stop_stops_the_clock_until_it_is_cleared(self) -> None:
        # Arrange
        stop = FACTS["controlRegisterF"]["bits"]["stop"]["mask"]

        # Act
        moved = (
            hours_moved(epson.HOURS_24 | stop),
            hours_moved(epson.HOURS_24 | stop, epson.HOURS_24),
        )

        # Assert
        self.assertEqual(moved, (0, 1))

    def test_the_test_bit_is_cleared_when_ce_falls(self) -> None:
        # Arrange
        test = FACTS["controlRegisterF"]["bits"]["test"]["mask"]
        chip = a_clock([FROZEN])
        written(chip, epson.CF, epson.HOURS_24 | test)

        # Act
        chip.write(epson.ENABLE, 0x00)

        # Assert
        self.assertEqual(chip.store.read(epson.CF) & test, 0)


if __name__ == "__main__":
    unittest.main()
