<div align="center">

<h1>SNES Cartridge Clocks</h1>

<strong>The two real-time clocks a Super Nintendo cartridge could carry, held to the chips' own reference implementations.</strong>

<br>
<br>

[![CI](https://github.com/gufranco/snes-rtc-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/snes-rtc-python/actions/workflows/ci.yml)
[![Conformance](https://img.shields.io/badge/conformance-1%2C600%2C000%20operations-brightgreen)](#conformance)
[![Coverage](https://img.shields.io/badge/coverage-100%25%20statement%20%2B%20branch-brightgreen)](#tests)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

<p align="center">
  <a href="#quick-start">Quick start</a> &nbsp;|&nbsp;
  <a href="#conformance">Conformance</a> &nbsp;|&nbsp;
  <a href="#the-two-chips">The two chips</a> &nbsp;|&nbsp;
  <a href="#what-the-reference-caught">What the reference caught</a> &nbsp;|&nbsp;
  <a href="https://github.com/gufranco/snes-rtc-python/issues">Issues</a>
</p>

**2** chips · **1,600,000** operations against the reference, **0** disagreements · **158** tests · **100%** statement and branch coverage

```python
from snesrtc import describe

clock = describe("s-rtc").build()
clock.read(0x2800)
```

## Quick start

### Prerequisites

| Tool | Version | Install |
|:-----|:--------|:--------|
| Python | 3.12 or newer | [python.org](https://www.python.org/downloads/) |
| A C++ compiler | any recent | only for running the conformance comparison |

### Install

```bash
pip install git+https://github.com/gufranco/snes-rtc-python.git
```

### Read the clock a cartridge would read

```python
from snesrtc import describe

clock = describe("s-rtc").build()

clock.write(0x2801, 0x0D)
print(f"{clock.read(0x2800):02X}")
for _ in range(13):
    print(f"{clock.read(0x2800):02X}", end=" ")
```

The first read answers `0F`, the marker that says the sequence is starting. The
thirteen that follow are the time, one decimal digit per byte, seconds first.

### Set it

```python
clock.write(0x2801, 0x0E)
clock.write(0x2801, 0x00)
for digit in (0, 0, 0, 3, 2, 1, 8, 1, 8, 6, 9, 9):
    clock.write(0x2801, digit)
```

Half past twelve on the eighteenth of August 1996. Twelve digits are written and
the thirteenth, the weekday, is worked out by the chip.

## The two chips

They are not revisions of one another. They are parts from different makers, on
cartridges from different publishers, and almost nothing carries across.

| | Sharp S-RTC | Epson RTC-4513 |
|:--|:--|:--|
| Reached at | `$2800` and `$2801` | `$4840` through `$4842`, via the SPC7110 |
| Shape | a fixed sequence wrapped in a marker | an addressed register file |
| Getting at one field | read the whole sequence and count | name its index |
| Weekday | computed from the date when the date is written | written like any other field |
| Year | three digits plus a thousand, so 1000 to 1999 | two digits read as 1990 to 2089 |
| Registers that do work when written | none | two, which add a second, round the minute, or stop the counter |
| Clock catches up | when the sequence is read | when the chip is switched **off** |

```python
from snesrtc import describe

sharp = describe("s-rtc").build()
epson = describe("rtc-4513").build()
```

Names are matched however they are written. Case, spaces and separators do not
matter, and each part answers to what people call it: `srtc`, `sharp`,
`rtc4513`, `epson`, `spc7110`.

## Conformance

Neither chip has a published per-instruction suite, so the oracle is the
implementation every emulator already agrees with. A script of reads, writes and
clock changes is generated from a seed, run through a driver compiled around
those sources, and replayed through the model here. The two transcripts are
compared line for line.

| Measure | Value |
|:--------|:------|
| Scripts | 400 |
| Operations per script | 4,000 |
| Operations compared | 1,600,000 |
| Disagreements | 0 |
| Reference | [snes9x](https://github.com/snes9xgit/snes9x), pinned by commit |

Run it yourself:

```bash
python conformance/build.py
python conformance/reference.py
```

```
400 scripts, 1600000 operations, 0 disagreed
```

The script is generated rather than written by hand for the same reason a suite
beats a handful of examples: a hand-written script exercises the paths its author
thought of. A generated one wanders into sequences nobody would write on purpose,
which is where the corners are. Time is scripted too, because the reference reads
the wall clock and a comparison against a moving target proves nothing.

The reference sources are fetched at build time and never vendored here. Only the
driver in [`conformance/ref/`](conformance/ref/) belongs to this repository.

## What the reference caught

Every one of these was a defect in this package. None would have been found by
reading a datasheet, because in each case the datasheet says nothing.

**The month underflows rather than wrapping.** The chip subtracts one from the
month before it starts counting, in unsigned arithmetic. A cartridge holding a
month of zero does not roll back to December: it underflows to four billion, and
the month length is read from that number's remainder, landing on a thirty day
month. Wrapping to December is the sensible reading and is wrong.

**A field above its range is not reduced, it is cleared.** A minute of one
hundred does not become forty on the next carry. It becomes zero, and the extra
hour is lost. Corrupt state stays corrupt in a particular way.

**The Epson clock catches up when it is switched off.** Not when it is switched
on, which is what you would write. A session therefore reads the time as the
previous session left it, and a game that opens the chip and reads immediately
gets a stale second.

**Asking for one more second does not add one.** It backdates the recorded moment
by a second, so the clock gains that second on the next catch-up rather than
immediately. Adding it directly lands two seconds away from what the chip does.

**The two stop flags are tested separately, not as alternatives.** A write that
sets both catches the clock up twice. The second catch-up finds nothing and
changes nothing, which is why it stays invisible until a generated script sets
both at once.

The first two were found by a script that wrote a nonsense month. The rest were
found by scripts that used the control registers in combinations no game would.

## Nothing starts cleared

A battery-backed cartridge holds what it held, and one fresh from the factory
holds whatever the silicon powered up with. The store reflects that: a byte that
has never been written derives its value from its position, so it is arbitrary,
never zero, and the same every time it is asked.

```python
from snesrtc import Store

held = Store(seed=1)
held.read(0)  # some byte, not zero, stable across reads

Store(cleared=True)  # a caller who genuinely means zeroes says so
Store(held=saved)  # the bytes a saved cartridge had
```

Two stores built with different seeds hold different rubbish, so a test can prove
a program does not depend on what it never wrote.

## Layout

| File | Holds |
|:-----|:------|
| [`snesrtc/calendar.py`](snesrtc/calendar.py) | Leap years, month lengths, the weekday counter, and rollover as the chips perform it |
| [`snesrtc/store.py`](snesrtc/store.py) | The twenty bytes the cartridge keeps on a battery |
| [`snesrtc/sharp.py`](snesrtc/sharp.py) | The Sharp protocol and its state machine |
| [`snesrtc/epson.py`](snesrtc/epson.py) | The Epson protocol, its register file and its control registers |
| [`snesrtc/models.py`](snesrtc/models.py) | Which chips this covers and how to build one |
| [`conformance/reference.py`](conformance/reference.py) | The differential runner |
| [`conformance/build.py`](conformance/build.py) | Fetches the pinned reference and builds the driver |
| [`conformance/ref/driver.cpp`](conformance/ref/driver.cpp) | The driver that wraps the reference implementations |

## For contributors and reviewers

### Running the tests

Each module has its test file beside it, named after it.

```bash
python -m coverage erase
for file in $(find snesrtc conformance -name '*.test.py' | sort); do
  python -m coverage run -a "$file"
done
python -m coverage report
```

Coverage is a gate, not a report: the build fails below 100% of statements and
branches.

### Reproducing a conformance failure

Every script comes from a seed, and the runner prints the seed of a script that
disagreed. That script can be regenerated exactly:

```python
import reference

script = reference.generate(seed=3, length=4000)
print(reference.render(script))
```

Feed that to the driver on standard input to see the reference's side alone.

### Project conventions

| Convention | Source |
|:-----------|:-------|
| Commit format | [Conventional Commits](https://www.conventionalcommits.org/) |
| Format and lint | [ruff](https://docs.astral.sh/ruff/), configured in [pyproject.toml](pyproject.toml) |
| Releases | [semantic-release](https://semantic-release.gitbook.io/), from the commit history |
| Test naming | A sentence stating the behaviour, not the function name |

### Non-obvious decisions

- The calendar arithmetic is the reference's loop transcribed, including the
  unsigned underflow, rather than a conversion to a timestamp and back. The two
  agree on every sane date and disagree on the ones a corrupt cartridge holds.
- There is a bulk path that divides out minutes and hours instead of counting
  them, used only once every counter is inside its range. It is a shortcut for
  the loop beside it, and the oracle is what keeps the two honest.
- The clock a chip reads is injected rather than taken from the machine, so a
  test can hold time still or move it a decade.
- Neither chip's crystal drift is modelled. The reference does not model it
  either, and a number invented here would be unverified.

## When something is wrong

```bash
python3 -m snesrtc.doctor
```

It looks at this machine and prints what is actually there, and every line is
something it looked at just now rather than something that ought to be true. A
check that fails says what it saw. A check that itself throws is reported as what
it threw rather than taking the report down with it. Paste all of it into an
issue.

## Contributing

Measurements first. [CONTRIBUTING.md](CONTRIBUTING.md) has the gates a change is
expected to pass, [SECURITY.md](SECURITY.md) says what belongs in a private
report, and the [Code of Conduct](CODE_OF_CONDUCT.md) applies wherever this
project is discussed.

Never attach a copyrighted file, and never link to somewhere one can be
downloaded. A digest identifies a file without carrying it.

## Citing this

[CITATION.cff](CITATION.cff) is kept in step with the released version by the
same script that stamps the package, so the version it names is the version that
shipped.

## Licence

[MIT](LICENSE).

The reference implementations are a separate work under their own licence,
fetched at build time and never redistributed here.
