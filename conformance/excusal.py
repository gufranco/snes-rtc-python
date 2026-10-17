from __future__ import annotations

from typing import NamedTuple

from snesrtc import epson, store

IRQ_F_DIVERGENCE = "epson-irqf-not-writable"

DIGIT_FIELDS_DIVERGENCE = "epson-digit-fields-narrower-than-registers"

TWELVE_HOUR_DIVERGENCE = "epson-twelve-hour-mode-transient"

EPSON_ADDRESSES = (epson.ENABLE, epson.DATA, epson.STATUS)

NOT_SELECTED = (epson.INACTIVE, epson.MODE_SELECT)

UNEXCUSED = (0, "")

Field = tuple[int, str]

Operation = tuple[str, int, int]


class Excuse(NamedTuple):
    fields: tuple[Field, ...]


def fixed_hour_bit(held: store.Store) -> Field:
    if held.read(epson.CF) & epson.HOURS_24:
        return epson.PM, DIGIT_FIELDS_DIVERGENCE
    return epson.H20, TWELVE_HOUR_DIVERGENCE


def explained(theirs: str, ours: str, excuse: Excuse | None) -> set[str] | None:
    if theirs == ours:
        return set()
    if excuse is None or len(theirs) != len(ours) or len(theirs) != 2 * len(excuse.fields):
        return None
    try:
        pairs = zip(bytes.fromhex(theirs), bytes.fromhex(ours), strict=True)
    except ValueError:
        return None
    names: set[str] = set()
    for (mask, name), (one, other) in zip(excuse.fields, pairs, strict=True):
        if (one ^ other) & ~mask:
            return None
        if one != other:
            names.add(name)
    return names


class Ledger:
    def __init__(self) -> None:
        self.held_back = 0
        self.active = False

    def follow(self, chip: epson.Chip, operation: Operation) -> None:
        verb, first, second = operation
        if verb in ("r", "w") and first in EPSON_ADDRESSES:
            self.active = True
        if verb == "power" or (verb == "store" and first == epson.H10):
            self.held_back = 0
        writing = verb == "w" and first == epson.DATA and chip.state == epson.WRITING
        if writing and chip.index == epson.H10:
            self.held_back = second & fixed_hour_bit(chip.store)[0]

    def blocks(self, chip: epson.Chip) -> set[str]:
        return {fixed_hour_bit(chip.store)[1]} if self.held_back else set()

    def excuse(self, chip: epson.Chip, operation: Operation) -> Excuse | None:
        verb, first, _ = operation
        if verb == "dump" and self.active:
            return Excuse(tuple(self.dumped(chip.store, at) for at in range(store.SIZE)))
        if verb != "r" or first != epson.DATA or chip.state in NOT_SELECTED:
            return None
        return Excuse((self.read(chip.store, chip.index),))

    def read(self, held: store.Store, index: int) -> Field:
        if index == epson.CD:
            return epson.IRQ_F, IRQ_F_DIVERGENCE
        if index == epson.H10:
            bit, name = fixed_hour_bit(held)
            return bit | self.held_back, name
        return UNEXCUSED

    def dumped(self, held: store.Store, at: int) -> Field:
        if at == epson.CD:
            return epson.IRQ_F, IRQ_F_DIVERGENCE
        if at == epson.H10 and self.held_back:
            return self.held_back, fixed_hour_bit(held)[1]
        return UNEXCUSED
