# Working in this repository

Read [FAMILY.md](FAMILY.md) first. It is the standard every member of this
family carries, byte for byte, and it decides most questions before they are
asked. What follows is only what is true of this member. [README.md](README.md)
is the document written for a person.

## What this project is, in one paragraph

The two real-time clocks a Super Nintendo cartridge could carry. They are not
revisions of one another: different makers, different publishers' cartridges, and
almost nothing carries across. One has its manufacturer's application manual,
read end to end and pinned fact by fact, and fifteen recorded places where that
manual and the implementation everybody uses disagree. The other has no
manufacturer document known to exist, so everything claimed about it rests on a
recording and the record says so on every page. Both are parts rather than
clocked parts: they tick, and nothing a host does to them is measured in cycles.

## The interface a caller drives

The model is chosen at construction, because the two parts are different parts.

- `Chip(model, store=None, now=...)` builds one over a store it is given or one
  of its own. That is the family's shape for a part, matching `Cpu(model, memory)`
  on the members that run a program.
- `describe(name)` finds a clock by any spelling: case, spaces and separators do
  not matter, and each answers to what people call it. `Chip` goes through it, so
  the same spellings work there. The clock a part reads is injected rather than taken from the
  machine, which is what lets a test hold time still or move it a decade.
- `clock.read(address)` and `clock.write(address, value)` at the addresses that
  part answers: `$2800` and `$2801` for the Sharp part, `$4840` through `$4842`
  for the Epson one through the SPC7110.
- `Store(seed=..., cleared=..., held=...)` is the twenty bytes a cartridge keeps
  on a battery. Nothing starts cleared, and a caller who genuinely means zeroes
  asks for them.

Everything the package raises lives in [`snesrtc/errors.py`](snesrtc/errors.py)
and nowhere else, and that module imports nothing from the package so it can
never be the far end of a cycle. There is one exception, because neither clock
refuses anything a caller does to it: a register written outside its documented
range counts wrongly rather than complaining, which is what the part does.

## The authority ladder

The two parts sit on different rungs, and reporting one number for both would
mislead.

1. **Manufacturer documentation.** Seiko Epson's application manual for the
   RTC-4513: register widths, count ranges, what each control bit does, how a
   session is framed, what power-on leaves behind. Every figure is in
   [`conformance/hardware.json`](conformance/hardware.json) with the sentence it
   was read from, the document's digest and the date it was read.
2. **The artifact itself.** Nothing here rests on one, which is why
   [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) is as long as it is.
3. **A recording from an independent implementation**, pinned by commit. It
   answers what the manual does not: how the SPC7110 turns a three-wire serial
   part into three cartridge addresses, what the counters do outside a documented
   range, and the whole of the Sharp part.
4. **Anything else.** Nothing is cited from below rung three.

Where the manual and the recording disagree, the manual wins and the
disagreement goes into
[`conformance/divergences.json`](conformance/divergences.json) rather than being
settled quietly. There are fifteen entries.

## What is settled and what is not

**Settled: every figure the Epson manual prints.**
[`conformance/hardware.test.py`](conformance/hardware.test.py) holds the model's
constants to the record, so a constant edited without the document is a failing
test rather than a quiet change of claim.

**Settled: agreement with the reference wherever the manual has not already
answered differently.** 329,630 operations compared, no disagreements. Each
script is compared only up to the first operation that reaches a declared
divergence, and the operations past that point are counted apart and named rather
than counted as agreements or dropped in silence.

**Not settled: 14 things**, each in [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) with
what would close it. Eight are places the manual contradicts the recording, two
are places nobody wrote it down, and three are modelling choices that turn on
this package having no sub-second time base. Do not close one by argument.

## The two parts share almost nothing

| | Sharp S-RTC | Epson RTC-4513 |
|:--|:--|:--|
| Manufacturer document | none known to exist | application manual, 1999 |
| Reached at | `$2800` and `$2801` | `$4840` through `$4842`, via the SPC7110 |
| Shape | a fixed sequence wrapped in a marker | an addressed register file of sixteen nibbles |
| Getting at one field | read the whole sequence and count | name its address |
| Weekday | computed from the date when the date is written | a counter of its own, with no meaning attached |
| Year | three digits plus a thousand | two digits with no century printed anywhere |
| Hours | twenty four | twelve or twenty four, chosen by a control bit |
| Control registers | none | three, whose sixteen bits the manual names one by one |
| Clock catches up | when the sequence is read | when the chip is switched **off** |

A change that looks like it applies to both almost certainly applies to one.

## Every gate, in the order to run them

```bash
ruff format --check .
ruff check .
mypy
pnpm run format:check
python3 -m coverage erase
for file in $(find snesrtc conformance -name '*.test.py' | sort); do
  python3 -m coverage run -a "$file"
done
python3 -m coverage report
```

Then the throughput floor, which runs outside the coverage step because a tracer
costs about ten times what the model does:

```bash
python3 -m conformance.speed
```

The differential needs the reference, which is fetched rather than vendored and
needs a C++ compiler. It takes a couple of minutes:

```bash
python3 -m conformance.build
python3 -m conformance.reference
```

Everything under `conformance/` runs as a module. Run as a script, its own
directory goes on the import path and a file there shadows any standard library
module of the same name.

## Conventions that are not negotiable

| Thing | Rule |
|:------|:-----|
| Language | Python only |
| Comments | None in source. Docstrings carry the reasoning |
| Test layout | `<module>.test.py` beside the module it covers |
| Test shape | Arrange, blank line, one act, blank line, assert. No section labels |
| Coverage | 100% statements and branches, enforced |
| Types | `mypy` at strict, plus every optional error class |
| Commits | Conventional Commits, subject under 50 characters |
| The reference | Fetched and pinned by commit, never vendored |
| Documents | Read, quoted and pinned by digest. Never committed: the Epson manual is Seiko Epson's |
| Undefined state | Nothing starts cleared, and the manufacturer says so in as many words |
| Fidelity | Where the part and convenience disagree, the part wins |
| Public API | This and the rest of the family present the same shape where the hardware allows. See [FAMILY.md](FAMILY.md) |

## Layout

```
snesrtc/
  calendar.py    leap years, month lengths, the weekday counter, rollover as the chips do it
  store.py       the twenty bytes the cartridge keeps on a battery
  sharp.py       the Sharp protocol and its state machine
  epson.py       the Epson register file, its named control bits, its two notations
  models.py      which clocks this covers and how to build one
  errors.py      the one refusal this package makes, importing nothing from it
  doctor.py      what is actually on this machine, for an issue report
  version.py     rewritten by the release job and by nothing else
conformance/
  hardware.json     what Epson printed, fact by fact, with the sentence each came from
  hardware.test.py  the gate that holds the model's constants to that file
  divergences.json  every place the manual and the recording part, and what would settle each
  reference.py      the differential runner, and what it refuses to compare
  build.py          fetching the pinned reference and building the driver
  ref/driver.cpp    the driver that wraps the reference implementations
  links.py          the weekly check that every cited address still answers
  speed.py          the throughput floor
```

## Things that will bite you

**Do not resolve a divergence by changing the model to match the recording.** The
manual is a manufacturer describing its own part. If the manual is wrong, say why,
with the page. A new disagreement needs an entry in `divergences.json` naming what
would settle it, or the run fails.

- **A divergence the runner can witness but nobody wrote down fails the run.**
  The runner reads the list of ids out of the record on every script rather than
  trusting a constant in the code, so adding a behaviour without recording it is
  caught rather than absorbed.
- **The Epson comparison stops early on purpose.** 6,130 operations compared
  against 9,772 not compared is not a weak run: past a declared divergence the
  recording is answering a question the manual already answered differently.
  Counting those as agreements would report the emulator's answer as the part's.
- **A generated script is not a hand-written one.** Every script comes from a
  seed, and the runner prints the seed and the operation that disagreed, so a
  failure can be regenerated exactly. Time is scripted too, because the reference
  reads the wall clock and a comparison against a moving target proves nothing.
- **`conformance/ref/` is built, not committed**, and `docs/` is not in the
  repository. A test that reads either and does not say so when it is absent
  passes here and fails everywhere else.
- **The calendar arithmetic is the reference's loop transcribed**, including the
  unsigned underflow, rather than a conversion to a timestamp and back. The two
  agree on every sane date and disagree on the ones a corrupt cartridge holds,
  and the manual declines to say which is right.

## Before calling anything finished

[`FAMILY.md`](FAMILY.md) carries a checklist under "What a new repository has to
have before it is a member". Every line on it was a defect found in one of these
repositories and fixed in all of them, so it is the list of things that have
actually gone wrong here rather than a list of good intentions. Read it before
adding a surface, and read it again before saying a change is done.

A change to `FAMILY.md` is a change to every member. Nothing here can catch it
being made in one of them and forgotten in the others, because a test in this
repository cannot see the others, so the check is a command rather than a suite:

```sh
shared() { sed '/^\*Everything above this line/q' "$1"; }

grep -o 'github\.com/[^/]*/\([a-z0-9-]*\))' FAMILY.md | sed 's|.*/||; s|)||' | sort -u |
while read -r member; do
  other="../$member/FAMILY.md"
  [ -f "$other" ] || { echo "not on this machine: $member"; continue; }
  cmp <(shared FAMILY.md) <(shared "$other") && echo "match: $member"
done
```

The members come from the table at the top of `FAMILY.md` rather than from a glob
over the parent directory. Several repositories beside these carry a copy of this
file because somebody started from one. Those are working notes: they bind
nothing, they are not expected to match, and a sweep that reports them as drifted
invites somebody to edit a file that was never a member.

Two rules from that file are worth repeating because they are the ones skipped
most often:

**A check nobody has seen fail is not known to work.** Drive it, once,
deliberately, against input that should fail it.

**Silence and success produce the same output.** A run that compared nothing exits
zero exactly like one that compared everything, which is why the differential
prints one line per part naming what it compared and what it did not.

## What a change is expected to leave behind

A gate that would have caught the bug. A change to either protocol also runs the
differential, because that is the only thing here that can tell you whether it
still agrees with anything outside this repository, and a change to a constant
the manual settles also updates the record, because the record is what a test
holds the constant to.
