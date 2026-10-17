import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.driving import (
    CAL_HW,
    CF,
    D10,
    DATA,
    DIGITS,
    ENABLE,
    FACTS,
    FROZEN,
    HOURS_24,
    MI10,
    MO10,
    READ_FLAG,
    S1,
    WRITE_MODE,
    a_clock,
    located,
    opened,
    read_back,
    written,
)


def flag_written(address: int, values: tuple[int, ...]) -> list[int]:
    chip = a_clock([FROZEN])
    kept = []
    for value in values:
        written(chip, address, value)
        kept.append(read_back(chip, address))
    return kept


class PrintedBehaviourTest(unittest.TestCase):
    def test_the_oscillator_flag_can_be_set_and_cleared_by_writing_it(self) -> None:
        # Arrange
        address, mask = located(FACTS["oscFlag"]["bit"])

        # Act
        kept = flag_written(address, (mask | 0x1, 0x1))

        # Assert
        self.assertEqual(kept, [mask | 0x1, 0x1])

    def test_a_second_ticking_while_ce_is_high_raises_every_read_flag(self) -> None:
        # Arrange
        flags = [located(one) for one in FACTS["readFlag"]["bit"].split(",")]
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, S1, *DIGITS)
        chip.write(ENABLE, 0x00)
        hand[0] += 5
        opened(chip, WRITE_MODE, CF)

        # Act
        chip.write(DATA, HOURS_24)

        # Assert
        self.assertEqual(
            [chip.store.read(address) & mask for address, mask in flags],
            [mask for _, mask in flags],
        )

    def test_ce_falling_clears_every_read_flag(self) -> None:
        # Arrange
        flags = [located(one) for one in FACTS["readFlag"]["bit"].split(",")]
        chip = a_clock([FROZEN])
        for address, mask in flags:
            chip.store.write(address, chip.store.read(address) | mask)

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual(
            [chip.store.read(address) & mask for address, mask in flags], [0] * len(flags)
        )

    def test_with_the_calendar_off_the_read_flags_beside_the_date_keep_what_was_written(
        self,
    ) -> None:
        # Arrange
        dated = FACTS["controlRegisterD"]["bits"]["calHw"]["mask"]
        chip = a_clock([FROZEN], control_d=CAL_HW & ~dated)
        written(chip, D10, READ_FLAG)
        written(chip, MO10, READ_FLAG)

        # Act
        chip.write(ENABLE, 0x00)

        # Assert
        self.assertEqual(
            [chip.store.read(at) & READ_FLAG for at in (D10, MO10)],
            [READ_FLAG] * 2,
        )

    def test_and_a_tick_does_not_raise_them(self) -> None:
        # Arrange
        dated = FACTS["controlRegisterD"]["bits"]["calHw"]["mask"]
        hand = [FROZEN]
        chip = a_clock(hand, control_d=CAL_HW & ~dated)
        written(chip, S1, *DIGITS)
        chip.write(ENABLE, 0x00)
        hand[0] += 5
        opened(chip, WRITE_MODE, CF)

        # Act
        chip.write(DATA, HOURS_24)

        # Assert
        self.assertEqual(
            [chip.store.read(at) & READ_FLAG for at in (MI10, D10, MO10)],
            [READ_FLAG, 0, 0],
        )


if __name__ == "__main__":
    unittest.main()
