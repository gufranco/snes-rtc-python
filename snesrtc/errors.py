"""Everything this package raises, in one place.

One module so a caller can see the whole set at once, and so `except` has
somewhere to import from. It imports nothing from the rest of the package, which
is what keeps it from ever closing a cycle: everything here raises, so everything
here imports this, and an import running the other way would make the order
modules happen to load in decide whether the package works at all.

One refusal is the whole set. Neither clock refuses anything a caller does to it:
a register written outside its documented range counts wrongly rather than
complaining, because that is what the part does, and a model that raised there
would be correcting the hardware.
"""

from __future__ import annotations


class UnknownModelError(Exception):
    """No clock goes by that name, under any spelling this package accepts.

    The same name the other members use for the same refusal, so a caller
    handling it across packages writes one `except` rather than one per part.
    The message names the clocks that would have worked, because a refusal that
    does not costs the caller a search through the source.
    """
