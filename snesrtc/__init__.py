"""The two real-time clocks a Super Nintendo cartridge could carry.

They are different parts with different protocols, so the model is chosen at
construction rather than assumed.

    from snesrtc import describe

    clock = describe("s-rtc").build()
    clock.read(0x2800)

Nothing starts cleared. A battery-backed cartridge holds what it held, and a
model that starts at zero hides the class of bug that only appears on a cartridge
that has been in a drawer.
"""

from . import calendar, epson, models, sharp, store
from .models import MODELS, Model, UnknownModelError, describe
from .store import Store
from .version import VERSION

__version__ = VERSION

__all__ = [
    "MODELS",
    "Model",
    "Store",
    "UnknownModelError",
    "__version__",
    "calendar",
    "describe",
    "epson",
    "models",
    "sharp",
    "store",
]
