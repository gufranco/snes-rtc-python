from typing import Any

from . import calendar as calendar
from . import crystal as crystal
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
