from __future__ import annotations

import random
from collections.abc import Iterable
from typing import override

SIZE = 20

STAMP_AT = 16

STAMP_BYTES = 4

UNSET_SEED = 0x5A5A5A5A


def _derive(seed: int, index: int) -> int:
    return random.Random((seed << 16) ^ index).randrange(0x100)


class Store:
    __slots__ = ("bytes",)

    def __init__(
        self,
        seed: int = UNSET_SEED,
        cleared: bool = False,
        held: Iterable[int] | None = None,
    ) -> None:
        if cleared:
            self.bytes: list[int] = [0] * SIZE
        else:
            self.bytes = [_derive(seed, index) for index in range(SIZE)]
        for index, value in enumerate(held or ()):
            self.bytes[index % SIZE] = value & 0xFF

    def read(self, index: int) -> int:
        return self.bytes[index % SIZE]

    def write(self, index: int, value: int) -> None:
        self.bytes[index % SIZE] = value & 0xFF

    @property
    def stamp(self) -> int:
        value = 0
        for offset in range(STAMP_BYTES):
            value |= self.read(STAMP_AT + offset) << (offset * 8)
        return value

    @stamp.setter
    def stamp(self, value: int) -> None:
        for offset in range(STAMP_BYTES):
            self.write(STAMP_AT + offset, (value >> (offset * 8)) & 0xFF)

    @override
    def __repr__(self) -> str:
        return "<Store " + " ".join(f"{value:02X}" for value in self.bytes) + ">"
