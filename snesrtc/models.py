from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, override

from . import epson, sharp
from .errors import UnknownModelError
from .store import Store

Protocol = type[epson.Chip] | type[sharp.Chip]

Built = epson.Chip | sharp.Chip


class Model:
    __slots__ = ("addresses", "aliases", "name", "protocol", "summary")

    def __init__(
        self,
        name: str,
        summary: str,
        addresses: Iterable[int],
        protocol: Protocol,
        aliases: Sequence[str] = (),
    ) -> None:
        self.name = name
        self.summary = summary
        self.addresses = tuple(addresses)
        self.protocol = protocol
        self.aliases = tuple(aliases)

    def build(self, store: Store | None = None, **options: Any) -> Built:
        built = self.protocol(store if store is not None else Store(), **options)
        built.model = self.name
        return built

    @override
    def __repr__(self) -> str:
        return f"<Model {self.name}, answering at {self.addresses[0]:#06x}>"


_CATALOGUE = (
    Model(
        name="s-rtc",
        summary=(
            "Sharp S-RTC. Two addresses, one to read and one to drive a state "
            "machine, handing out thirteen bytes in a fixed order wrapped in a "
            "marker. The weekday is computed from the date when the date is "
            "written, and counted from there on. The year is three digits with a "
            "thousand added."
        ),
        addresses=(sharp.DATA, sharp.CONTROL),
        protocol=sharp.Chip,
        aliases=("srtc", "sharp", "sharprtc"),
    ),
    Model(
        name="rtc-4513",
        summary=(
            "Epson RTC-4513, as the SPC7110 presents it. Three addresses and an "
            "addressed register file rather than a fixed sequence, with two of the "
            "sixteen registers doing work when written rather than storing a value. "
            "The year is two digits read as 1990 through 2089."
        ),
        addresses=(epson.ENABLE, epson.DATA, epson.STATUS),
        protocol=epson.Chip,
        aliases=("rtc4513", "epson", "epsonrtc", "spc7110", "spc7110rtc"),
    ),
)

MODELS = {model.name: model for model in _CATALOGUE}


_BY_ALIAS: dict[str, Model] = {}
for _model in _CATALOGUE:
    _BY_ALIAS[_model.name.replace("-", "")] = _model
    for _alias in _model.aliases:
        _BY_ALIAS[_alias] = _model


def _normalise(name: str) -> str:
    return str(name).strip().lower().replace("-", "").replace("_", "").replace(" ", "")


def lookup(name: str | None) -> Model:
    if name is None:
        raise UnknownModelError(
            "no model was named, and this package will not choose one for you."
            f" Name one of: {', '.join(sorted(MODELS))}"
        )
    found = _BY_ALIAS.get(_normalise(name))
    if found is None:
        raise UnknownModelError(
            f"{name} is not a clock this package covers; it has {', '.join(sorted(MODELS))}"
        )
    return found
