import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance import driving
from snesrtc import epson


class RecordTest(unittest.TestCase):
    def test_the_epson_facts_come_from_the_documented_part(self) -> None:
        # Arrange
        part = driving.PARTS["Epson RTC-4513"]

        # Act
        facts = part["facts"]

        # Assert
        self.assertIs(driving.FACTS, facts)

    def test_the_register_table_has_a_row_per_register(self) -> None:
        # Arrange
        rows = driving.ROWS

        # Act
        addresses = [row["address"] for row in rows]

        # Assert
        self.assertEqual(addresses, list(range(epson.REGISTERS)))


class ClockTest(unittest.TestCase):
    def test_a_clock_reads_the_hand_it_was_given(self) -> None:
        # Arrange
        hand = [driving.FROZEN]

        # Act
        chip = driving.a_clock(hand)

        # Assert
        self.assertEqual((chip.now(), chip.store.stamp), (driving.FROZEN, driving.FROZEN))

    def test_and_starts_dated_on_a_twenty_four_hour_dial(self) -> None:
        # Arrange
        hand = [driving.FROZEN]

        # Act
        chip = driving.a_clock(hand)

        # Assert
        self.assertEqual((chip.dated(), chip.twenty_four_hour()), (True, True))


class SessionTest(unittest.TestCase):
    def test_opening_leaves_the_chip_at_the_register_named(self) -> None:
        # Arrange
        chip = driving.a_clock([driving.FROZEN])

        # Act
        driving.opened(chip, epson.READ_MODE, epson.MI1)

        # Assert
        self.assertEqual((chip.state, chip.index), (epson.READING, epson.MI1))

    def test_writing_lands_each_nibble_at_the_next_register(self) -> None:
        # Arrange
        chip = driving.a_clock([driving.FROZEN])

        # Act
        driving.written(chip, epson.MI1, 1, 2)

        # Assert
        self.assertEqual((chip.store.read(epson.MI1), chip.store.read(epson.MI10)), (1, 2))

    def test_reading_back_answers_what_was_written(self) -> None:
        # Arrange
        chip = driving.a_clock([driving.FROZEN])
        driving.written(chip, epson.MI1, 7)

        # Act
        answered = driving.read_back(chip, epson.MI1)

        # Assert
        self.assertEqual(answered, 7)


class BitTest(unittest.TestCase):
    def test_a_bit_spelled_as_register_and_position_is_found(self) -> None:
        # Arrange
        spelled = "H10.D2"

        # Act
        found = driving.located(spelled)

        # Assert
        self.assertEqual(found, (epson.H10, 0x4))

    def test_a_bit_named_in_the_register_table_is_found(self) -> None:
        # Arrange
        name = "h20"

        # Act
        found = driving.named_bit(name)

        # Assert
        self.assertEqual(found, (epson.H10, 0x2))


if __name__ == "__main__":
    unittest.main()
