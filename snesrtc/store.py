"""The twenty bytes the cartridge keeps alive on a battery.

Thirteen hold the time, as one decimal digit per byte rather than as numbers. The
next three are control registers that only one of the two chips uses. The last
four hold the timestamp of the moment the clock was last read, which is how a
cartridge that has been in a drawer for a year knows how far to advance when it
is next powered up.

Storing a digit per byte looks wasteful and is what the hardware does, so the
model does it too. A model that stored the number would agree with the reference
on every value a game writes and disagree the moment a game writes a digit above
nine, which the chip accepts and stores.

Nothing here starts cleared. A battery-backed cartridge holds whatever it held,
and a fresh one from the factory holds whatever the silicon powered up with. A
caller who genuinely means a cleared cartridge says so.
"""

import random

SIZE = 20

STAMP_AT = 16

STAMP_BYTES = 4

UNSET_SEED = 0x5A5A5A5A


def _derive(seed, index):
    return random.Random((seed << 16) ^ index).randrange(0x100)


class Store:
    """The cartridge's own bytes, holding what they held."""

    def __init__(self, seed=UNSET_SEED, cleared=False, held=None):
        if cleared:
            self.bytes = [0] * SIZE
        else:
            self.bytes = [_derive(seed, index) for index in range(SIZE)]
        for index, value in enumerate(held or ()):
            self.bytes[index % SIZE] = value & 0xFF

    def read(self, index):
        return self.bytes[index % SIZE]

    def write(self, index, value):
        self.bytes[index % SIZE] = value & 0xFF

    @property
    def stamp(self):
        """When the clock was last read, as the four bytes hold it, low first."""
        value = 0
        for offset in range(STAMP_BYTES):
            value |= self.read(STAMP_AT + offset) << (offset * 8)
        return value

    @stamp.setter
    def stamp(self, value):
        for offset in range(STAMP_BYTES):
            self.write(STAMP_AT + offset, (value >> (offset * 8)) & 0xFF)

    def __repr__(self):
        return "<Store " + " ".join(f"{value:02X}" for value in self.bytes) + ">"
