import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.driving import (
    D10,
    DATA,
    DIGITS,
    ENABLE,
    FROZEN,
    H10,
    MO10,
    OSC_FLAG,
    PM,
    READ_MODE,
    S1,
    S10,
    STATUS,
    WRITE_MODE,
    W,
    a_clock,
    opened,
    written,
)
from snesrtc import Chip, Store

UNANSWERED = 0x4843


class SessionTest(unittest.TestCase):
    def test_a_chip_that_was_never_enabled_answers_nothing(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])

        # Act
        answered = chip.read(DATA)

        # Assert
        self.assertEqual(answered, 0x00)

    def test_enabling_it_is_not_enough_on_its_own(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        chip.write(ENABLE, 0x01)

        # Act
        answered = chip.read(DATA)

        # Assert
        self.assertEqual(answered, 0x00)

    def test_the_write_mode_code_and_an_index_open_a_session(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])

        # Act
        opened(chip, WRITE_MODE, S1)

        # Assert
        self.assertEqual(chip.state, "write")

    def test_the_read_mode_code_opens_one_that_only_reads(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])

        # Act
        opened(chip, READ_MODE, S1)

        # Assert
        self.assertEqual(chip.state, "read")

    def test_clearing_the_enable_bit_closes_it_again(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        opened(chip, WRITE_MODE, S1)
        chip.write(ENABLE, 0x00)

        # Act
        answered = chip.read(DATA)

        # Assert
        self.assertEqual(answered, 0x00)

    def test_a_mode_code_the_manual_does_not_name_leaves_the_session_unopened(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        chip.write(ENABLE, 0x01)
        chip.write(DATA, 0x07)

        # Act
        answered = chip.read(DATA)

        # Assert
        self.assertEqual(answered, 0x00)

    def test_the_mode_code_is_matched_on_the_whole_byte_not_its_low_nibble(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        chip.write(ENABLE, 0x01)
        read_code_under_a_high_nibble = 0x50 | READ_MODE

        # Act
        chip.write(DATA, read_code_under_a_high_nibble)

        # Assert
        self.assertEqual(chip.state, "mode")

    def test_the_enable_register_reads_back_what_was_put_there(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        chip.write(ENABLE, 0x01)

        # Act
        answered = chip.read(ENABLE)

        # Assert
        self.assertEqual(answered, 0x01)

    def test_an_address_the_chip_does_not_answer_gives_nothing_back(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])

        # Act
        answered = chip.read(UNANSWERED)

        # Assert
        self.assertEqual(answered, 0x00)

    def test_and_writing_to_one_changes_nothing(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        before = list(chip.store.bytes)

        # Act
        chip.write(UNANSWERED, 0x0F)

        # Assert
        self.assertEqual(chip.store.bytes, before)


class ReadTest(unittest.TestCase):
    def test_reading_walks_forward_through_the_registers(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, *DIGITS)
        opened(chip, READ_MODE, S1)

        # Act
        answered = [chip.read(DATA) for _ in range(12)]

        # Assert
        self.assertEqual(answered, list(DIGITS))

    def test_the_address_wraps_after_the_last_register(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        opened(chip, WRITE_MODE, 15)

        # Act
        chip.read(DATA)

        # Assert
        self.assertEqual(chip.index, 0)

    def test_a_session_can_start_partway_along(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, *DIGITS)
        opened(chip, READ_MODE, 4)

        # Act
        answered = chip.read(DATA)

        # Assert
        self.assertEqual(answered, DIGITS[4])

    def test_a_write_during_a_read_mode_session_is_ignored(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, *DIGITS)
        opened(chip, READ_MODE, 4)
        chip.write(DATA, 0x09)

        # Act
        answered = chip.read(DATA)

        # Assert
        self.assertEqual(answered, DIGITS[4])


class StatusTest(unittest.TestCase):
    def test_the_status_register_reports_ready_after_a_transfer(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        opened(chip, WRITE_MODE, S1)

        # Act
        answered = chip.read(STATUS)

        # Assert
        self.assertEqual(answered & 0x80, 0x80)

    def test_and_reading_it_clears_the_bit(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        opened(chip, WRITE_MODE, S1)
        chip.read(STATUS)

        # Act
        answered = chip.read(STATUS)

        # Assert
        self.assertEqual(answered & 0x80, 0x00)


class WriteTest(unittest.TestCase):
    def test_a_written_digit_lands_where_the_address_points(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        opened(chip, WRITE_MODE, 2)

        # Act
        chip.write(DATA, 0x05)

        # Assert
        self.assertEqual(chip.store.read(2), 0x05)

    def test_only_the_low_four_bits_survive(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        opened(chip, WRITE_MODE, 2)

        # Act
        chip.write(DATA, 0xF5)

        # Assert
        self.assertEqual(chip.store.read(2), 0x05)

    def test_the_address_moves_on_after_each_one(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        opened(chip, WRITE_MODE, 2)

        # Act
        chip.write(DATA, 0x05)

        # Assert
        self.assertEqual(chip.index, 3)


class DigitFieldTest(unittest.TestCase):
    def test_the_tens_of_seconds_digit_stops_at_three_bits(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, *DIGITS)
        chip.store.write(S10, 0x8 | 0x4)

        # Act
        moment = chip.moment()

        # Assert
        self.assertEqual(moment.second, DIGITS[0] + 40)

    def test_the_oscillator_flag_is_not_part_of_the_seconds(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, *DIGITS)
        chip.store.write(S10, OSC_FLAG)

        # Act
        moment = chip.moment()

        # Assert
        self.assertEqual(moment.second, DIGITS[0])

    def test_the_tens_of_months_digit_is_one_bit_wide(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, *DIGITS)
        chip.store.write(MO10, 0xF)

        # Act
        moment = chip.moment()

        # Assert
        self.assertEqual(moment.month, DIGITS[8] + 10)

    def test_the_free_ram_beside_the_tens_of_days_is_not_part_of_the_date(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, *DIGITS)
        chip.store.write(D10, 0x4 | 0x1)

        # Act
        moment = chip.moment()

        # Assert
        self.assertEqual(moment.day, DIGITS[6] + 10)

    def test_the_weekday_counter_is_three_bits(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, *DIGITS)
        chip.store.write(W, 0xF)

        # Act
        moment = chip.moment()

        # Assert
        self.assertEqual(moment.weekday, 7)

    def test_writing_the_time_back_leaves_free_ram_alone(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, *DIGITS)
        chip.store.write(MO10, chip.store.read(MO10) | 0x4)
        hand[0] = FROZEN + 86_400

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual(chip.store.read(MO10) & 0x4, 0x4)


class NotationTest(unittest.TestCase):
    def test_a_configured_chip_reads_hours_on_a_twenty_four_hour_dial(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, *DIGITS)

        # Act
        moment = chip.moment()

        # Assert
        self.assertEqual(moment.hour, 12)

    def test_the_afternoon_flag_carries_the_hour_past_noon(self) -> None:
        # Arrange
        chip = a_clock([FROZEN], control_f=0)
        written(chip, S1, 0, 0, 0, 0, 3, 0, 8, 1, 8, 0, 6, 2)
        chip.store.write(H10, chip.store.read(H10) | PM)

        # Act
        moment = chip.moment()

        # Assert
        self.assertEqual(moment.hour, 15)

    def test_twelve_in_the_morning_is_the_top_of_the_day(self) -> None:
        # Arrange
        chip = a_clock([FROZEN], control_f=0)
        written(chip, S1, 0, 0, 0, 0, 2, 1, 8, 1, 8, 0, 6, 2)

        # Act
        moment = chip.moment()

        # Assert
        self.assertEqual(moment.hour, 0)

    def test_twelve_in_the_afternoon_is_noon(self) -> None:
        # Arrange
        chip = a_clock([FROZEN], control_f=0)
        written(chip, S1, 0, 0, 0, 0, 2, 1, 8, 1, 8, 0, 6, 2)
        chip.store.write(H10, chip.store.read(H10) | PM)

        # Act
        moment = chip.moment()

        # Assert
        self.assertEqual(moment.hour, 12)

    def test_the_afternoon_flag_is_set_when_the_time_is_written_back(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand, control_f=0)
        written(chip, S1, 0, 0, 0, 0, 1, 1, 8, 1, 8, 0, 6, 2)
        hand[0] = FROZEN + 7200

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual(chip.store.read(H10) & PM, PM)

    def test_and_cleared_again_in_the_morning(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand, control_f=0)
        written(chip, S1, 0, 0, 0, 0, 1, 1, 8, 1, 8, 0, 6, 2)
        chip.store.write(H10, chip.store.read(H10) | PM)
        hand[0] = FROZEN + 43_200

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual(chip.store.read(H10) & PM, 0)

    def test_the_tens_of_hours_bit_never_rises_in_twelve_hour_notation(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand, control_f=0)
        written(chip, S1, 0, 0, 0, 0, 1, 1, 8, 1, 8, 0, 6, 2)
        hand[0] = FROZEN + 7200

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual(chip.store.read(H10) & 0x2, 0)

    def test_a_write_to_the_afternoon_flag_is_disregarded_on_a_twenty_four_hour_dial(
        self,
    ) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, *DIGITS)
        chip.store.write(H10, chip.store.read(H10) | PM)
        hand[0] = FROZEN + 60

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual(chip.store.read(H10) & PM, 0)


class ResetTest(unittest.TestCase):
    def test_a_reset_closes_any_session(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, S1, 7)
        opened(chip, READ_MODE, S1)
        chip.reset()

        # Act
        answered = chip.read(DATA)

        # Assert
        self.assertEqual((answered, chip.state), (0x00, "inactive"))

    def test_a_chip_prints_as_its_state_and_its_place(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])

        # Act
        shown = repr(chip)

        # Assert
        self.assertIn("inactive", shown)


def machine_cycles() -> int:
    return time.time_ns() * 32_768 // 1_000_000_000


class DefaultClockTest(unittest.TestCase):
    def test_a_chip_given_no_clock_reads_the_machine_in_crystal_cycles(self) -> None:
        # Arrange
        chip = Chip("rtc-4513", Store(cleared=True))
        before = machine_cycles()

        # Act
        reading = chip.now()

        # Assert
        self.assertGreaterEqual(reading, before)
        self.assertLessEqual(reading, machine_cycles())

    def test_a_whole_second_chip_given_no_clock_reads_the_machine_in_seconds(self) -> None:
        # Arrange
        chip = Chip("rtc-4513", Store(cleared=True), rate=1)
        before = int(time.time())

        # Act
        reading = chip.now()

        # Assert
        self.assertGreaterEqual(reading, before)
        self.assertLessEqual(reading, int(time.time()))


if __name__ == "__main__":
    unittest.main()
