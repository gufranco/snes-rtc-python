import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.driving import (
    ADJUST,
    CAL_HW,
    CD,
    CF,
    D1,
    D10,
    DATA,
    DAY,
    DIGITS,
    ENABLE,
    FROZEN,
    H1,
    HOLD,
    HOURS_24,
    IRQ_F,
    MI1,
    MI10,
    MO1,
    MO10,
    READ_FLAG,
    READ_FLAG_AT,
    READ_MODE,
    RESET,
    S1,
    S10,
    STOP,
    TEST,
    WRITE_MODE,
    W,
    a_clock,
    opened,
    written,
)


class ClockRangeTest(unittest.TestCase):
    def test_a_dated_chip_carries_the_day_over_at_midnight(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, *DIGITS)
        hand[0] = FROZEN + DAY

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual(chip.store.read(D1), DIGITS[6] + 1)

    def test_an_undated_chip_leaves_the_date_registers_as_the_program_left_them(
        self,
    ) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand, control_d=0)
        written(chip, S1, *DIGITS)
        hand[0] = FROZEN + DAY

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual(chip.store.read(D1), DIGITS[6])

    def test_but_the_weekday_still_counts(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand, control_d=0)
        written(chip, S1, *DIGITS)
        before = chip.store.read(W)
        hand[0] = FROZEN + DAY

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual(chip.store.read(W), (before + 1) % 7)


class ControlRegisterDTest(unittest.TestCase):
    def test_the_interrupt_flag_cannot_be_written(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        opened(chip, WRITE_MODE, CD)

        # Act
        chip.write(DATA, IRQ_F | CAL_HW)

        # Assert
        self.assertEqual(chip.store.read(CD) & IRQ_F, 0)

    def test_a_held_interrupt_flag_survives_a_write(self) -> None:
        # Arrange
        chip = a_clock([FROZEN], control_d=CAL_HW | IRQ_F)
        opened(chip, WRITE_MODE, CD)

        # Act
        chip.write(DATA, CAL_HW)

        # Assert
        self.assertEqual(chip.store.read(CD) & IRQ_F, IRQ_F)

    def test_reading_the_register_clears_the_interrupt_flag(self) -> None:
        # Arrange
        chip = a_clock([FROZEN], control_d=CAL_HW | IRQ_F)
        opened(chip, READ_MODE, CD)

        # Act
        chip.read(DATA)

        # Assert
        self.assertEqual(chip.store.read(CD) & IRQ_F, 0)

    def test_the_adjustment_bit_does_not_latch(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, *DIGITS)
        opened(chip, WRITE_MODE, CD)

        # Act
        chip.write(DATA, CAL_HW | ADJUST)

        # Assert
        self.assertEqual(chip.store.read(CD) & ADJUST, 0)

    def test_adjusting_below_the_half_minute_drops_the_seconds(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, DIGITS[0], 2, *DIGITS[2:])
        opened(chip, WRITE_MODE, CD)

        # Act
        chip.write(DATA, CAL_HW | ADJUST)

        # Assert
        self.assertEqual((chip.store.read(S1), chip.store.read(S10)), (0, 0))

    def test_adjusting_from_past_it_carries_into_the_next_minute(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, 0, 4, *DIGITS[2:])
        opened(chip, WRITE_MODE, CD)
        chip.write(DATA, CAL_HW | ADJUST)

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual((chip.store.read(MI1), chip.store.read(MI10)), (1, 3))

    def test_the_range_bit_adds_no_time_of_its_own(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, *DIGITS)
        opened(chip, WRITE_MODE, CD)
        chip.write(DATA, CAL_HW)

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual(chip.store.read(S1), DIGITS[0])


class HoldTest(unittest.TestCase):
    def test_a_held_clock_does_not_move_while_it_is_held(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, *DIGITS)
        written(chip, CD, CAL_HW | HOLD)
        hand[0] = FROZEN + 300

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual(chip.store.read(MI1), DIGITS[2])

    def test_releasing_it_hands_back_the_one_second_it_suppressed(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, *DIGITS)
        written(chip, CD, CAL_HW | HOLD)
        hand[0] = FROZEN + 300
        opened(chip, WRITE_MODE, CD)

        # Act
        chip.write(DATA, CAL_HW)

        # Assert
        self.assertEqual(chip.store.read(S1), DIGITS[0] + 1)

    def test_and_only_that_one_second_however_long_the_hold_lasted(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, *DIGITS)
        written(chip, CD, CAL_HW | HOLD)
        hand[0] = FROZEN + DAY
        opened(chip, WRITE_MODE, CD)

        # Act
        chip.write(DATA, CAL_HW)

        # Assert
        self.assertEqual(chip.store.read(MI1), DIGITS[2])

    def test_a_hold_that_spans_no_tick_gives_nothing_back(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, *DIGITS)
        written(chip, CD, CAL_HW | HOLD)
        opened(chip, WRITE_MODE, CD)

        # Act
        chip.write(DATA, CAL_HW)

        # Assert
        self.assertEqual(chip.store.read(S1), DIGITS[0])

    def test_setting_it_brings_the_digits_current_first(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, *DIGITS)
        hand[0] = FROZEN + 65
        opened(chip, WRITE_MODE, CD)

        # Act
        chip.write(DATA, CAL_HW | HOLD)

        # Assert
        self.assertEqual(chip.store.read(MI1), DIGITS[2] + 1)


class ControlRegisterFTest(unittest.TestCase):
    def test_a_reset_zeroes_the_seconds(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, 5, 2, *DIGITS[2:])
        opened(chip, WRITE_MODE, CF)

        # Act
        chip.write(DATA, HOURS_24 | RESET)

        # Assert
        self.assertEqual((chip.store.read(S1), chip.store.read(S10)), (0, 0))

    def test_a_reset_forces_the_test_bit_down(self) -> None:
        # Arrange
        chip = a_clock([FROZEN], control_f=HOURS_24 | TEST)
        opened(chip, WRITE_MODE, CF)

        # Act
        chip.write(DATA, HOURS_24 | TEST | RESET)

        # Assert
        self.assertEqual(chip.store.read(CF) & TEST, 0)

    def test_closing_the_chip_clears_the_test_bit(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, CF, HOURS_24 | TEST)

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual(chip.store.read(CF) & TEST, 0)

    def test_a_stopped_clock_does_not_move_when_time_passes(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, *DIGITS)
        written(chip, CF, HOURS_24 | STOP)
        hand[0] = FROZEN + 3600

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual(chip.store.read(H1), DIGITS[4])

    def test_a_reset_stops_it_too(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, *DIGITS)
        written(chip, CF, HOURS_24 | RESET)
        hand[0] = FROZEN + 3600

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual(chip.store.read(H1), DIGITS[4])

    def test_clearing_both_lets_it_run_again(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, *DIGITS)
        written(chip, CF, HOURS_24 | STOP)
        written(chip, CF, HOURS_24)
        hand[0] = FROZEN + 3600

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual(chip.store.read(H1), DIGITS[4] + 1)


class ReadFlagTest(unittest.TestCase):
    def test_closing_the_chip_clears_the_read_flag(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        for index in READ_FLAG_AT:
            chip.store.write(index, chip.store.read(index) | READ_FLAG)

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual([chip.store.read(at) & READ_FLAG for at in READ_FLAG_AT], [0] * 5)

    def test_a_second_ticking_during_an_open_session_raises_it(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, *DIGITS)
        chip.write(ENABLE, 0x00)
        hand[0] = FROZEN + 5
        opened(chip, WRITE_MODE, CF)

        # Act
        chip.write(DATA, HOURS_24 | RESET)

        # Assert
        self.assertEqual(chip.store.read(MI10) & READ_FLAG, READ_FLAG)


class TimeTest(unittest.TestCase):
    def test_a_running_clock_moves_forward_when_the_session_closes(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, *DIGITS)
        hand[0] = FROZEN + 65

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual((chip.store.read(MI1), chip.store.read(S1)), (1, 5))

    def test_opening_a_session_shows_the_time_as_the_last_one_left_it(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, *DIGITS)
        hand[0] = FROZEN + 65

        # Act
        opened(chip, WRITE_MODE, S1)

        # Assert
        self.assertEqual(chip.store.read(MI1), DIGITS[2])

    def test_an_impossible_date_corrects_on_the_next_day(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, 0, 0, 0, 0, 0, 0, 1, 3, 1, 1, 3, 9)
        hand[0] = FROZEN + DAY

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual(
            (
                chip.store.read(D1),
                chip.store.read(D10),
                chip.store.read(MO1),
                chip.store.read(MO10),
            ),
            (1, 0, 2, 1),
        )

    def test_a_leap_day_is_kept_where_the_year_has_one(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, 0, 0, 0, 0, 0, 0, 8, 2, 2, 0, 4, 2)
        hand[0] = FROZEN + DAY

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual((chip.store.read(D1), chip.store.read(MO1)), (9, 2))

    def test_and_skipped_where_it_does_not(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, 0, 0, 0, 0, 0, 0, 8, 2, 2, 0, 5, 2)
        hand[0] = FROZEN + DAY

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual((chip.store.read(D1), chip.store.read(MO1)), (1, 3))

    def test_the_year_is_read_as_the_range_this_package_covers(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, *DIGITS[:10], 9, 9)

        # Act
        moment = chip.moment()

        # Assert
        self.assertEqual(moment.year, 1999)

    def test_and_a_small_year_belongs_to_the_century_after(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, *DIGITS)

        # Act
        moment = chip.moment()

        # Assert
        self.assertEqual(moment.year, 2026)


if __name__ == "__main__":
    unittest.main()
