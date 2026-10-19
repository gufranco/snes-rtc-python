import sys
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.driving import (
    CAL_HW,
    CD,
    CE,
    CF,
    CRYSTAL,
    DATA,
    DAY,
    ENABLE,
    FACTS,
    FROZEN,
    H10,
    HOLD,
    HOURS_24,
    INT_STND,
    IRQ_F,
    MASK,
    MI1,
    MO10,
    NIBBLE,
    OSC_FLAG,
    PAST_THE_LOCKOUT,
    READ_FLAG,
    READ_MODE,
    ROWS,
    S1,
    S10,
    W,
    a_clock,
    a_crystal_clock,
    opened,
    read_back,
    written,
)
from snesrtc import Chip, Store

CANDIDATE_BITS = (0x1, 0x2, 0x4, 0x8)

WRAP_LIMIT = 64

README_EXAMPLE = {
    "S1": 0,
    "S10": 5,
    "MI1": 9,
    "MI10": 5,
    "H1": 3,
    "H10": 2,
    "D1": 1,
    "D10": 3,
    "MO1": 2,
    "MO10": 1,
    "Y1": 9,
    "Y10": 9,
    "W": 5,
}


def stepped_index(chip: Any) -> int:
    chip.read(DATA)
    return int(chip.index)


def weekdays_seen(days: int) -> set[int]:
    hand = [FROZEN]
    chip = a_clock(hand)
    seen = set()
    for _ in range(days):
        hand[0] += DAY
        chip.write(ENABLE, 0x00)
        seen.add(chip.digit(W))
    return seen


def freezes_the_seconds(bit: int) -> bool:
    hand = [FROZEN]
    chip = a_clock(hand)
    written(chip, CD, CAL_HW | bit)
    hand[0] += 5
    chip.write(ENABLE, 0x00)
    return bool(chip.digit(S1) == 0)


def starts_the_date(bit: int) -> bool:
    chip = a_clock([FROZEN], control_d=0)
    written(chip, CD, bit)
    return bool(chip.dated())


def clears_when_read(bit: int) -> bool:
    chip = a_clock([FROZEN], control_d=CAL_HW | bit)
    chip.store.write(CE, INT_STND)
    answered = read_back(chip, CD)
    return bool(answered & bit and not chip.store.read(CD) & bit)


def rounds_to_the_minute(bit: int) -> bool:
    hand = [FROZEN * CRYSTAL]
    chip = a_crystal_clock(hand)
    chip.store.write(S10, 4)
    written(chip, CD, CAL_HW | bit)
    hand[0] += PAST_THE_LOCKOUT
    chip.write(ENABLE, 0x00)
    return (chip.digit(S1), chip.digit(S10), chip.digit(MI1)) == (0, 0, 1)


def seconds_five_later(bit: int) -> int:
    hand = [FROZEN]
    chip = a_clock(hand)
    chip.store.write(S1, 5)
    chip.store.write(S10, 2)
    written(chip, CF, HOURS_24 | bit)
    hand[0] += 5
    chip.write(ENABLE, 0x00)
    return int(chip.digit(S1) + chip.digit(S10) * 10)


def zeroes_the_seconds(bit: int) -> bool:
    chip = a_clock([FROZEN])
    chip.store.write(S1, 5)
    chip.store.write(S10, 2)
    written(chip, CF, HOURS_24 | bit)
    return (chip.digit(S1), chip.digit(S10)) == (0, 0)


def holds_the_seconds_where_they_were(bit: int) -> bool:
    return seconds_five_later(bit) == 25


def keeps_the_seconds_from_moving(bit: int) -> bool:
    return seconds_five_later(bit) != 30


def selects_twenty_four_hours(bit: int) -> bool:
    chip = a_clock([FROZEN], control_f=0)
    written(chip, CF, bit)
    return bool(chip.twenty_four_hour())


def clears_on_deselect(bit: int) -> bool:
    chip = a_clock([FROZEN])
    written(chip, CF, HOURS_24 | bit)
    stored = chip.store.read(CF) & bit
    chip.write(ENABLE, 0x00)
    return bool(stored and not chip.store.read(CF) & bit)


def bits_that(behaviour: Callable[[int], bool]) -> list[int]:
    return [bit for bit in CANDIDATE_BITS if behaviour(bit)]


class RegisterTableTest(unittest.TestCase):
    def test_the_table_has_one_row_for_every_register(self) -> None:
        # Arrange
        printed = FACTS["registerCount"]["value"]

        # Act
        rows = len(ROWS)

        # Assert
        self.assertEqual(rows, printed)

    def test_the_model_holds_as_many_registers_as_the_manual_gives(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        opened(chip, READ_MODE, S1)

        # Act
        visited = [stepped_index(chip) for _ in range(WRAP_LIMIT)]

        # Assert
        self.assertEqual(visited.index(S1) + 1, FACTS["registerCount"]["value"])

    def test_the_rows_are_in_address_order(self) -> None:
        # Arrange
        expected = list(range(len(ROWS)))

        # Act
        addresses = [row["address"] for row in ROWS]

        # Assert
        self.assertEqual(addresses, expected)

    def test_the_digit_masks_the_model_uses_are_the_ones_the_manual_prints(self) -> None:
        # Arrange
        chip: Any = Chip("rtc-4513", Store(cleared=True, held=[NIBBLE] * len(ROWS)), now=lambda: 0)

        # Act
        found = [chip.digit(index) for index in range(len(ROWS))]

        # Assert
        self.assertEqual(found, [row.get("digitMask", NIBBLE) for row in ROWS])

    def test_every_digit_mask_reaches_the_top_of_that_register_count_range(self) -> None:
        # Arrange
        counted = [row for row in ROWS if row["countRange"]]

        # Act
        undersized = [row["name"] for row in counted if row["countRange"][1] > row["digitMask"]]

        # Assert
        self.assertEqual(undersized, [])

    def test_and_no_mask_is_wider_than_the_count_range_needs(self) -> None:
        # Arrange
        counted = [row for row in ROWS if row["countRange"]]

        # Act
        oversized = [
            row["name"]
            for row in counted
            if row["digitMask"] > 2 ** row["countRange"][1].bit_length() - 1
        ]

        # Assert
        self.assertEqual(oversized, [])

    def test_the_control_registers_sit_where_the_manual_puts_them(self) -> None:
        # Arrange
        named = {row["name"]: row["address"] for row in ROWS}
        dating, notation, masking = (a_clock([FROZEN], 0, 0) for _ in range(3))
        masking.store.write(named["CD"], IRQ_F)

        # Act
        written(dating, named["CD"], CAL_HW)
        written(notation, named["CF"], HOURS_24)
        written(masking, named["CE"], MASK)

        # Assert
        self.assertEqual(
            (dating.dated(), notation.twenty_four_hour(), masking.store.read(named["CD"])),
            (True, True, 0),
        )

    def test_the_clock_registers_sit_where_the_manual_puts_them(self) -> None:
        # Arrange
        named = {row["name"]: row["address"] for row in ROWS}
        chip = a_clock([FROZEN])

        # Act
        for name, digit in README_EXAMPLE.items():
            written(chip, named[name], digit)

        # Assert
        self.assertEqual(repr(chip.moment()), "<1999-12-31 23:59:50 weekday=5>")

    def test_the_read_flag_sits_in_every_register_whose_top_bit_the_manual_calls_fr(
        self,
    ) -> None:
        # Arrange
        chip = a_clock([FROZEN])

        # Act
        chip.set_read_flag()

        # Assert
        self.assertEqual(
            tuple(index for index in range(len(ROWS)) if chip.store.read(index) & READ_FLAG),
            tuple(row["address"] for row in ROWS if row["d3"] == "fr"),
        )

    def test_the_oscillator_flag_sits_where_the_manual_calls_it_fo(self) -> None:
        # Arrange
        chip: Any = Chip("rtc-4513", Store(cleared=True, held=[OSC_FLAG] * (W + 1)), now=lambda: 0)
        flagged = a_clock([FROZEN])
        flagged.set_read_flag()

        # Act
        outside = [index for index in range(W + 1) if chip.digit(index) == 0]

        # Assert
        self.assertEqual(
            [index for index in outside if not flagged.store.read(index) & READ_FLAG],
            [row["address"] for row in ROWS if row["d3"] == "fo"],
        )

    def test_the_afternoon_flag_sits_where_the_manual_puts_it(self) -> None:
        # Arrange
        chip = a_clock([FROZEN], control_f=0)

        # Act
        chip.store_hour(15)

        # Assert
        self.assertEqual((ROWS[H10]["d2"], chip.store.read(H10)), ("PM/AM", 0x4))


class ProtocolTest(unittest.TestCase):
    def test_the_write_mode_code_is_the_one_the_manual_names(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        chip.write(ENABLE, 0x01)
        chip.write(DATA, FACTS["writeModeCode"]["value"])

        # Act
        chip.write(DATA, S1)

        # Assert
        self.assertEqual(chip.state, "write")

    def test_and_the_read_mode_code(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        chip.write(ENABLE, 0x01)
        chip.write(DATA, FACTS["readModeCode"]["value"])

        # Act
        chip.write(DATA, S1)

        # Assert
        self.assertEqual(chip.state, "read")

    def test_a_register_is_as_wide_as_the_manual_says(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, MI1, 0xFF)

        # Act
        answered = read_back(chip, MI1)

        # Assert
        self.assertEqual(answered, 2 ** FACTS["registerWidthBits"]["value"] - 1)

    def test_the_weekday_counts_over_the_range_the_manual_gives(self) -> None:
        # Arrange
        low, high = FACTS["weekdayCountsZeroToSix"]["value"]

        # Act
        seen = weekdays_seen(14)

        # Assert
        self.assertEqual(seen, set(range(low, high + 1)))


class ControlBitTest(unittest.TestCase):
    def test_control_register_d_bits_carry_the_manual_masks(self) -> None:
        # Arrange
        bits = FACTS["controlRegisterD"]["bits"]

        # Act
        found = {
            "hold": bits_that(freezes_the_seconds),
            "calHw": bits_that(starts_the_date),
            "irqF": bits_that(clears_when_read),
            "thirtySecondAdjust": bits_that(rounds_to_the_minute),
        }

        # Assert
        self.assertEqual(
            found,
            {
                "hold": [bits["hold"]["mask"]],
                "calHw": [bits["calHw"]["mask"]],
                "irqF": [bits["irqF"]["mask"]],
                "thirtySecondAdjust": [bits["thirtySecondAdjust"]["mask"]],
            },
        )

    def test_control_register_f_bits_carry_the_manual_masks(self) -> None:
        # Arrange
        bits = FACTS["controlRegisterF"]["bits"]

        # Act
        found = {
            "reset": bits_that(zeroes_the_seconds),
            "stop": bits_that(holds_the_seconds_where_they_were),
            "twentyFourTwelve": bits_that(selects_twenty_four_hours),
            "test": bits_that(clears_on_deselect),
        }

        # Assert
        self.assertEqual(
            found,
            {
                "reset": [bits["reset"]["mask"]],
                "stop": [bits["stop"]["mask"]],
                "twentyFourTwelve": [bits["twentyFourTwelve"]["mask"]],
                "test": [bits["test"]["mask"]],
            },
        )

    def test_the_interrupt_flag_is_marked_read_only(self) -> None:
        # Arrange
        bits = FACTS["controlRegisterD"]["bits"]

        # Act
        marked = bits["irqF"]["readOnly"]

        # Assert
        self.assertIs(marked, True)

    def test_the_two_bits_that_stop_the_clock_are_the_two_the_manual_says_stop_it(
        self,
    ) -> None:
        # Arrange
        bits = FACTS["controlRegisterF"]["bits"]

        # Act
        stopping = bits_that(keeps_the_seconds_from_moving)

        # Assert
        self.assertEqual(stopping, [bits["reset"]["mask"], bits["stop"]["mask"]])

    def test_and_hold_is_not_one_of_them(self) -> None:
        # Arrange
        held = Store(cleared=True)
        held.write(CD, HOLD)
        chip: Any = Chip("rtc-4513", held)

        # Act
        stopped = chip.stopped()

        # Assert
        self.assertIs(stopped, False)

    def test_the_stopping_bits_are_named_in_control_register_f_and_not_in_d(self) -> None:
        # Arrange
        stopping = {"reset", "stop"}

        # Act
        shared = stopping & set(FACTS["controlRegisterD"]["bits"])

        # Assert
        self.assertEqual(shared, set())

    def test_control_register_d_has_no_bit_that_adds_a_second(self) -> None:
        # Arrange
        bits = FACTS["controlRegisterD"]["bits"]

        # Act
        named = set(bits)

        # Assert
        self.assertEqual(named, {"hold", "calHw", "irqF", "thirtySecondAdjust"})


class ContradictionTest(unittest.TestCase):
    def test_six_registers_carry_a_digit_narrower_than_the_register(self) -> None:
        # Arrange
        clock_rows = ROWS[:13]

        # Act
        narrow = [row["name"] for row in clock_rows if row["digitMask"] != NIBBLE]

        # Assert
        self.assertEqual(narrow, ["S10", "MI10", "H10", "D10", "MO10", "W"])

    def test_the_tens_of_months_register_carries_a_single_bit(self) -> None:
        # Arrange
        row = ROWS[MO10]

        # Act
        mask = row["digitMask"]

        # Assert
        self.assertEqual(mask, 1)

    def test_the_free_ram_bits_are_the_ones_the_manual_marks(self) -> None:
        # Arrange
        clock_rows = ROWS[:13]

        # Act
        marked = {
            row["name"]: [key for key in ("d3", "d2", "d1", "d0") if row[key] == "*"]
            for row in clock_rows
        }

        # Assert
        self.assertEqual(
            {name: bits for name, bits in marked.items() if bits},
            {"D10": ["d2"], "MO10": ["d2", "d1"]},
        )


if __name__ == "__main__":
    unittest.main()
