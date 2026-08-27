"""Look at this machine and say what is actually here, so a report can be believed.

What goes wrong with this package is rarely a defect in it. It is a Python too
old to run it, a reference driver that was never built so the differential check
quietly did nothing, or a clock reading this machine's wall time when it should
be reading a moment somebody chose. The last one is the worst, because every
disagreement about it turns into an argument about when it was run.

So this looks, and prints what it found in a form that can be pasted into an
issue as it stands.

Two rules shape it, and they are the whole point.

Nothing is hidden. A check that fails says what it saw, and a check that itself
throws is caught and reported as what it threw, named by its type. Swallowing
either would leave a report that says everything is fine on a machine where
something is not, which is worse than no report.

Nothing is inferred. Every line is something looked at on this machine just now,
including a clock actually told a moment and asked what it holds.
"""

from __future__ import annotations

import hashlib
import json
import platform
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol, override


def _version(where: Path | None = None) -> str:
    """The package version, read out of the file beside this one.

    Read rather than imported. Importing it would go through the package, and a
    package that will not import is one of the things this exists to report.
    """
    found = re.search(
        r"""VERSION\s*[:=][^"']*["']([^"']+)["']""",
        (where or Path(__file__).resolve().parent / "version.py").read_text(),
    )
    return found.group(1) if found else "unknown"


ROOT = Path(__file__).resolve().parent.parent


VERSION = _version()


if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from snesrtc import models  # noqa: E402

PIN = ROOT / "conformance" / "pinned.json"

DRIVER = ROOT / "conformance" / "ref" / "driver"

OLDEST_PYTHON = (3, 12)

MOMENT = 1_000_000_000
"""A moment in the past, told to a clock to see whether it listens to what it is told."""

WITNESS = "s-rtc"
"""The model the two behavioural checks are run against, since both protocols share them."""


class Ticking(Protocol):
    """A thing that can be asked what time it thinks it is."""

    def now(self) -> int: ...


class Addressed(Protocol):
    """A thing that can be asked what is at an address."""

    def read(self, address: int) -> int: ...


class Resettable(Protocol):
    """A thing the console's reset line can reach."""

    def reset(self) -> object: ...


Builder = Callable[..., models.Built]
"""What examine is given: something that builds a real clock by name.

Each check below asks for less than this, naming only the one method it calls.
The doctor's whole job is to report what is actually on this machine, which
includes a clock that does not work, so a check that demanded the concrete class
could only be tested against a working one. Narrowing per check keeps the checks
testable against a deliberately broken clock without letting any of them reach
for a method it does not use.
"""


class Finding:
    """One thing that was looked at, and what was there."""

    def __init__(self, name: str, ok: bool, detail: str, advice: str | None = None) -> None:
        self.name = name
        self.ok = ok
        self.detail = detail
        self.advice = advice

    @property
    def line(self) -> str:
        """The one-line form, which is what a reader scans."""
        return f"  {'ok  ' if self.ok else '   !'}  {self.name}: {self.detail}"

    @property
    def report(self) -> str:
        """The same, with what to do about it when there is something to do."""
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
    """Whether that clock builds and resets, saying what stopped it if not.

    The reset is driven rather than described. It is the console's line reaching
    a battery-backed part, so it puts the command sequence back to its start and
    leaves everything stored alone, and a report that never pulled it has said
    nothing about the one event a cartridge causes on every boot.
    """
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


def _time_source(build: Callable[..., Ticking]) -> Finding:
    """That a clock reads the moment it was given rather than this machine's.

    A model reading the host clock cannot be replayed, and a recording taken
    against it stops agreeing the moment the day changes. The source is a
    constructor argument here, and this is where a machine says whether that is
    still true of the code it has.
    """
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


def _foreign(build: Callable[..., Addressed]) -> Finding:
    """That an address the clock does not own reads as an undriven bus.

    A part that answers everywhere is the failure that hides: the console reads
    something plausible from an address nothing drove, and nothing downstream can
    tell it from a real answer.
    """
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
    """Which implementation this is held to, and at which commit.

    Two people comparing against two commits of the same reference will disagree
    and both be right. The digest of the file that pins it is what ends that.
    """
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
    """Whether the reference is built, since its absence is silent otherwise.

    The differential check builds somebody else's implementation and asks it the
    same sequences. That build is not needed to use this package, and a machine
    without it is the normal case rather than a broken one. It is reported so
    that nobody reads a run that skipped as a run that passed.
    """
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
    """Everything worth looking at on this machine, in the order a reader wants it."""
    found = [_python(), _package()]
    found.extend(_clock(name, build) for name in sorted(models.MODELS))
    found.append(_time_source(build))
    found.append(_foreign(build))
    found.append(_reference(pin))
    found.append(_driver(driver))
    return found


def report(found: Sequence[Finding]) -> list[str]:
    """The lines a person pastes into an issue."""
    unwell = [one for one in found if not one.ok]
    lines = [f"snesrtc {VERSION} on {platform.python_version()}, {platform.system()}", ""]
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
