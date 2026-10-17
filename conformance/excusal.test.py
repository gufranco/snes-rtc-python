import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance import excusal
from conformance.driving import (
    CAL_HW,
    CD,
    CF,
    DATA,
    ENABLE,
    H10,
    H20,
    HOURS_24,
    IRQ_F,
    MI1,
    PM,
    READ_MODE,
    STATUS,
    WRITE_MODE,
)
from snesrtc import Chip, Store

IRQF = "epson-irqf-not-writable"

DIGIT_FIELDS = "epson-digit-fields-narrower-than-registers"

TWELVE_HOUR = "epson-twelve-hour-mode-transient"


def a_chip(control_f: int = HOURS_24) -> Any:
    held = Store(cleared=True)
    held.write(CF, control_f)
    held.write(CD, CAL_HW)
    return Chip("rtc-4513", held, now=lambda: 0)


def at_register(chip: Any, mode: int, index: int) -> Any:
    chip.write(ENABLE, 0x01)
    chip.write(DATA, mode)
    chip.write(DATA, index)
    return chip


def a_ledger_that_has_seen_the_epson_part(chip: Any) -> excusal.Ledger:
    ledger = excusal.Ledger()
    ledger.follow(chip, ("w", ENABLE, 0x01))
    return ledger


class ExplainedTest(unittest.TestCase):
    def test_two_identical_lines_need_no_excuse(self) -> None:
        # Arrange
        excuse = None

        # Act
        found = excusal.explained("0F", "0F", excuse)

        # Assert
        self.assertEqual(found, set())

    def test_a_difference_inside_an_excused_field_is_named(self) -> None:
        # Arrange
        excuse = excusal.Excuse(((IRQ_F, IRQF),))

        # Act
        found = excusal.explained("06", "02", excuse)

        # Assert
        self.assertEqual(found, {IRQF})

    def test_bytes_that_agree_beside_an_excused_one_name_nothing_of_their_own(self) -> None:
        # Arrange
        excuse = excusal.Excuse(((0, ""), (IRQ_F, IRQF)))

        # Act
        found = excusal.explained("0006", "0002", excuse)

        # Assert
        self.assertEqual(found, {IRQF})

    def test_a_difference_outside_it_is_not_explained(self) -> None:
        # Arrange
        excuse = excusal.Excuse(((IRQ_F, IRQF),))

        # Act
        found = excusal.explained("07", "02", excuse)

        # Assert
        self.assertIsNone(found)

    def test_a_difference_on_a_line_with_no_excuse_is_not_explained(self) -> None:
        # Arrange
        excuse = None

        # Act
        found = excusal.explained("06", "02", excuse)

        # Assert
        self.assertIsNone(found)

    def test_a_line_that_is_not_hexadecimal_is_not_explained(self) -> None:
        # Arrange
        excuse = excusal.Excuse(((0xFF, IRQF),))

        # Act
        found = excusal.explained("ZZ", "02", excuse)

        # Assert
        self.assertIsNone(found)

    def test_nor_is_one_of_another_length(self) -> None:
        # Arrange
        excuse = excusal.Excuse(((0xFF, IRQF),))

        # Act
        found = excusal.explained("0602", "02", excuse)

        # Assert
        self.assertIsNone(found)

    def test_nor_is_one_longer_than_its_excuse(self) -> None:
        # Arrange
        excuse = excusal.Excuse(((0xFF, IRQF),))

        # Act
        found = excusal.explained("0606", "0202", excuse)

        # Assert
        self.assertIsNone(found)


class ReadExcuseTest(unittest.TestCase):
    def test_reading_cd_excuses_only_the_interrupt_flag(self) -> None:
        # Arrange
        chip = at_register(a_chip(), READ_MODE, CD)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)

        # Act
        excuse = ledger.excuse(chip, ("r", DATA, 0))

        # Assert
        self.assertEqual(excuse, excusal.Excuse(((IRQ_F, IRQF),)))

    def test_reading_h10_on_a_twenty_four_hour_dial_excuses_the_afternoon_bit(self) -> None:
        # Arrange
        chip = at_register(a_chip(), READ_MODE, H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)

        # Act
        excuse = ledger.excuse(chip, ("r", DATA, 0))

        # Assert
        self.assertEqual(excuse, excusal.Excuse(((PM, DIGIT_FIELDS),)))

    def test_and_on_a_twelve_hour_dial_the_twenty_bit(self) -> None:
        # Arrange
        chip = at_register(a_chip(control_f=0), READ_MODE, H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)

        # Act
        excuse = ledger.excuse(chip, ("r", DATA, 0))

        # Assert
        self.assertEqual(excuse, excusal.Excuse(((H20, TWELVE_HOUR),)))

    def test_reading_any_other_register_excuses_nothing(self) -> None:
        # Arrange
        chip = at_register(a_chip(), READ_MODE, MI1)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)

        # Act
        excuse = ledger.excuse(chip, ("r", DATA, 0))

        # Assert
        self.assertEqual(excuse, excusal.Excuse(((0, ""),)))

    def test_a_read_while_no_register_is_selected_excuses_nothing(self) -> None:
        # Arrange
        chip = a_chip()
        ledger = a_ledger_that_has_seen_the_epson_part(chip)

        # Act
        excuse = ledger.excuse(chip, ("r", DATA, 0))

        # Assert
        self.assertIsNone(excuse)

    def test_nor_does_a_read_at_another_address(self) -> None:
        # Arrange
        chip = at_register(a_chip(), READ_MODE, CD)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)

        # Act
        excuse = ledger.excuse(chip, ("r", STATUS, 0))

        # Assert
        self.assertIsNone(excuse)

    def test_nor_does_a_write(self) -> None:
        # Arrange
        chip = at_register(a_chip(), WRITE_MODE, CD)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)

        # Act
        excuse = ledger.excuse(chip, ("w", DATA, 0))

        # Assert
        self.assertIsNone(excuse)


class DumpExcuseTest(unittest.TestCase):
    def test_a_dump_excuses_the_interrupt_flag_in_cd_and_nothing_else(self) -> None:
        # Arrange
        chip = a_chip()
        ledger = a_ledger_that_has_seen_the_epson_part(chip)

        # Act
        excuse = ledger.excuse(chip, ("dump", 0, 0))

        # Assert
        assert excuse is not None
        self.assertEqual([at for at, field in enumerate(excuse.fields) if field != (0, "")], [CD])

    def test_a_dump_before_the_epson_part_is_touched_excuses_nothing(self) -> None:
        # Arrange
        chip = a_chip()
        ledger = excusal.Ledger()

        # Act
        excuse = ledger.excuse(chip, ("dump", 0, 0))

        # Assert
        self.assertIsNone(excuse)

    def test_a_dropped_afternoon_bit_is_excused_in_the_dump_too(self) -> None:
        # Arrange
        chip = at_register(a_chip(), WRITE_MODE, H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)
        ledger.follow(chip, ("w", DATA, PM | 0x1))

        # Act
        excuse = ledger.excuse(chip, ("dump", 0, 0))

        # Assert
        assert excuse is not None
        self.assertEqual(excuse.fields[H10], (PM, DIGIT_FIELDS))


class HeldBackTest(unittest.TestCase):
    def test_a_write_of_the_fixed_bit_is_held_back_by_the_recording(self) -> None:
        # Arrange
        chip = at_register(a_chip(), WRITE_MODE, H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)

        # Act
        ledger.follow(chip, ("w", DATA, PM | 0x1))

        # Assert
        self.assertEqual(ledger.held_back, PM)

    def test_and_blocks_the_next_catch_up(self) -> None:
        # Arrange
        chip = at_register(a_chip(), WRITE_MODE, H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)
        ledger.follow(chip, ("w", DATA, PM | 0x1))

        # Act
        blocked = ledger.blocks(chip)

        # Assert
        self.assertEqual(blocked, {DIGIT_FIELDS})

    def test_a_clean_ledger_blocks_nothing(self) -> None:
        # Arrange
        chip = a_chip()
        ledger = excusal.Ledger()

        # Act
        blocked = ledger.blocks(chip)

        # Assert
        self.assertEqual(blocked, set())

    def test_a_later_write_without_the_bit_lets_it_go(self) -> None:
        # Arrange
        chip = at_register(a_chip(), WRITE_MODE, H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)
        ledger.follow(chip, ("w", DATA, PM | 0x1))

        # Act
        ledger.follow(chip, ("w", DATA, 0x1))

        # Assert
        self.assertEqual(ledger.held_back, 0)

    def test_storing_the_register_directly_lets_it_go(self) -> None:
        # Arrange
        chip = at_register(a_chip(), WRITE_MODE, H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)
        ledger.follow(chip, ("w", DATA, PM | 0x1))

        # Act
        ledger.follow(chip, ("store", H10, 0x1))

        # Assert
        self.assertEqual(ledger.held_back, 0)

    def test_and_so_does_power(self) -> None:
        # Arrange
        chip = at_register(a_chip(), WRITE_MODE, H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)
        ledger.follow(chip, ("w", DATA, PM | 0x1))

        # Act
        ledger.follow(chip, ("power", 0, 0))

        # Assert
        self.assertEqual(ledger.held_back, 0)

    def test_storing_another_register_keeps_it(self) -> None:
        # Arrange
        chip = at_register(a_chip(), WRITE_MODE, H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)
        ledger.follow(chip, ("w", DATA, PM | 0x1))

        # Act
        ledger.follow(chip, ("store", MI1, 0x1))

        # Assert
        self.assertEqual(ledger.held_back, PM)

    def test_a_write_to_another_register_keeps_it(self) -> None:
        # Arrange
        chip = at_register(a_chip(), WRITE_MODE, MI1)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)
        ledger.held_back = PM

        # Act
        ledger.follow(chip, ("w", DATA, 0x1))

        # Assert
        self.assertEqual(ledger.held_back, PM)


if __name__ == "__main__":
    unittest.main()
