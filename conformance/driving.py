from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from snesrtc import Chip, Store

HARDWARE = Path(__file__).resolve().parent / "hardware.json"

HELD: dict[str, Any] = json.loads(HARDWARE.read_text())

PARTS: dict[str, Any] = {part["part"]: part for part in HELD["parts"]}

EPSON: dict[str, Any] = PARTS["Epson RTC-4513"]

SHARP: dict[str, Any] = PARTS["Sharp S-RTC"]

FACTS: dict[str, Any] = EPSON["facts"]

ROWS: list[dict[str, Any]] = FACTS["registerTable"]["rows"]

RECORDED: dict[str, Any] = SHARP["recordedFacts"]

BITS = ("d0", "d1", "d2", "d3")

FROZEN = 1_000_000_000

DAY = 86_400

HOUR = 3_600

DIGITS = (0, 0, 0, 3, 2, 1, 8, 1, 8, 0, 6, 2)

ENABLE, DATA, STATUS = 0x4840, 0x4841, 0x4842

SHARP_DATA: int = RECORDED["dataAddress"]

SHARP_CONTROL: int = RECORDED["controlAddress"]

WRITE_MODE: int = FACTS["writeModeCode"]["value"]

READ_MODE: int = FACTS["readModeCode"]["value"]

REGISTERS: int = FACTS["registerCount"]["value"]

NIBBLE = (1 << FACTS["registerWidthBits"]["value"]) - 1

CRYSTAL: int = FACTS["crystalHz"]["value"]

WHOLE_SECONDS = 1

LOCKOUT_MICROSECONDS: int = FACTS["controlRegisterD"]["bits"]["thirtySecondAdjust"][
    "lockoutMicroseconds"
]

PAST_THE_LOCKOUT = math.ceil(CRYSTAL * LOCKOUT_MICROSECONDS / 1_000_000)

LOW_MILLISECONDS: float = FACTS["controlRegisterE"]["fixedPeriodLowMilliseconds"]["value"]

PAST_THE_PULSE = math.ceil(CRYSTAL * LOW_MILLISECONDS / 1_000)


def register(name: str) -> int:
    return next(int(row["address"]) for row in ROWS if row["name"] == name)


def named_bit(name: str) -> tuple[int, int]:
    return next(
        (int(row["address"]), 1 << at)
        for row in ROWS
        for at, key in enumerate(BITS)
        if row[key] == name
    )


def mask_of(name: str) -> int:
    return named_bit(name)[1]


S1, S10, MI1, MI10 = register("S1"), register("S10"), register("MI1"), register("MI10")

H1, H10, D1, D10 = register("H1"), register("H10"), register("D1"), register("D10")

MO1, MO10, Y1, Y10 = register("MO1"), register("MO10"), register("Y1"), register("Y10")

W, CD, CE, CF = register("W"), register("CD"), register("CE"), register("CF")

HOLD, CAL_HW, IRQ_F, ADJUST = (mask_of(name) for name in ("HOLD", "CAL/HW", "IRQ-F", "30ADJ."))

MASK, INT_STND = mask_of("MASK"), mask_of("INT/STND")

RESET, STOP, HOURS_24, TEST = (mask_of(name) for name in ("RESET", "STOP", "24/12", "TEST"))

PM, H20, OSC_FLAG = mask_of("PM/AM"), mask_of("h20"), mask_of("fo")

READ_FLAG = mask_of("fr")

READ_FLAG_AT = tuple(int(row["address"]) for row in ROWS if row["d3"] == "fr")


def a_store(second: int, control_f: int, control_d: int) -> Store:
    held = Store(cleared=True)
    held.stamp = second
    held.write(CF, control_f)
    held.write(CD, control_d)
    return held


def a_clock(hand: list[int], control_f: int = HOURS_24, control_d: int = CAL_HW) -> Any:
    held = a_store(hand[0], control_f, control_d)
    return Chip("rtc-4513", held, now=lambda: hand[0] * CRYSTAL)


def a_crystal_clock(hand: list[int]) -> Any:
    held = a_store(hand[0] // CRYSTAL, HOURS_24, CAL_HW)
    return Chip("rtc-4513", held, now=lambda: hand[0])


def a_whole_second_clock(
    hand: list[int], control_f: int = HOURS_24, control_d: int = CAL_HW
) -> Any:
    held = a_store(hand[0], control_f, control_d)
    return Chip("rtc-4513", held, now=lambda: hand[0], rate=WHOLE_SECONDS)


def opened(chip: Any, mode: int, index: int) -> None:
    chip.write(ENABLE, 0x01)
    chip.write(DATA, mode)
    chip.write(DATA, index)


def written(chip: Any, index: int, *nibbles: int) -> None:
    opened(chip, WRITE_MODE, index)
    for one in nibbles:
        chip.write(DATA, one)


def read_back(chip: Any, index: int) -> int:
    opened(chip, READ_MODE, index)
    return int(chip.read(DATA))


def located(spelled: str) -> tuple[int, int]:
    name, _, bit = spelled.strip().partition(".")
    return register(name), 1 << int(bit.removeprefix("D"))
