# SNES Cartridge Clocks

The two real-time clocks a Super Nintendo cartridge could carry. One is held to its manufacturer's application manual. The other has no manual, and this says so on every page.

[![CI](https://github.com/gufranco/snes-rtc-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/snes-rtc-python/actions/workflows/ci.yml)

**2** clocks, **329,630** operations compared against the reference, **0** disagreements, **15** places the manual and that reference part, each one written down, **776** tests, **100%** statement and branch coverage, no dependencies

```python
from snesrtc import Chip

sharp = Chip("s-rtc")
epson = Chip("rtc-4513")

print(sharp.model, epson.model)
```

```
s-rtc rtc-4513
```

## Install

```bash
pip install git+https://github.com/gufranco/snes-rtc-python.git
```

Python 3.12 or newer. Nothing else at runtime.

A C++ compiler is needed only to build the reference the differential compares
against, and only if you want to run that comparison yourself.

## The interface

The model is chosen at construction, because the two parts are different parts
rather than revisions of one another.

| Call | Does | Returns |
|:--|:--|:--|
| `MODELS` | Every clock this package covers, by the name it goes by | a mapping |
| `model.build(store=None, now=...)` | Builds one, over a store it is given or one of its own | a `Chip` |
| `clock.read(address)` | Reads at one of the addresses that part answers | `int` |
| `clock.write(address, value)` | Writes at one of them | nothing |
| `clock.reset()` | What the part does when the console resets it | the `Chip` |
| `Store(seed=..., cleared=..., held=...)` | The twenty bytes a cartridge keeps on a battery | a `Store` |

| Attribute | Is |
|:--|:--|
| `clock.model` | Which part this is, by its canonical name |
| `clock.store` | The twenty bytes it counts in |
| `model.addresses` | Where that part answers |
| `model.aliases` | Every other spelling that reaches it |

Names are matched however they are written. Case, spaces and separators do not
matter, and each part answers to what people call it: `srtc`, `sharp`,
`rtc4513`, `epson`, `spc7110`.

```python
from snesrtc import MODELS

print(sorted(MODELS["s-rtc"].aliases))
print(sorted(MODELS["rtc-4513"].aliases))
```

```
['sharp', 'sharprtc', 'srtc']
['epson', 'epsonrtc', 'rtc4513', 'spc7110', 'spc7110rtc']
```

There is no clock in the family's sense. A real-time clock ticks and is still not
driven by a budget of cycles, so nothing here has a `step` or a cycle count. Time
arrives through the callable a clock is built with, which is what lets a test
hold it still or move it a decade.

### Read the clock a cartridge would read

```python
from snesrtc import Chip

clock = Chip("s-rtc")
clock.write(0x2801, 0x0D)

print(f"{clock.read(0x2800):02X}")
print(" ".join(f"{clock.read(0x2800):02X}" for _ in range(13)))
```

The first read answers `0F`, the marker that says the sequence is starting. The
thirteen that follow are the time, one decimal digit per byte, seconds first.

### Set it

```python
from snesrtc import Chip

clock = Chip("s-rtc")

clock.write(0x2801, 0x0E)
clock.write(0x2801, 0x00)
for digit in (0, 0, 0, 3, 2, 1, 8, 1, 8, 6, 9, 9):
    clock.write(0x2801, digit)

print(clock.model)
```

```
s-rtc
```

Half past twelve on the eighteenth of August 1996. Twelve digits are written and
the thirteenth, the weekday, is worked out by the chip.

## Where each answer comes from

The two clocks in this package are not backed by the same kind of evidence, and
the difference is large enough that reporting one number for both would be
misleading.

| Rung | Source | Settles |
|:-----|:-------|:--------|
| 1 | [Seiko Epson, *Application Manual: Real Time Clock Module RTC-4513*](conformance/hardware.json) | Anything Epson printed about the RTC-4513: register widths, count ranges, what each control bit does, how a session is framed, what power-on leaves behind |
| 2 | A recording from an independent implementation, pinned by commit | What the manual does not: how the SPC7110 turns a three-wire serial part into three cartridge addresses, what the counters do outside a documented range, and the whole of the Sharp part |
| 3 | Nothing else | Nothing |

Every figure on rung 1 lives in [`conformance/hardware.json`](conformance/hardware.json)
with the sentence it was read from, the document's digest, and the date it was
read. [`conformance/hardware.test.py`](conformance/hardware.test.py) checks the
model's constants against it, so a constant edited without the document is a
failing test rather than a quiet change of claim.

Where the manual and the recording disagree, the manual wins and the
disagreement is written down in
[`conformance/divergences.json`](conformance/divergences.json) rather than
settled quietly. There are fifteen entries. Each names what the document says,
what the recording does, which one this package follows, and what evidence would
close the question.

### The Sharp part has no datasheet

The marking `S-RTC` is a Nintendo part designation in the same style as `S-DSP`,
`S-SMP` and `S-PPU`, not a Sharp catalogue number, and no manufacturer document
for it is known to exist publicly. It was searched for; the date and the search
are recorded in `hardware.json` under `"verified": false`, along with the three
things that would settle it.

So every claim this package makes about the Sharp clock rests on a recording, and
a test asserts that the file still says so. Filling that block in from an
emulator would make a guess indistinguishable from a fact, which is the failure
the whole arrangement exists to prevent.

## What the manual caught

Every one of these was wrong in this package before Epson's own application
manual was read end to end, and every one of them is still wrong in the
implementation this package used to be calibrated against.

**Six of the thirteen clock registers carry a digit narrower than the register.**
The manual's own count range column proves it without reading a single bit name:
a register whose count stops at 5 is not holding a four-bit digit, and the
tens-of-months register, which stops at 1, is holding one bit. The spare bits are
an oscillator flag, a read flag, an AM/PM flag, and free RAM the manual
explicitly invites a program to use. A model that treats every register as a
four-bit digit reads a program's stored flag back as part of the date.

**HOLD does not stop the clock.** Its first documented sentence says the opposite:
"The clock continues to run, and the first incrementation after HOLD was set to
'1' is compensated for when the hold condition is released (+1 second)." The
manual's own procedure for setting the clock uses HOLD for exactly that and warns
the write must finish within one second or the seconds are lost. Treating it as a
stop throws away every second a program spends holding.

**There is no bit that adds a second.** Bit 1 of control register D is CAL/HW,
which selects how much of the counter chain runs and turns six registers into
RAM when it is clear. The only documented software adjustment is the 30-second
adjust on bit 3, which this package already had right and the manual confirms
word for word.

**Twelve-hour notation exists and is the power-on state.** Control register F bit
2 selects it, and the manual says every register is undefined at power-on, so a
cartridge whose program never ran the power-on procedure is running in twelve-hour
notation with its date counters switched off. A model that hardcodes twenty-four
hours cannot reproduce that cartridge.

**The interrupt flag cannot be written.** "A write instruction for the IRQ-F bit
is not executed." It is set by the increment logic and cleared by reading the
register it lives in.

**The test bit clears when the chip is deselected**, and a reset forces it down.
Two separate paragraphs say so, and the bit powers up undefined, so it is
reachable without any program setting it.

**A stop bit takes effect after the counters are brought current, not before.**
This one was a defect introduced while implementing the others, and it is worth
naming because it is the kind that hides: writing the stop bit first and then
asking whether to catch up finds the clock already stopped and silently discards
the elapsed time.

Two of the findings this README used to list have been withdrawn. An
"add a second" function on control register D bit 1 and a double catch-up from
testing two stop flags separately were both behaviours of the emulator, not of
the part, and both are recorded in `divergences.json` with the quote that
displaced them. The claim that "none of these would have been found by reading a
datasheet, because in each case the datasheet says nothing" was false; nobody had
read the datasheet.

## What the recording caught

These remain. The manual is silent on all of them, which is what makes a
recording the right authority rather than a convenience.

**The month underflows rather than wrapping.** The chip subtracts one from the
month before it starts counting, in unsigned arithmetic. A cartridge holding a
month of zero does not roll back to December: it underflows to four billion, and
the month length is read from that number's remainder, landing on a thirty day
month. The manual says only "Do not set impossible values", so it does not
contradict this and does not confirm it.

**A field above its range is not reduced, it is cleared.** A minute of one hundred
does not become forty on the next carry. It becomes zero, and the extra hour is
lost.

**The Epson clock catches up when it is switched off.** Not when it is switched
on, which is what you would write. A session therefore reads the time as the
previous session left it. This is an artefact of modelling a continuously running
counter from a reading taken at intervals, and a real part has no such seam at
all.

**The mode code is compared as a whole byte.** On the part that distinction cannot
arise, because the serial interface carries four bits and there is nothing above
them. It is a property of the SPC7110 wrapper, which no document describes.

## The two chips

They are not revisions of one another. They are parts from different makers, on
cartridges from different publishers, and almost nothing carries across.

| | Sharp S-RTC | Epson RTC-4513 |
|:--|:--|:--|
| Manufacturer document | none known to exist | application manual, 1999 |
| Reached at | `$2800` and `$2801` | `$4840` through `$4842`, via the SPC7110 |
| Shape | a fixed sequence wrapped in a marker | an addressed register file of sixteen nibbles |
| Getting at one field | read the whole sequence and count | name its address |
| Weekday | computed from the date when the date is written | a counter of its own, 0 to 6, with no meaning attached |
| Year | three digits plus a thousand, so 1000 to 1999 | two digits with no century printed anywhere |
| Hours | twenty four | twelve or twenty four, chosen by a control bit |
| Control registers | none | three, whose sixteen bits the manual names one by one |
| Clock catches up | when the sequence is read | when the chip is switched **off** |

```python
from snesrtc import Chip

sharp = Chip("s-rtc")
epson = Chip("rtc-4513")
```

Names are matched however they are written. Case, spaces and separators do not
matter, and each part answers to what people call it: `srtc`, `sharp`,
`rtc4513`, `epson`, `spc7110`.

### A cleared register file is not a configured chip

Epson: "At power-on, all registers and the STD.P output are undefined." Zeroing
them leaves the notation bit low, which is twelve-hour notation, and the range
bit low, which switches the date counters off. Both are faithful, and both are
what the manual's power-on procedure exists to escape.

```python
from snesrtc import Store, epson

held = Store(cleared=True)
held.write(epson.CF, epson.HOURS_24)
held.write(epson.CD, epson.CAL_HW)
clock = epson.Chip(held)
```

## Nothing starts cleared

A battery-backed cartridge holds what it held, and one fresh from the factory
holds whatever the silicon powered up with. This is the one place where the
family convention and the manufacturer agree in as many words: Epson prints "At
power-on, all registers and the STD.P output are undefined."

```python
from snesrtc import Store

one = Store(seed=1)
two = Store(seed=2)
saved = bytes(Store(seed=7).bytes)

print(one.read(0) == two.read(0))
print(Store(cleared=True).read(0))
print(len(Store(held=saved).bytes))
```

```
False
0
20
```

A seeded store holds rubbish that is stable across reads and different for a
different seed, so a test can prove a program does not depend on what it never
wrote. A caller who genuinely means zeroes asks for them, and a caller restoring
a cartridge hands over the bytes it had.

## What is deliberately not modelled

Each is recorded in `divergences.json` with the reason and what would change it.

**No interrupt.** Control register E selects one of four periods and drives the
STD.P pin. No document says the SPC7110 routes that pin anywhere a Super Nintendo
program can observe, so the register is stored and drives nothing. Modelling an
interrupt that reaches nothing would be inventing a wire.

**No crystal drift.** The manual gives the figures: 0 plus or minus 25 ppm at 25
degrees C, a secondary temperature coefficient of -0.035 ppm per degree C
squared, and "At 11.574 ppm, the daily clock error is about one second per day."
They are recorded and not simulated, because a tolerance bounds a population of
modules rather than describing the one in a cartridge, and it depends on a
temperature the model cannot know. An earlier version of this README said no
number existed. One does, and it is now written down.

**No 125 microsecond lockout after a 30-second adjustment.** The bit clears
itself, which is observable and modelled. The window during which the clock
registers cannot be written needs a sub-second time base this package does not
have, and adding one would change the public interface.

## Is it right

The differential drives each part with scripts generated from a seed, runs them
through a driver compiled around the pinned reference sources, and compares the
two transcripts line for line.

It reports one line per part, and the two lines look very different on purpose:

```
epson: 200 scripts, 6130 operations compared, 9772 not compared, 0 disagreed
  not compared past epson-digit-fields-narrower-than-registers, reached by 195 scripts
  not compared past epson-oscillation-flag-cannot-be-originated, reached by 134 scripts
  ...
sharp: 200 scripts, 323500 operations compared, 155 not compared, 0 disagreed
  not compared past stamp-width-platform-dependent, reached by 2 scripts
```

Each script is compared only up to the first operation that reaches a declared
divergence. Past that point the recording is answering a question the manual has
already answered differently, so counting those operations as agreements would be
reporting the emulator's answer as though it were the part's, and dropping them
silently would let the summary claim a comparison that never happened. They are
counted apart and named instead.

The Sharp part is compared very nearly end to end, because for it the recording
is the only authority there is. The one thing excluded from it is not about the
part at all: the recording tests its stamp for underflow against the maximum of
the host's `time_t` rather than against the range the cartridge's four stored
bytes can hold, so a 64-bit build and a 32-bit build of it disagree about any
interval past two billion seconds. An answer that turns on the width of a type on
the build machine is a property of the recorder, and it is excluded and named
rather than allowed to decide.

Epson scripts are capped at two hundred operations because a longer one buys
nothing. Comparison stops at the first operation reaching a declared divergence,
and measured over hundreds of scripts that happens after about thirty operations
whether the script is two hundred long or four thousand. Coverage of that part
scales with the number of scripts, not with their length.

A divergence the runner can witness but nobody wrote down fails the run. The
runner reads the list of ids out of `divergences.json` on every script rather
than trusting a constant in the code.

The two clocks are driven by separate scripts. They share one twenty-byte store
here and in the recording, which is a convenience of the harness rather than
anything a board did, since no cartridge carried both parts.

Run it yourself:

```bash
python3 -m conformance.build
python3 -m conformance.reference
```

The script is generated rather than written by hand for the same reason a suite
beats a handful of examples: a hand-written script exercises the paths its author
thought of. A generated one wanders into sequences nobody would write on purpose,
which is where the corners are. Time is scripted too, because the reference reads
the wall clock and a comparison against a moving target proves nothing.

The reference sources are fetched at build time and never vendored here. Only the
driver in [`conformance/ref/`](conformance/ref/) belongs to this repository.

### When something is wrong

```bash
python3 snesrtc/doctor.py
```

It looks at this machine and prints what is actually there, and every line is
something it looked at just now rather than something that ought to be true. A
check that fails says what it saw. A check that itself throws is reported as what
it threw rather than taking the report down with it. Paste all of it into an
issue.

## Working on it

### Running the tests

`python3 snesrtc/doctor.py` says what is actually on this machine: both clocks, a write pushed through and read back, and whether the reference this repository cannot carry is built. It is run as a file rather than with `-m` so that it still runs when the package itself will not import, which is the case it exists for. Its report is what an issue asks for, because a report is only as good as what it says about the machine that produced it.

Each module has its test file beside it, named after it.

```bash
python -m coverage erase
for file in $(find snesrtc conformance -name '*.test.py' | sort); do
  python -m coverage run -a "$file"
done
python -m coverage report
```

Coverage is a gate, not a report: the build fails below 100% of statements and
branches. Types are a gate too, `mypy` in strict mode with every optional error
class the checker offers.

### Reproducing a conformance failure

Every script comes from a seed, and the runner prints the seed and the part of a
script that disagreed. That script can be regenerated exactly:

```bash
python3 -m conformance.reference --seed 22 --length 4000
```

Or render it and feed it to the driver on standard input, to see the reference's
side alone:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from conformance import reference

script = reference.generate(seed=22, length=4000, part="sharp")
print(reference.render(script)[:40])
```

### Changing something the manual settles

Do not resolve a divergence by changing the model to match the recording. If the
manual is wrong, say why, with the page. If a new disagreement appears, it needs
an entry in `divergences.json` naming what would settle it, or it fails the run.

### Project conventions

| Convention | Source |
|:-----------|:-------|
| Commit format | [Conventional Commits](https://www.conventionalcommits.org/) |
| Format and lint | [ruff](https://docs.astral.sh/ruff/), configured in [pyproject.toml](pyproject.toml) |
| Types | [mypy](https://mypy-lang.org/) strict, configured in [pyproject.toml](pyproject.toml) |
| Releases | [semantic-release](https://semantic-release.gitbook.io/), from the commit history |
| Test naming | A sentence stating the behaviour, not the function name |
| Comments | None in source. Docstrings carry the reasoning |

### Non-obvious decisions

- The calendar arithmetic is the reference's loop transcribed, including the
  unsigned underflow, rather than a conversion to a timestamp and back. The two
  agree on every sane date and disagree on the ones a corrupt cartridge holds,
  and the manual declines to say which is right.
- There is a bulk path that divides out minutes and hours instead of counting
  them, used only once every counter is inside its range. It is a shortcut for
  the loop beside it, and the differential is what keeps the two honest.
- The clock a chip reads is injected rather than taken from the machine, so a
  test can hold time still or move it a decade.
- The century a two-digit Epson year belongs to is a convention inherited from
  the recording. The manual prints two BCD digits and names no century, and the
  window decides only which years are leap years.

### Layout

| File | Holds |
|:-----|:------|
| [`snesrtc/calendar.py`](snesrtc/calendar.py) | Leap years, month lengths, the weekday counter, and rollover as the chips perform it |
| [`snesrtc/store.py`](snesrtc/store.py) | The twenty bytes the cartridge keeps on a battery |
| [`snesrtc/sharp.py`](snesrtc/sharp.py) | The Sharp protocol and its state machine |
| [`snesrtc/epson.py`](snesrtc/epson.py) | The Epson register file, its named control bits, and its two notations |
| [`snesrtc/models.py`](snesrtc/models.py) | Which chips this covers and how to build one |
| [`conformance/hardware.json`](conformance/hardware.json) | What Epson printed, fact by fact, with the sentence each came from |
| [`conformance/divergences.json`](conformance/divergences.json) | Every place the manual and the recording disagree, and what would settle each |
| [`conformance/hardware.test.py`](conformance/hardware.test.py) | The gate that holds the model's constants to that file |
| [`conformance/reference.py`](conformance/reference.py) | The differential runner, and what it refuses to compare |
| [`conformance/build.py`](conformance/build.py) | Fetches the pinned reference and builds the driver |
| [`conformance/ref/driver.cpp`](conformance/ref/driver.cpp) | The driver that wraps the reference implementations |

### Contributing

Measurements first. [CONTRIBUTING.md](CONTRIBUTING.md) has the gates a change is
expected to pass, [SECURITY.md](SECURITY.md) says what belongs in a private
report, and the [Code of Conduct](CODE_OF_CONDUCT.md) applies wherever this
project is discussed.

Never attach a copyrighted file, and never link to somewhere one can be
downloaded. A digest identifies a file without carrying it.

## References

This repository carries no documents, no cartridges and no reference sources.

| Document | Publisher | Pinned by | Redistributable |
|:---------|:----------|:----------|:----------------|
| *Application Manual: Real Time Clock Module RTC-4513* | Seiko Epson, 1999 | Digest and read-date in [`conformance/hardware.json`](conformance/hardware.json) | No |
| *RTC-4513 catalogue extract* | Seiko Epson, undated | Digest and read-date in [`conformance/hardware.json`](conformance/hardware.json) | No |

Fetching them is a command rather than an exercise. [`conformance/documents.json`](conformance/documents.json) carries the full digest, the byte count and a fetchable address for each, and [`conformance/documents.py`](conformance/documents.py) brings both down into `docs/`, which git ignores, and refuses anything whose digest does not match.

```bash
python3 -m conformance.documents          # fetch and verify every digest
python3 -m conformance.documents --check  # verify what is already here
```

The application manual is a fax with no text layer at all, so a citation into it is followed by rendering the page and reading it.

**No manufacturer document for the Sharp part is known to exist.** The marking
`S-RTC` is a Nintendo part designation in the same style as `S-DSP`, `S-SMP` and
`S-PPU`, not a Sharp catalogue number. It was searched for; the date and the
search are recorded in `hardware.json` under `"verified": false`, along with the
three things that would settle it. A test asserts the file still says so, because
filling that block in from an emulator would make a guess indistinguishable from
a fact.

| Source | Used for |
|:-------|:---------|
| [snes9xgit/snes9x](https://github.com/snes9xgit/snes9x) | The reference both parts are compared against, pinned by commit in [`conformance/pinned.json`](conformance/pinned.json). Fetched at build time, never vendored, and a second implementation rather than a measurement |

## Citing this

[CITATION.cff](CITATION.cff) is kept in step with the released version by the
same script that stamps the package, so the version it names is the version that
shipped.

## License

[MIT](LICENSE).

The reference implementations are a separate work under their own licence,
fetched at build time and never redistributed here. The Epson application manual
is Seiko Epson's; this repository records what it says, with digests so a reader
can confirm they are holding the same document, and does not carry it.
