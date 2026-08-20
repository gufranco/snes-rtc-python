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

import hashlib
import json
import platform
import sys
from pathlib import Path

from . import models
from .version import VERSION

ROOT = Path(__file__).resolve().parent.parent

PIN = ROOT / "conformance" / "pinned.json"

DRIVER = ROOT / "conformance" / "ref" / "driver"

OLDEST_PYTHON = (3, 12)

MOMENT = 1_000_000_000
"""A moment in the past, told to a clock to see whether it listens to what it is told."""

WITNESS = "s-rtc"
"""The model the two behavioural checks are run against, since both protocols share them."""


class Finding:
    """One thing that was looked at, and what was there."""

    def __init__(self, name, ok, detail, advice=None):
        self.name = name
        self.ok = ok
        self.detail = detail
        self.advice = advice

    @property
    def line(self):
        """The one-line form, which is what a reader scans."""
        return f"  {'ok  ' if self.ok else '   !'}  {self.name}: {self.detail}"

    @property
    def report(self):
        """The same, with what to do about it when there is something to do."""
        if self.ok or not self.advice:
            return self.line
        return f"{self.line}\n         {self.advice}"

    def __repr__(self):
        return f"<Finding {self.name} {'ok' if self.ok else 'not ok'}>"


def _python():
    return Finding(
        "python",
        sys.version_info[:2] >= OLDEST_PYTHON,
        f"{platform.python_version()} on {platform.system()} {platform.machine()}",
        f"this package needs {OLDEST_PYTHON[0]}.{OLDEST_PYTHON[1]} or newer",
    )


def _package():
    return Finding("snesrtc", True, f"version {VERSION}")


def _default_build(name, **options):
    return models.describe(name).build(**options)


def _clock(name, build):
    """Whether that clock builds, saying exactly what stopped it if not."""
    try:
        built = build(name)
    except Exception as trouble:
        return Finding(
            name,
            False,
            f"{type(trouble).__name__}: {trouble}",
            "this is the clock failing to build rather than anything to do with a"
            " reference; the line above is what it said",
        )
    described = models.describe(name)
    where = ", ".join(f"{one:#06x}" for one in described.addresses)
    return Finding(
        name,
        True,
        f"answers {where}, protocol {described.protocol.__module__.rsplit('.', 1)[-1]},"
        f" model {getattr(built, 'model', name)}",
    )


def _time_source(build):
    """That a clock reads the moment it was given rather than this machine's.

    A model reading the host clock cannot be replayed, and a corpus recorded
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


def _foreign(build):
    """That an address the clock does not own reads as an undriven bus.

    A part that answers everywhere is the failure that hides: the console reads
    something plausible from an address nothing drove, and nothing downstream can
    tell it from a real answer.
    """
    try:
        built = build(WITNESS)
        elsewhere = max(models.describe(WITNESS).addresses) + 1
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


def _reference(where):
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


def _driver(where):
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


def examine(build=_default_build, pin=PIN, driver=DRIVER):
    """Everything worth looking at on this machine, in the order a reader wants it."""
    found = [_python(), _package()]
    found.extend(_clock(name, build) for name in sorted(models.MODELS))
    found.append(_time_source(build))
    found.append(_foreign(build))
    found.append(_reference(pin))
    found.append(_driver(driver))
    return found


def report(found):
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


def main(argv=(), examine=examine, say=print):
    found = examine()
    for line in report(found):
        say(line)
    return 1 if any(not one.ok for one in found) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
