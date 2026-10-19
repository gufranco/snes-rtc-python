import sys
import unittest
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.driving import (
    CAL_HW,
    CD,
    CE,
    CRYSTAL,
    DIGITS,
    ENABLE,
    FACTS,
    FROZEN,
    INT_STND,
    IRQ_F,
    PAST_THE_PULSE,
    S1,
    a_clock,
    a_crystal_clock,
    read_back,
    written,
)

UNIT_SECONDS = {"s": 1, "second": 1, "minute": 60, "hour": 3600}

PERIOD_BITS = FACTS["controlRegisterE"]["bits"]

EVERY_SECOND = INT_STND | PERIOD_BITS["t0"]["mask"]

A_MINUTE_TURNING = (9, 5, 8, 5, 2, 1)

A_SECOND_TURNING = (8, 5, 9, 5, 2, 1)

AN_HOUR_TURNING = (9, 5, 9, 5, 2, 1)


def period_in_seconds(period: str) -> Fraction:
    count, unit = period.split()
    return Fraction(count) * UNIT_SECONDS[unit]


def flag_after_a_second(control_e: int, start: tuple[int, ...]) -> int:
    hand = [FROZEN * CRYSTAL]
    chip = a_crystal_clock(hand)
    written(chip, S1, *start, *DIGITS[6:])
    written(chip, CE, control_e)
    chip.write(ENABLE, 0x00)
    hand[0] += CRYSTAL + PAST_THE_PULSE
    chip.write(ENABLE, 0x00)
    return read_back(chip, CD) & IRQ_F


class PrintedBehaviourTest(unittest.TestCase):
    def test_a_write_to_the_interrupt_flag_is_not_executed(self) -> None:
        # Arrange
        fact = FACTS["controlRegisterD"]["bits"]["irqF"]
        chip = a_clock([FROZEN])
        written(chip, CD, CAL_HW | fact["mask"])

        # Act
        answered = read_back(chip, CD)

        # Assert
        self.assertEqual(answered & fact["mask"], 0 if fact["readOnly"] else fact["mask"])

    def test_the_period_increment_raises_the_interrupt_flag_until_cd_is_read(self) -> None:
        # Arrange
        flag = FACTS["controlRegisterD"]["bits"]["irqF"]["mask"]
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, *DIGITS)
        written(chip, CE, EVERY_SECOND)
        chip.write(ENABLE, 0x00)
        hand[0] += 1
        chip.write(ENABLE, 0x00)

        # Act
        answered = (read_back(chip, CD), read_back(chip, CD))

        # Assert
        self.assertEqual((answered[0] & flag, answered[1] & flag), (flag, 0))

    def test_under_mask_the_period_increment_leaves_the_interrupt_flag_down(self) -> None:
        # Arrange
        mask = PERIOD_BITS["mask"]["mask"]

        # Act
        raised = (
            flag_after_a_second(EVERY_SECOND, DIGITS[:6]),
            flag_after_a_second(EVERY_SECOND | mask, DIGITS[:6]),
        )

        # Assert
        self.assertEqual(raised, (IRQ_F, 0))

    def test_and_setting_mask_puts_down_a_flag_already_raised(self) -> None:
        # Arrange
        mask = PERIOD_BITS["mask"]["mask"]
        chip = a_clock([FROZEN], control_d=CAL_HW | IRQ_F)

        # Act
        written(chip, CE, EVERY_SECOND | mask)

        # Assert
        self.assertEqual(chip.store.read(CD) & IRQ_F, 0)

    def test_interrupt_cycle_mode_holds_the_flag_and_fixed_period_mode_does_not(self) -> None:
        # Arrange
        interrupt_cycle = PERIOD_BITS["intStnd"]["mask"]
        every_second = PERIOD_BITS["t0"]["mask"]

        # Act
        raised = (
            flag_after_a_second(every_second | interrupt_cycle, DIGITS[:6]),
            flag_after_a_second(every_second, DIGITS[:6]),
        )

        # Assert
        self.assertEqual(raised, (IRQ_F, 0))

    def test_each_printed_period_raises_the_flag_when_its_digit_increments(self) -> None:
        # Arrange
        rows = FACTS["controlRegisterE"]["periodTable"]["rows"]
        chosen = [
            INT_STND
            | (PERIOD_BITS["t1"]["mask"] if row["t1"] else 0)
            | (PERIOD_BITS["t0"]["mask"] if row["t0"] else 0)
            for row in rows
        ]

        # Act
        raised = [
            tuple(
                bool(flag_after_a_second(control_e, start))
                for start in (A_SECOND_TURNING, A_MINUTE_TURNING, AN_HOUR_TURNING)
            )
            for control_e in chosen
        ]

        # Assert
        seconds = [period_in_seconds(row["period"]) for row in rows]
        self.assertEqual(raised, [(period <= 1, period <= 60, True) for period in seconds])


if __name__ == "__main__":
    unittest.main()
