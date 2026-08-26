"""The two real-time clocks a Super Nintendo cartridge could carry.

They are different parts with different protocols, so the model is chosen at
construction rather than assumed.

    from snesrtc import Chip

    clock = Chip("s-rtc")
    clock.read(0x2800)

Nothing starts cleared. A battery-backed cartridge holds what it held, and a
model that starts at zero hides the class of bug that only appears on a cartridge
that has been in a drawer.
"""

from typing import Any

from . import calendar as calendar
from . import epson as epson
from . import errors as errors
from . import models as models
from . import sharp as sharp
from . import store as store
from .errors import UnknownModelError
from .models import MODELS, Built, Model
from .store import Store
from .version import VERSION


def Chip(  # noqa: N802
    model: str | None = None, store: Store | None = None, **options: Any
) -> Built:
    """A clock of the named model, sharing one interface across the family.

    The model comes first because it is the thing a caller always knows and the
    store is the thing they often do not care about yet. Omitting it hands back a
    part with a store of its own, holding what a battery-backed cartridge holds
    rather than zeroes.

    The same shape as `Cpu(model, memory)` on the members that run a program, and
    named for what this is rather than for what it does. These parts answer
    accesses; they do not execute anything, and calling the constructor `Cpu`
    would say they did.
    """
    return models.lookup(model).build(Store() if store is None else store, **options)


__version__ = VERSION

__all__ = [
    "MODELS",
    "Chip",
    "Model",
    "Store",
    "UnknownModelError",
    "__version__",
]
