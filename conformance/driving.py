from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from snesrtc import epson, store

HARDWARE = Path(__file__).resolve().parent / "hardware.json"

HELD: dict[str, Any] = json.loads(HARDWARE.read_text())

PARTS: dict[str, Any] = {part["part"]: part for part in HELD["parts"]}

EPSON: dict[str, Any] = PARTS["Epson RTC-4513"]

SHARP: dict[str, Any] = PARTS["Sharp S-RTC"]

FACTS: dict[str, Any] = EPSON["facts"]

ROWS: list[dict[str, Any]] = FACTS["registerTable"]["rows"]

FROZEN = 1_000_000_000

DAY = 86_400

HOUR = 3_600

DIGITS = (0, 0, 0, 3, 2, 1, 8, 1, 8, 0, 6, 2)


def a_clock(
    hand: list[int], control_f: int = epson.HOURS_24, control_d: int = epson.CAL_HW
) -> epson.Chip:
    held = store.Store(cleared=True)
    held.stamp = hand[0]
    held.write(epson.CF, control_f)
    held.write(epson.CD, control_d)
    return epson.Chip(held, now=lambda: hand[0])


def opened(chip: epson.Chip, mode: int, index: int) -> None:
    chip.write(epson.ENABLE, 0x01)
    chip.write(epson.DATA, mode)
    chip.write(epson.DATA, index)


def written(chip: epson.Chip, index: int, *nibbles: int) -> None:
    opened(chip, epson.WRITE_MODE, index)
    for one in nibbles:
        chip.write(epson.DATA, one)


def read_back(chip: epson.Chip, index: int) -> int:
    opened(chip, epson.READ_MODE, index)
    return chip.read(epson.DATA)


def located(spelled: str) -> tuple[int, int]:
    name, _, bit = spelled.strip().partition(".")
    address = next(row["address"] for row in ROWS if row["name"] == name)
    return int(address), 1 << int(bit.removeprefix("D"))


def named_bit(name: str) -> tuple[int, int]:
    return next(
        (int(row["address"]), 1 << at)
        for row in ROWS
        for at, key in enumerate(("d0", "d1", "d2", "d3"))
        if row[key] == name
    )
