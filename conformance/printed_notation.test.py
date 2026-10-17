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
    located,
    named_bit,
    read_back,
    written,
)
from snesrtc import epson


def tens_of_hours(control_f: int) -> set[int]:
    chip = a_clock([FROZEN], control_f=control_f)
    seen = set()
    for hour in range(24):
        chip.store_hour(hour)
        seen.add(chip.digit(epson.H10))
    return seen


def hour_read(control_f: int, tens: int) -> int:
    chip = a_clock([FROZEN], control_f=control_f)
    written(chip, epson.H1, 3, tens)
    return chip.hour()


class PrintedBehaviourTest(unittest.TestCase):
    def test_the_tens_of_hours_counts_to_one_or_to_two_by_notation(self) -> None:
        # Arrange
        row = next(one for one in FACTS["registerTable"]["rows"] if "countRangeQuote" in one)
        low, _, tops = row["countRangeQuote"].partition("~")
        twelve, twenty_four = (int(top) for top in tops.split(","))

        # Act
        seen = (tens_of_hours(0), tens_of_hours(epson.HOURS_24))

        # Assert
        self.assertEqual(
            seen,
            (set(range(int(low), twelve + 1)), set(range(row["countRange"][0], twenty_four + 1))),
        )

    def test_the_afternoon_bit_is_one_for_pm_and_zero_for_am(self) -> None:
        # Arrange
        _, afternoon = located(FACTS["pmAmBit"]["bit"])

        # Act
        read = (hour_read(0, afternoon), hour_read(0, 0))

        # Assert
        self.assertEqual(read, (15, 3))

    def test_the_notation_bit_chooses_twenty_four_hours_when_set(self) -> None:
        # Arrange
        notation = FACTS["controlRegisterF"]["bits"]["twentyFourTwelve"]["mask"]

        # Act
        read = (hour_read(notation, epson.PM), hour_read(0, epson.PM))

        # Assert
        self.assertEqual(read, (3, 15))

    def test_the_twenty_bit_cannot_be_written_in_twelve_hour_notation(self) -> None:
        # Arrange
        fact = FACTS["twelveHourNotation"]
        address, bit = named_bit(fact["bit"])
        chip = a_clock([FROZEN], control_f=0)
        written(chip, address, bit | 0x1)

        # Act
        answered = read_back(chip, address)

        # Assert
        self.assertEqual((int(bool(answered & bit)), answered & 0x1), (fact["reads"], 0x1))

    def test_and_the_clock_never_increments_it(self) -> None:
        # Arrange
        fact = FACTS["twelveHourNotation"]
        address, bit = named_bit(fact["bit"])
        hand = [FROZEN]
        chip = a_clock(hand, control_f=0)
        written(chip, epson.S1, *DIGITS)

        # Act
        seen = []
        for _ in range(24):
            hand[0] += HOUR
            chip.write(epson.ENABLE, 0x00)
            seen.append(int(bool(chip.store.read(address) & bit)))

        # Assert
        self.assertEqual(seen, [fact["reads"]] * 24)

    def test_a_write_to_the_afternoon_bit_is_disregarded_in_twenty_four_hour_notation(
        self,
    ) -> None:
        # Arrange
        fact = FACTS["twentyFourHourNotation"]
        address, bit = named_bit(fact["bit"])
        chip = a_clock([FROZEN])

        # Act
        written(chip, address, bit | 0x1)

        # Assert
        self.assertEqual(
            (int(bool(chip.store.read(address) & bit)), chip.digit(address)), (fact["reads"], 1)
        )

    def test_and_the_afternoon_bit_reads_zero_whatever_the_register_holds(self) -> None:
        # Arrange
        fact = FACTS["twentyFourHourNotation"]
        address, bit = named_bit(fact["bit"])
        chip = a_clock([FROZEN])
        chip.store.write(address, bit | 0x1)

        # Act
        answered = read_back(chip, address)

        # Assert
        self.assertEqual((int(bool(answered & bit)), answered & 0x1), (fact["reads"], 0x1))


if __name__ == "__main__":
    unittest.main()
