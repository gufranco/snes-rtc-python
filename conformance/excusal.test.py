import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance import excusal
from snesrtc import epson, store

IRQF = "epson-irqf-not-writable"

DIGIT_FIELDS = "epson-digit-fields-narrower-than-registers"

TWELVE_HOUR = "epson-twelve-hour-mode-transient"


def a_chip(control_f: int = epson.HOURS_24) -> epson.Chip:
    held = store.Store(cleared=True)
    held.write(epson.CF, control_f)
    held.write(epson.CD, epson.CAL_HW)
    return epson.Chip(held, now=lambda: 0)


def at_register(chip: epson.Chip, mode: int, index: int) -> epson.Chip:
    chip.write(epson.ENABLE, 0x01)
    chip.write(epson.DATA, mode)
    chip.write(epson.DATA, index)
    return chip


def a_ledger_that_has_seen_the_epson_part(chip: epson.Chip) -> excusal.Ledger:
    ledger = excusal.Ledger()
    ledger.follow(chip, ("w", epson.ENABLE, 0x01))
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
        excuse = excusal.Excuse(((epson.IRQ_F, IRQF),))

        # Act
        found = excusal.explained("06", "02", excuse)

        # Assert
        self.assertEqual(found, {IRQF})

    def test_bytes_that_agree_beside_an_excused_one_name_nothing_of_their_own(self) -> None:
        # Arrange
        excuse = excusal.Excuse(((0, ""), (epson.IRQ_F, IRQF)))

        # Act
        found = excusal.explained("0006", "0002", excuse)

        # Assert
        self.assertEqual(found, {IRQF})

    def test_a_difference_outside_it_is_not_explained(self) -> None:
        # Arrange
        excuse = excusal.Excuse(((epson.IRQ_F, IRQF),))

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
        chip = at_register(a_chip(), epson.READ_MODE, epson.CD)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)

        # Act
        excuse = ledger.excuse(chip, ("r", epson.DATA, 0))

        # Assert
        self.assertEqual(excuse, excusal.Excuse(((epson.IRQ_F, IRQF),)))

    def test_reading_h10_on_a_twenty_four_hour_dial_excuses_the_afternoon_bit(self) -> None:
        # Arrange
        chip = at_register(a_chip(), epson.READ_MODE, epson.H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)

        # Act
        excuse = ledger.excuse(chip, ("r", epson.DATA, 0))

        # Assert
        self.assertEqual(excuse, excusal.Excuse(((epson.PM, DIGIT_FIELDS),)))

    def test_and_on_a_twelve_hour_dial_the_twenty_bit(self) -> None:
        # Arrange
        chip = at_register(a_chip(control_f=0), epson.READ_MODE, epson.H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)

        # Act
        excuse = ledger.excuse(chip, ("r", epson.DATA, 0))

        # Assert
        self.assertEqual(excuse, excusal.Excuse(((epson.H20, TWELVE_HOUR),)))

    def test_reading_any_other_register_excuses_nothing(self) -> None:
        # Arrange
        chip = at_register(a_chip(), epson.READ_MODE, epson.MI1)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)

        # Act
        excuse = ledger.excuse(chip, ("r", epson.DATA, 0))

        # Assert
        self.assertEqual(excuse, excusal.Excuse(((0, ""),)))

    def test_a_read_while_no_register_is_selected_excuses_nothing(self) -> None:
        # Arrange
        chip = a_chip()
        ledger = a_ledger_that_has_seen_the_epson_part(chip)

        # Act
        excuse = ledger.excuse(chip, ("r", epson.DATA, 0))

        # Assert
        self.assertIsNone(excuse)

    def test_nor_does_a_read_at_another_address(self) -> None:
        # Arrange
        chip = at_register(a_chip(), epson.READ_MODE, epson.CD)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)

        # Act
        excuse = ledger.excuse(chip, ("r", epson.STATUS, 0))

        # Assert
        self.assertIsNone(excuse)

    def test_nor_does_a_write(self) -> None:
        # Arrange
        chip = at_register(a_chip(), epson.WRITE_MODE, epson.CD)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)

        # Act
        excuse = ledger.excuse(chip, ("w", epson.DATA, 0))

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
        self.assertEqual(
            [at for at, field in enumerate(excuse.fields) if field != (0, "")], [epson.CD]
        )

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
        chip = at_register(a_chip(), epson.WRITE_MODE, epson.H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)
        ledger.follow(chip, ("w", epson.DATA, epson.PM | 0x1))

        # Act
        excuse = ledger.excuse(chip, ("dump", 0, 0))

        # Assert
        assert excuse is not None
        self.assertEqual(excuse.fields[epson.H10], (epson.PM, DIGIT_FIELDS))


class HeldBackTest(unittest.TestCase):
    def test_a_write_of_the_fixed_bit_is_held_back_by_the_recording(self) -> None:
        # Arrange
        chip = at_register(a_chip(), epson.WRITE_MODE, epson.H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)

        # Act
        ledger.follow(chip, ("w", epson.DATA, epson.PM | 0x1))

        # Assert
        self.assertEqual(ledger.held_back, epson.PM)

    def test_and_blocks_the_next_catch_up(self) -> None:
        # Arrange
        chip = at_register(a_chip(), epson.WRITE_MODE, epson.H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)
        ledger.follow(chip, ("w", epson.DATA, epson.PM | 0x1))

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
        chip = at_register(a_chip(), epson.WRITE_MODE, epson.H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)
        ledger.follow(chip, ("w", epson.DATA, epson.PM | 0x1))

        # Act
        ledger.follow(chip, ("w", epson.DATA, 0x1))

        # Assert
        self.assertEqual(ledger.held_back, 0)

    def test_storing_the_register_directly_lets_it_go(self) -> None:
        # Arrange
        chip = at_register(a_chip(), epson.WRITE_MODE, epson.H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)
        ledger.follow(chip, ("w", epson.DATA, epson.PM | 0x1))

        # Act
        ledger.follow(chip, ("store", epson.H10, 0x1))

        # Assert
        self.assertEqual(ledger.held_back, 0)

    def test_and_so_does_power(self) -> None:
        # Arrange
        chip = at_register(a_chip(), epson.WRITE_MODE, epson.H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)
        ledger.follow(chip, ("w", epson.DATA, epson.PM | 0x1))

        # Act
        ledger.follow(chip, ("power", 0, 0))

        # Assert
        self.assertEqual(ledger.held_back, 0)

    def test_storing_another_register_keeps_it(self) -> None:
        # Arrange
        chip = at_register(a_chip(), epson.WRITE_MODE, epson.H10)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)
        ledger.follow(chip, ("w", epson.DATA, epson.PM | 0x1))

        # Act
        ledger.follow(chip, ("store", epson.MI1, 0x1))

        # Assert
        self.assertEqual(ledger.held_back, epson.PM)

    def test_a_write_to_another_register_keeps_it(self) -> None:
        # Arrange
        chip = at_register(a_chip(), epson.WRITE_MODE, epson.MI1)
        ledger = a_ledger_that_has_seen_the_epson_part(chip)
        ledger.held_back = epson.PM

        # Act
        ledger.follow(chip, ("w", epson.DATA, 0x1))

        # Assert
        self.assertEqual(ledger.held_back, epson.PM)


if __name__ == "__main__":
    unittest.main()
