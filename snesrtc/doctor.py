from __future__ import annotations

import hashlib
import json
import platform
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol, override


def installed_version(where: Path | None = None) -> str:
    found = re.search(
        r"""VERSION\s*[:=][^"']*["']([^"']+)["']""",
        (where or Path(__file__).resolve().parent / "version.py").read_text(),
    )
    return found.group(1) if found else "unknown"


ROOT = Path(__file__).resolve().parent.parent


def reachable(root: Path = ROOT, path: list[str] | None = None) -> bool:
    where = sys.path if path is None else path
    if str(root) in where:
        return False
    where.insert(0, str(root))
    return True


reachable()

from snesrtc import environment, models  # noqa: E402

VERSION = installed_version()

PIN = ROOT / "conformance" / "pinned.json"

DRIVER = ROOT / "conformance" / "ref" / "driver"

OLDEST_PYTHON = (3, 12)

MOMENT = 1_000_000_000

WITNESS = "s-rtc"


class Ticking(Protocol):
    def now(self) -> int: ...


class Addressed(Protocol):
    def read(self, address: int) -> int: ...


class Resettable(Protocol):
    def reset(self) -> object: ...


Builder = Callable[..., models.Built]


class Finding:
    def __init__(self, name: str, ok: bool, detail: str, advice: str | None = None) -> None:
        self.name = name
        self.ok = ok
        self.detail = detail
        self.advice = advice

    @property
    def line(self) -> str:
        return f"  {'ok  ' if self.ok else '   !'}  {self.name}: {self.detail}"

    @property
    def report(self) -> str:
        if self.ok or not self.advice:
            return self.line
        return f"{self.line}\n         {self.advice}"

    @override
    def __repr__(self) -> str:
        return f"<Finding {self.name} {'ok' if self.ok else 'not ok'}>"


def _python() -> Finding:
    return Finding(
        "python",
        sys.version_info[:2] >= OLDEST_PYTHON,
        f"{platform.python_version()} on {platform.system()} {platform.machine()}",
        f"this package needs {OLDEST_PYTHON[0]}.{OLDEST_PYTHON[1]} or newer",
    )


def _package() -> Finding:
    return Finding("snesrtc", True, f"version {VERSION}")


def _default_build(name: str, **options: Any) -> models.Built:
    return models.lookup(name).build(**options)


def _clock(name: str, build: Callable[..., Resettable]) -> Finding:
    try:
        built = build(name)
        built.reset()
    except Exception as trouble:
        return Finding(
            name,
            False,
            f"{type(trouble).__name__}: {trouble}",
            "this is the clock failing to build rather than anything to do with a"
            " reference; the line above is what it said",
        )
    described = models.lookup(name)
    where = ", ".join(f"{one:#06x}" for one in described.addresses)
    return Finding(
        name,
        True,
        f"answers {where}, protocol {described.protocol.__module__.rsplit('.', 1)[-1]},"
        f" model {getattr(built, 'model', name)}, and resets",
    )


def check_time_source(build: Callable[..., Ticking]) -> Finding:
    try:
        built = build(WITNESS, now=lambda: MOMENT)
        told = built.now()
    except Exception as trouble:
        return Finding(
            "time source",
            False,
            f"{type(trouble).__name__}: {trouble}",
            "asking the clock what time it thinks it is failed, which is itself the finding",
        )
    return Finding(
        "time source",
        told == MOMENT,
        f"a clock told {MOMENT} reads {told} back",
        "the clock is reading this machine rather than what it was given, so"
        " nothing recorded against it can be replayed",
    )


def check_foreign(build: Callable[..., Addressed]) -> Finding:
    try:
        built = build(WITNESS)
        elsewhere = max(models.lookup(WITNESS).addresses) + 1
        expected = getattr(built, "open_bus", 0x00)
        answered = built.read(elsewhere)
    except Exception as trouble:
        return Finding(
            "foreign address",
            False,
            f"{type(trouble).__name__}: {trouble}",
            "reading an address the clock does not own failed, which is itself the finding",
        )
    return Finding(
        "foreign address",
        answered == expected,
        f"{elsewhere:#06x} reads {answered:#04x}, an undriven bus being {expected:#04x}",
        "the clock is answering at an address it does not own",
    )


def _reference(where: Path | str) -> Finding:
    try:
        raw = Path(where).read_bytes()
    except OSError as trouble:
        return Finding(
            "reference",
            False,
            f"could not be read: {trouble}",
            "the file that pins which implementation this is held to is missing from conformance/",
        )
    digest = hashlib.sha256(raw).hexdigest()
    try:
        held = json.loads(raw)
    except ValueError as trouble:
        return Finding(
            "reference",
            False,
            f"is not readable as JSON: {trouble}, sha256 {digest}",
            "the file is here and damaged, which is worse than absent",
        )
    named = held.get("reference") or {}
    if not named:
        return Finding(
            "reference",
            False,
            f"names no implementation, sha256 {digest}",
            "a pin that names nothing pins nothing",
        )
    return Finding(
        "reference",
        True,
        f"{named.get('name', 'not stated')} at {named.get('commit', 'no commit')}, sha256 {digest}",
    )


def _driver(where: Path | str) -> Finding:
    found = Path(where).exists()
    return Finding(
        "reference driver",
        True,
        "built and here"
        if found
        else "not built, so the differential check will skip rather than run",
    )


def examine(
    build: Builder = _default_build, pin: Path | str = PIN, driver: Path | str = DRIVER
) -> list[Finding]:
    found = [_python(), _package()]
    found.extend(_clock(name, build) for name in sorted(models.MODELS))
    found.append(check_time_source(build))
    found.append(check_foreign(build))
    found.append(_reference(pin))
    found.append(_driver(driver))
    return found


def report(found: Sequence[Finding]) -> list[str]:
    unwell = [one for one in found if not one.ok]
    lines = [f"snesrtc {VERSION} on {platform.python_version()}, {platform.system()}", ""]
    lines.append("  the machine")
    lines.extend(environment.lines(ROOT))
    lines.append("")
    lines.append("  this package")
    lines.extend(one.report for one in found)
    lines.append("")
    if unwell:
        lines.append(f"  {len(unwell)} of {len(found)} checks did not pass")
    else:
        lines.append(f"  {len(found)} checks, nothing to report")
    return lines


def main(
    argv: Sequence[str] = (),
    examine: Callable[[], list[Finding]] = examine,
    say: Callable[[str], None] = print,
) -> int:
    found = examine()
    for line in report(found):
        say(line)
    return 1 if any(not one.ok for one in found) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
