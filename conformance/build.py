"""Fetch the reference sources and build the driver that wraps them.

The reference implementations are a separate work under their own licence, so
they are fetched rather than carried here. Only the driver in `ref/` belongs to
this repository, and it is the only file that is compiled from this side.

The sources are pinned by commit. A build that resolves whatever upstream holds
today is not reproducible, and a change made upstream would turn this repository
red with no commit of its own to explain it.

Usage:
    python3 conformance/build.py [--sources DIR] [--output PATH]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent

DEFINITION = ROOT / "pinned.json"

DEFAULT_SOURCES = str(Path.home() / ".cache" / "snes-rtc-reference")

DEFAULT_OUTPUT = str(ROOT / "ref" / "driver")

COMPILER = "g++"

STANDARD = "c++17"

FETCH_TIMEOUT = 600

COMPILE_TIMEOUT = 600


class Usage(Exception):
    pass


class Options:
    def __init__(
        self,
        sources: str = DEFAULT_SOURCES,
        output: str = DEFAULT_OUTPUT,
        pinned: str | None = None,
        driver: str | None = None,
    ) -> None:
        self.sources = sources
        self.output = output
        self.pinned = pinned
        self.driver = driver


def reference(path: Path | str | None = None) -> dict[str, Any]:
    """The reference this driver is built against, as written down."""
    with Path(path or DEFINITION).open() as handle:
        held: dict[str, Any] = json.load(handle)["reference"]
    return held


def checkout_command(pinned: dict[str, Any], directory: Path | str) -> list[list[str]]:
    """The git steps that bring the sources down, without history or blobs."""
    where = str(directory)
    return [
        ["git", "init", "-q", where],
        ["git", "-C", where, "remote", "add", "origin", pinned["repository"]],
        ["git", "-C", where, "sparse-checkout", "init", "--cone"],
        ["git", "-C", where, "sparse-checkout", "set", *pinned["sparse"]],
        [
            "git",
            "-C",
            where,
            "fetch",
            "-q",
            "--depth=1",
            "--filter=blob:none",
            "origin",
            pinned["commit"],
        ],
        ["git", "-C", where, "checkout", "-q", "FETCH_HEAD"],
    ]


def compile_command(
    sources: Path | str, output: Path | str, driver: Path | str | None = None
) -> list[str]:
    """The one compile, of the one file this repository owns."""
    return [
        COMPILER,
        f"-std={STANDARD}",
        "-O2",
        "-w",
        f"-I{sources}",
        "-o",
        str(output),
        str(driver or ROOT / "ref" / "driver.cpp"),
    ]


def _git_environment() -> dict[str, str]:
    return {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


def fetch(pinned: dict[str, Any], directory: Path | str) -> Path:
    at = Path(directory)
    at.mkdir(parents=True, exist_ok=True)
    for step in checkout_command(pinned, at):
        done = subprocess.run(
            step,
            capture_output=True,
            text=True,
            check=False,
            timeout=FETCH_TIMEOUT,
            env=_git_environment(),
        )
        if done.returncode:
            raise Usage(f"fetching the reference failed at {' '.join(step)}\n{done.stderr}")
    return at / str(pinned["path"])


def options(argv: Sequence[str]) -> Options:
    chosen = Options()
    rest = list(argv)
    while rest:
        item = rest.pop(0)
        if item not in ("--sources", "--output", "--pinned", "--driver-source"):
            raise Usage(f"unknown option {item}")
        if not rest:
            raise Usage(f"{item} needs a value")
        value = rest.pop(0)
        if item == "--sources":
            chosen.sources = value
        elif item == "--output":
            chosen.output = value
        elif item == "--pinned":
            chosen.pinned = value
        else:
            chosen.driver = value
    return chosen


def run(argv: Sequence[str]) -> int:
    chosen = options(argv)
    sources = Path(chosen.sources)
    pinned = reference(chosen.pinned)
    if not sources.exists():
        sources = fetch(pinned, sources)
    Path(chosen.output).parent.mkdir(parents=True, exist_ok=True)

    done = subprocess.run(
        compile_command(sources, Path(chosen.output), chosen.driver),
        capture_output=True,
        text=True,
        check=False,
        timeout=COMPILE_TIMEOUT,
    )
    if done.returncode:
        print(done.stderr.strip()[:2000])
        return 1
    print(f"built {chosen.output} against {pinned['commit'][:12]}")
    return 0


def main(argv: Sequence[str]) -> int:
    try:
        return run(argv)
    except Usage as error:
        print(error)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
