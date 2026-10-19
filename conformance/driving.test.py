import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance import driving

README_REGISTERS = (
    "S1",
    "S10",
    "MI1",
    "MI10",
    "H1",
    "H10",
    "D1",
    "D10",
    "MO1",
    "MO10",
    "Y1",
    "Y10",
    "W",
    "CD",
    "CE",
    "CF",
)


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
        self.assertEqual(addresses, list(range(16)))


class VocabularyTest(unittest.TestCase):
    def test_each_register_is_found_at_the_index_the_readme_table_gives(self) -> None:
        # Arrange
        names = README_REGISTERS

        # Act
        found = [driving.register(name) for name in names]

        # Assert
        self.assertEqual(found, list(range(16)))

    def test_the_named_registers_match_the_readme_table(self) -> None:
        # Arrange
        expected = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)

        # Act
        found = (
            driving.S1,
            driving.S10,
            driving.MI1,
            driving.MI10,
            driving.H1,
            driving.H10,
            driving.D1,
            driving.D10,
            driving.MO1,
            driving.MO10,
            driving.Y1,
            driving.Y10,
            driving.W,
            driving.CD,
            driving.CE,
            driving.CF,
        )

        # Assert
        self.assertEqual(found, expected)

    def test_the_control_bits_carry_the_masks_the_readme_table_places(self) -> None:
        # Arrange
        expected = (0x1, 0x2, 0x4, 0x8, 0x1, 0x2, 0x1, 0x2, 0x4, 0x8)

        # Act
        found = (
            driving.HOLD,
            driving.CAL_HW,
            driving.IRQ_F,
            driving.ADJUST,
            driving.MASK,
            driving.INT_STND,
            driving.RESET,
            driving.STOP,
            driving.HOURS_24,
            driving.TEST,
        )

        # Assert
        self.assertEqual(found, expected)

    def test_the_flag_bits_sit_where_the_readme_table_places_them(self) -> None:
        # Arrange
        expected = (0x4, 0x2, 0x8, 0x8, (3, 5, 7, 9, 12))

        # Act
        found = (driving.PM, driving.H20, driving.OSC_FLAG, driving.READ_FLAG, driving.READ_FLAG_AT)

        # Assert
        self.assertEqual(found, expected)

    def test_the_bus_and_the_mode_codes_are_the_ones_the_readme_gives(self) -> None:
        # Arrange
        expected = (0x4840, 0x4841, 0x4842, 0x03, 0x0C, 0x2800, 0x2801)

        # Act
        found = (
            driving.ENABLE,
            driving.DATA,
            driving.STATUS,
            driving.WRITE_MODE,
            driving.READ_MODE,
            driving.SHARP_DATA,
            driving.SHARP_CONTROL,
        )

        # Assert
        self.assertEqual(found, expected)

    def test_a_register_holds_four_bits(self) -> None:
        # Arrange
        expected = (16, 0x0F)

        # Act
        found = (driving.REGISTERS, driving.NIBBLE)

        # Assert
        self.assertEqual(found, expected)


class ClockTest(unittest.TestCase):
    def test_a_clock_reads_the_hand_it_was_given(self) -> None:
        # Arrange
        hand = [driving.FROZEN]

        # Act
        chip = driving.a_clock(hand)

        # Assert
        self.assertEqual(
            (chip.now(), chip.seconds(), chip.store.stamp),
            (driving.FROZEN * 32_768, driving.FROZEN, driving.FROZEN),
        )

    def test_a_crystal_clock_reads_its_hand_as_crystal_cycles(self) -> None:
        # Arrange
        hand = [driving.FROZEN * 32_768 + 5]

        # Act
        chip = driving.a_crystal_clock(hand)

        # Assert
        self.assertEqual(
            (chip.now(), chip.seconds(), chip.store.stamp),
            (driving.FROZEN * 32_768 + 5, driving.FROZEN, driving.FROZEN),
        )

    def test_a_whole_second_clock_reads_its_hand_as_seconds(self) -> None:
        # Arrange
        hand = [driving.FROZEN]

        # Act
        chip = driving.a_whole_second_clock(hand)

        # Assert
        self.assertEqual(
            (chip.now(), chip.seconds(), chip.crystal.rate),
            (driving.FROZEN, driving.FROZEN, 1),
        )

    def test_the_lockout_is_passed_at_the_first_whole_cycle_past_125_microseconds(self) -> None:
        # Arrange
        first_whole_cycle_past = 5

        # Act
        passed = driving.PAST_THE_LOCKOUT

        # Assert
        self.assertEqual(passed, first_whole_cycle_past)

    def test_and_starts_dated_on_a_twenty_four_hour_dial(self) -> None:
        # Arrange
        hand = [driving.FROZEN]

        # Act
        chip = driving.a_clock(hand)

        # Assert
        self.assertEqual((chip.dated(), chip.twenty_four_hour()), (True, True))

    def test_and_is_the_epson_part(self) -> None:
        # Arrange
        hand = [driving.FROZEN]

        # Act
        chip = driving.a_clock(hand)

        # Assert
        self.assertEqual(chip.model, "rtc-4513")


class SessionTest(unittest.TestCase):
    def test_opening_leaves_the_chip_at_the_register_named(self) -> None:
        # Arrange
        chip = driving.a_clock([driving.FROZEN])

        # Act
        driving.opened(chip, driving.READ_MODE, driving.MI1)

        # Assert
        self.assertEqual((chip.state, chip.index), ("read", driving.MI1))

    def test_writing_lands_each_nibble_at_the_next_register(self) -> None:
        # Arrange
        chip = driving.a_clock([driving.FROZEN])

        # Act
        driving.written(chip, driving.MI1, 1, 2)

        # Assert
        self.assertEqual((chip.store.read(driving.MI1), chip.store.read(driving.MI10)), (1, 2))

    def test_reading_back_answers_what_was_written(self) -> None:
        # Arrange
        chip = driving.a_clock([driving.FROZEN])
        driving.written(chip, driving.MI1, 7)

        # Act
        answered = driving.read_back(chip, driving.MI1)

        # Assert
        self.assertEqual(answered, 7)


class BitTest(unittest.TestCase):
    def test_a_bit_spelled_as_register_and_position_is_found(self) -> None:
        # Arrange
        spelled = "H10.D2"

        # Act
        found = driving.located(spelled)

        # Assert
        self.assertEqual(found, (5, 0x4))

    def test_a_bit_named_in_the_register_table_is_found(self) -> None:
        # Arrange
        name = "h20"

        # Act
        found = driving.named_bit(name)

        # Assert
        self.assertEqual(found, (5, 0x2))

    def test_a_bit_mask_is_found_by_its_printed_name(self) -> None:
        # Arrange
        name = "INT/STND"

        # Act
        found = driving.mask_of(name)

        # Assert
        self.assertEqual(found, 0x2)


if __name__ == "__main__":
    unittest.main()
