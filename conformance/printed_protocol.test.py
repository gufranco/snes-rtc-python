import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.driving import (
    DATA,
    ENABLE,
    FACTS,
    FROZEN,
    H1,
    MI1,
    MI10,
    NIBBLE,
    READ_MODE,
    REGISTERS,
    S1,
    a_clock,
    opened,
    read_back,
    written,
)
from snesrtc import Chip, Store


def stepped(chip: Any) -> int:
    at = int(chip.index)
    chip.read(DATA)
    return at


def disregarded(code: int) -> bool:
    chip = a_clock([FROZEN])
    chip.store.write(0x05, 0x0A)
    before = list(chip.store.bytes)
    chip.write(ENABLE, 0x01)
    chip.write(DATA, code)
    chip.write(DATA, 0x05)
    chip.write(DATA, 0x09)
    return bool(chip.store.bytes == before and chip.read(DATA) == 0x00)


def registers_at_power_on(seed: int) -> list[int]:
    chip = Chip("rtc-4513", Store(seed=seed), now=lambda: FROZEN)
    opened(chip, READ_MODE, S1)
    return [chip.read(DATA) for _ in range(REGISTERS)]


class PrintedBehaviourTest(unittest.TestCase):
    def test_the_address_returns_to_zero_after_the_last_register(self) -> None:
        # Arrange
        printed = FACTS["registerCount"]["value"]
        chip = a_clock([FROZEN])
        opened(chip, READ_MODE, S1)

        # Act
        visited = [stepped(chip) for _ in range(printed + 1)]

        # Assert
        self.assertEqual(visited, [*range(printed), 0])

    def test_a_register_holds_the_printed_number_of_bits(self) -> None:
        # Arrange
        printed = FACTS["registerWidthBits"]["value"]
        chip = a_clock([FROZEN])
        written(chip, MI1, 0xFF)

        # Act
        answered = read_back(chip, MI1)

        # Assert
        self.assertEqual(answered, 2**printed - 1)

    def test_the_printed_write_code_opens_a_session_that_writes(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        chip.write(ENABLE, 0x01)
        chip.write(DATA, FACTS["writeModeCode"]["value"])
        chip.write(DATA, MI1)

        # Act
        chip.write(DATA, 0x05)

        # Assert
        self.assertEqual(chip.store.read(MI1), 0x05)

    def test_the_printed_read_code_opens_a_session_that_reads(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, MI1, 0x07)
        chip.write(ENABLE, 0x01)
        chip.write(DATA, FACTS["readModeCode"]["value"])
        chip.write(DATA, MI1)

        # Act
        answered = chip.read(DATA)

        # Assert
        self.assertEqual(answered, 0x07)

    def test_every_other_mode_code_leaves_the_data_that_follows_disregarded(self) -> None:
        # Arrange
        named = {FACTS["writeModeCode"]["value"], FACTS["readModeCode"]["value"]}
        others = [code for code in range(NIBBLE + 1) if code not in named]

        # Act
        ignored = all(disregarded(code) for code in others)

        # Assert
        self.assertEqual(ignored, FACTS["otherModeCodesIgnored"]["value"])

    def test_nibbles_after_the_first_land_at_the_following_addresses(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])

        # Act
        written(chip, MI1, 1, 2, 3)

        # Assert
        landed = [chip.store.read(at) for at in (MI1, MI10, H1)]
        self.assertEqual(landed == [1, 2, 3], FACTS["addressAutoIncrements"]["value"])

    def test_the_registers_come_up_holding_whatever_the_seed_left(self) -> None:
        # Arrange
        seeds = (1, 2)

        # Act
        seen = [registers_at_power_on(seed) for seed in seeds]

        # Assert
        self.assertEqual(seen[0] != seen[1], FACTS["powerOnStateUndefined"]["value"])


if __name__ == "__main__":
    unittest.main()
