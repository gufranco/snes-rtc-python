import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.driving import (
    ADJUST,
    CAL_HW,
    CD,
    CE,
    CF,
    DATA,
    ENABLE,
    FACTS,
    FROZEN,
    HOURS_24,
    INT_STND,
    IRQ_F,
    MASK,
    MI1,
    MI10,
    OSC_FLAG,
    READ_FLAG,
    READ_MODE,
    RESET,
    S1,
    S10,
    a_crystal_clock,
    a_whole_second_clock,
    located,
    opened,
    read_back,
    written,
)
from snesrtc import Chip, Store, crystal, epson

RATE: int = FACTS["crystalHz"]["value"]

START = FROZEN * RATE

EVERY_SECOND = FACTS["controlRegisterE"]["bits"]["t0"]["mask"]

FAST = 64


def lockout_ticks() -> int:
    micro: float = FACTS["controlRegisterD"]["bits"]["thirtySecondAdjust"]["lockoutMicroseconds"]
    return round(RATE * micro / 1_000_000)


def ticking_every_second(hand: list[int], control_e: int) -> Any:
    chip = a_crystal_clock(hand)
    written(chip, S1, 0, 0)
    written(chip, CE, control_e)
    chip.write(ENABLE, 0x00)
    return chip


class CountingTest(unittest.TestCase):
    def test_a_read_inside_a_session_shows_the_second_that_has_just_passed(self) -> None:
        # Arrange
        hand = [START]
        chip = a_crystal_clock(hand)
        written(chip, S1, 0)
        opened(chip, READ_MODE, S1)
        hand[0] += RATE

        # Act
        shown = chip.read(DATA)

        # Assert
        self.assertEqual(shown, 1)

    def test_a_second_that_has_not_yet_ended_does_not_count(self) -> None:
        # Arrange
        hand = [START]
        chip = a_crystal_clock(hand)
        written(chip, S1, 0)
        opened(chip, READ_MODE, S1)
        hand[0] += RATE - 1

        # Act
        shown = chip.read(DATA)

        # Assert
        self.assertEqual(shown, 0)

    def test_the_read_flag_rises_when_a_second_passes_inside_a_session(self) -> None:
        # Arrange
        where, bit = located(FACTS["readFlag"]["bit"].split(",")[0])
        hand = [START]
        chip = a_crystal_clock(hand)
        opened(chip, READ_MODE, where)
        hand[0] += RATE

        # Act
        flag = chip.read(DATA) & bit

        # Assert
        self.assertEqual(flag, bit)

    def test_but_not_when_the_second_passed_between_sessions(self) -> None:
        # Arrange
        hand = [START]
        chip = a_crystal_clock(hand)
        hand[0] += RATE

        # Act
        flag = read_back(chip, MI10) & READ_FLAG

        # Assert
        self.assertEqual(flag, 0)


class DefaultTest(unittest.TestCase):
    def test_a_part_built_without_a_rate_counts_the_crystal(self) -> None:
        # Arrange
        hand = [START]
        held = Store(cleared=True)
        held.stamp = FROZEN
        held.write(CF, HOURS_24)
        held.write(CD, CAL_HW)
        held.write(CE, INT_STND)
        chip: Any = Chip("rtc-4513", held, now=lambda: hand[0])
        chip.read(epson.STATUS)
        hand[0] += 32_768 // 64

        # Act
        flag = read_back(chip, CD) & IRQ_F

        # Assert
        self.assertEqual((chip.crystal.rate, flag), (32_768, IRQ_F))


class PeriodTest(unittest.TestCase):
    def test_the_crystal_is_the_printed_frequency(self) -> None:
        # Arrange
        printed = FACTS["crystalHz"]["value"]

        # Act
        held = epson.CRYSTAL_HZ

        # Assert
        self.assertEqual(held, printed)

    def test_the_sixty_fourth_of_a_second_raises_the_flag_on_its_own_edge(self) -> None:
        # Arrange
        hand = [START]
        chip = ticking_every_second(hand, INT_STND)
        hand[0] += RATE // FAST - 1
        early = read_back(chip, CD) & IRQ_F
        chip.write(ENABLE, 0x00)
        hand[0] += 1

        # Act
        late = read_back(chip, CD) & IRQ_F

        # Assert
        self.assertEqual((early, late), (0, IRQ_F))

    def test_in_fixed_period_mode_the_flag_is_up_for_the_printed_low_time(self) -> None:
        # Arrange
        printed = FACTS["controlRegisterE"]["fixedPeriodLowMilliseconds"]["value"]
        fixed = EVERY_SECOND & ~FACTS["controlRegisterE"]["bits"]["intStnd"]["mask"]
        hands = [[START], [START]]
        chips = [ticking_every_second(hand, fixed) for hand in hands]
        hands[0][0] += RATE + round(RATE * printed / 1000) - 1
        hands[1][0] += RATE + round(RATE * printed / 1000)

        # Act
        flags = [read_back(chip, CD) & IRQ_F for chip in chips]

        # Assert
        self.assertEqual(flags, [IRQ_F, 0])


class PinTest(unittest.TestCase):
    def test_in_fixed_period_mode_std_p_is_low_for_the_printed_time_even_once_read(self) -> None:
        # Arrange
        fact = FACTS["controlRegisterE"]["fixedPeriodLowMilliseconds"]
        hand = [START]
        chip = ticking_every_second(hand, EVERY_SECOND)
        hand[0] += RATE
        read_back(chip, CD)
        chip.write(ENABLE, 0x00)
        hand[0] += round(RATE * fact["value"] / 1000) - 1
        during = chip.std_p
        hand[0] += 1

        # Act
        after = chip.std_p

        # Assert
        self.assertEqual((during, after), (crystal.LOW, crystal.OPEN))

    def test_in_interrupt_mode_std_p_stays_low_until_cd_is_read(self) -> None:
        # Arrange
        hand = [START]
        chip = ticking_every_second(hand, INT_STND | EVERY_SECOND)
        hand[0] += 2 * RATE
        before = chip.std_p
        read_back(chip, CD)

        # Act
        after = chip.std_p

        # Assert
        self.assertEqual((before, after), (crystal.LOW, crystal.OPEN))

    def test_under_mask_std_p_is_open(self) -> None:
        # Arrange
        fact = FACTS["controlRegisterE"]["bits"]["mask"]
        hand = [START]
        chip = ticking_every_second(hand, INT_STND | EVERY_SECOND | fact["mask"])
        hand[0] += RATE

        # Act
        level = chip.std_p

        # Assert
        self.assertEqual(level, crystal.OPEN)

    def test_whole_seconds_have_no_pulse_to_show(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_whole_second_clock(hand)
        written(chip, CE, EVERY_SECOND)
        chip.write(ENABLE, 0x00)
        hand[0] += 1

        # Act
        level = chip.std_p

        # Assert
        self.assertEqual(level, crystal.OPEN)


class AdjustTest(unittest.TestCase):
    def test_the_adjust_bit_reads_one_through_the_lockout_and_clears_after_it(self) -> None:
        # Arrange
        fact = FACTS["controlRegisterD"]["bits"]["thirtySecondAdjust"]
        hand = [START]
        chip = a_crystal_clock(hand)
        written(chip, CD, CAL_HW | fact["mask"])
        chip.write(ENABLE, 0x00)
        hand[0] += lockout_ticks() - 1
        during = read_back(chip, CD) & ADJUST
        chip.write(ENABLE, 0x00)
        hand[0] += 1

        # Act
        after = read_back(chip, CD) & ADJUST

        # Assert
        self.assertEqual((during, after), (ADJUST, 0))

    def test_a_write_to_cd_inside_the_lockout_leaves_the_adjust_bit_up(self) -> None:
        # Arrange
        hand = [START]
        chip = a_crystal_clock(hand)
        written(chip, CD, CAL_HW | ADJUST)
        written(chip, CD, CAL_HW)
        chip.write(ENABLE, 0x00)

        # Act
        held = read_back(chip, CD) & ADJUST

        # Assert
        self.assertEqual(held, ADJUST)

    def test_the_clock_registers_cannot_be_written_during_the_lockout(self) -> None:
        # Arrange
        hand = [START]
        chip = a_crystal_clock(hand)
        written(chip, S1, 0, 4)
        written(chip, CD, CAL_HW | ADJUST)
        written(chip, MI1, 7)
        chip.write(ENABLE, 0x00)
        hand[0] += lockout_ticks()

        # Act
        minute = read_back(chip, MI1)

        # Assert
        self.assertEqual(minute, 1)

    def test_a_reset_inside_the_lockout_cancels_the_adjustment(self) -> None:
        # Arrange
        hand = [START]
        chip = a_crystal_clock(hand)
        written(chip, S1, 0, 4, 3)
        written(chip, CD, CAL_HW | ADJUST)
        written(chip, CF, HOURS_24 | RESET)
        chip.write(ENABLE, 0x00)
        hand[0] += lockout_ticks()

        # Act
        held = (read_back(chip, MI1), read_back(chip, CD) & ADJUST)

        # Assert
        self.assertEqual(held, (3, 0))

    def test_the_adjustment_lands_when_the_window_ends_not_at_the_next_access(self) -> None:
        # Arrange
        hand = [START]
        chip = a_crystal_clock(hand)
        written(chip, S1, 0, 1)
        written(chip, CD, CAL_HW | ADJUST)
        chip.write(ENABLE, 0x00)
        hand[0] += 25 * RATE

        # Act
        held = (read_back(chip, S1), read_back(chip, S10), read_back(chip, MI1))

        # Assert
        self.assertEqual(held, (5, 2, 0))


class OscillationTest(unittest.TestCase):
    def test_an_interruption_raises_fo_and_loses_the_time_it_lasted(self) -> None:
        # Arrange
        where, bit = located(FACTS["oscFlag"]["bit"])
        hand = [START]
        chip = a_crystal_clock(hand)
        written(chip, S1, 0, 0)
        chip.write(ENABLE, 0x00)
        chip.interrupt_oscillation()
        hand[0] += 10 * RATE
        chip.restore_oscillation()
        hand[0] += RATE

        # Act
        held = (read_back(chip, S1), read_back(chip, where) & bit)

        # Assert
        self.assertEqual(held, (1, bit))

    def test_a_clock_read_while_its_oscillator_is_stopped_has_not_moved(self) -> None:
        # Arrange
        hand = [START]
        chip = a_crystal_clock(hand)
        written(chip, S1, 0, 0)
        chip.write(ENABLE, 0x00)
        chip.interrupt_oscillation()
        hand[0] += 5 * RATE

        # Act
        second = read_back(chip, S1)

        # Assert
        self.assertEqual(second, 0)

    def test_a_clock_never_interrupted_leaves_fo_alone(self) -> None:
        # Arrange
        hand = [START]
        chip = a_crystal_clock(hand)
        written(chip, S1, 0, 0)
        chip.write(ENABLE, 0x00)
        hand[0] += RATE

        # Act
        flag = read_back(chip, S10) & OSC_FLAG

        # Assert
        self.assertEqual(flag, 0)


class StopTest(unittest.TestCase):
    def test_a_stopped_clock_raises_no_sixty_fourth_edge(self) -> None:
        # Arrange
        hand = [START]
        chip = ticking_every_second(hand, INT_STND)
        written(chip, CF, HOURS_24 | epson.STOP)
        chip.write(ENABLE, 0x00)
        hand[0] += RATE // FAST

        # Act
        flag = read_back(chip, CD) & IRQ_F

        # Assert
        self.assertEqual(flag, 0)

    def test_under_mask_a_sixty_fourth_edge_raises_nothing(self) -> None:
        # Arrange
        hand = [START]
        chip = ticking_every_second(hand, INT_STND | MASK)
        hand[0] += RATE // FAST

        # Act
        chip.read(epson.STATUS)

        # Assert
        self.assertEqual(chip.store.read(CD) & IRQ_F, 0)


if __name__ == "__main__":
    unittest.main()
