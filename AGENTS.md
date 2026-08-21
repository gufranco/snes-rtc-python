# Working in this repository

This file is for a coding agent. A person reading it will not be harmed, but
[README.md](README.md) is the document written for them.

## What this project is, in one paragraph

A model of the two real-time clocks a Super Nintendo cartridge could carry. They
are parts from different makers with different protocols and different evidence
behind them, and the difference in evidence is the single most important thing to
understand before changing anything here. The Epson RTC-4513 has a manufacturer's
application manual, pinned fact by fact and gated by a test. The Sharp S-RTC has
no public manufacturer document at all, so every claim about it rests on a
recording. Reporting one confidence for both would read as uniform when it is
not.

## The authority ladder

Every factual question is answered by the highest rung that has an answer, and a
lower rung never overrules a higher one.

1. **`conformance/hardware.json`**, which is Seiko Epson's own application manual
   pinned fact by fact with the sentence each figure came from, plus a second
   Epson document that prints the same register table. It decides anything the
   manufacturer printed: register widths, count ranges, what each control bit
   does, what power-on leaves behind, how a session is framed.
2. **The recording**, taken from the implementation pinned in
   `conformance/pinned.json`. It decides what the manual does not: how the
   SPC7110 turns a three-wire serial part into three cartridge addresses, and
   what the counters do with a register outside its documented range.
3. **Nothing else.** An emulator, an FPGA core and a wiki are rung 2 at best and
   rung 3 for a printed fact.

Where the two disagree, the document wins and the disagreement is written down in
`conformance/divergences.json` rather than settled quietly. Twelve entries are
there now. Reading them is the fastest way to understand why this model does not
match the emulator everybody else matches.

**Never resolve a divergence by changing the model to match the recording.** That
is the failure this repository is arranged to prevent. If the manual is wrong,
say why, with the page.

## The Sharp part is unverified and must stay marked so

`hardware.json` carries the Sharp part with `"verified": false` and a block
naming what is asserted, by whom, what was searched for, what was found, and what
would settle it. A test asserts that block is still there and still says so.

The marking `S-RTC` is a Nintendo part designation in the style of S-DSP, S-SMP
and S-PPU, not a Sharp catalogue number. Searching for a Sharp datasheet under
that name will not find one; it has been tried and the date is recorded. If you
find one, that is a significant change and the block comes out.

Do not fill that block in from an emulator. A part quietly given an emulator's
numbers is indistinguishable from a part given a manufacturer's numbers, which is
exactly what makes it dangerous.

## Every gate, in the order to run them

```bash
ruff format --check .                                  # formatting
ruff check .                                           # lint, zero warnings
mypy                                                   # types, strict
pnpm run format:check                                  # every JSON file
for f in $(find snesrtc conformance -name '*.test.py' | sort); do python3 "$f"; done
python3 -m coverage report                             # fails below 100%
python3 conformance/build.py                           # fetch and build the driver
python3 conformance/reference.py                       # the differential
```

Coverage is collected by running each test file under `coverage run -a`, not by a
test runner:

```bash
python3 -m coverage erase
for f in $(find snesrtc conformance -name '*.test.py' | sort); do
  python3 -m coverage run -a "$f"
done
python3 -m coverage report
```

All of it is 100% of statements and branches, and that is enforced rather than
aspired to. A new branch without a test fails the build.

## How the differential reports, and why it looks like it does

It prints one line per part, and the Epson line will say most of the script was
not compared:

```
epson: 200 scripts, 6130 operations compared, 9772 not compared, 0 disagreed
  not compared past epson-digit-fields-narrower-than-registers, reached by 195 scripts
  ...
sharp: 200 scripts, 323500 operations compared, 155 not compared, 0 disagreed
  not compared past stamp-width-platform-dependent, reached by 2 scripts
```

That is the intended shape, not a defect. Each script is compared only up to the
first operation that reaches a declared divergence, because past that point the
recording is answering a question the manual has already answered differently.
Counting those operations as agreements would be reporting the emulator's answer
as though it were the part's; dropping them silently would let the summary claim
a comparison that never happened.

The Sharp part is compared end to end, because for it the recording is the only
authority there is.

**A divergence the runner can witness but nobody wrote down is a failure**, not a
new exclusion. The runner reads the ids out of `divergences.json` on every run.
Add the entry, with what would settle it, or fix the model.

The two clocks are driven by separate scripts. They share one twenty-byte store
here and in the recording, which is a convenience of the harness rather than
anything a board did: no cartridge carried both parts. Letting one write the
other's register file measures the convenience and nothing else.

**Epson scripts are capped at two hundred operations, and that is not a shortcut.**
Comparison stops at the first operation reaching a declared divergence, and
measured over hundreds of scripts that happens after about thirty operations
whether the script is two hundred long or four thousand. Coverage of that part
therefore scales with the number of scripts and not with their length, and the
cap turns the same work into twenty times more scripts. Raising `--length` past
the cap does nothing for the Epson part; raise `--runs` instead. The Sharp part
has no divergences to reach, so its scripts run to whatever length is asked.

**One exclusion is about the recorder, not about a part.** The recording builds
its stamp from the four bytes the cartridge holds and then tests for underflow
against the maximum of the host's `time_t` rather than against the range those
four bytes can hold. Its own comment admits the problem: "sizeof(time_t) is
platform-dependent; though memory::cartrtc needs to be platform-agnostic." A
64-bit build and a 32-bit build of it therefore disagree about every interval
past 2^31 seconds, which a generated script reaches by chance because it may jump
forward twelve years at a time. Both models here test against the range the four
bytes hold, which is the only self-consistent reading, and the operations past
that point are excluded and named rather than allowed to decide.

**Reproducing one failing script:** the runner prints the seed, and `--seed` runs
that one alone without waiting for the ones before it.

```bash
python3 conformance/reference.py --seed 22 --length 4000
```

## Things that will bite you

**A cleared store is not a configured chip.** The manual says every register is
undefined at power-on. Clearing them leaves control register F bit 2 low, which
is twelve-hour notation, and control register D bit 1 low, which switches the
date counters off and turns six registers into RAM. Both are faithful. Tests that
mean a configured chip write `epson.HOURS_24` and `epson.CAL_HW` first, and the
differential does the same to both sides before comparing.

**Six of the thirteen clock registers carry a digit narrower than the register.**
`epson.DIGIT_MASK` holds the widths and the manual's count range column proves
them without reading a bit name: a register that counts to 5 is not using four
bits. Read a digit with `digit()` and write one with `put_digit()`, never with
`store.read` and `store.write` directly, or a program's flag bit becomes part of
the time.

**The mode code is compared as a whole byte, not as a nibble.** On the part that
distinction cannot arise, because the serial interface carries four bits. It is a
property of the SPC7110 wrapper, which no document describes, so the recording
decides and it compares all eight. A write of `0x5C` selects nothing even though
its low nibble is the read mode code. Masking here silently breaks the
differential in a way that takes a while to find.

**HOLD is not a stop.** The manual's first sentence about it says the clock keeps
running. Only STOP and RESET halt it, and `stopped()` reads control register F
alone for that reason. HOLD is bit 0 of CD and RESET is bit 0 of CF, so their
masks are numerically equal and comparing them across registers is meaningless.

**Catch up before changing a stop bit, never after.** On the part the counters run
right up to the instant a stop bit is asserted. A model that writes the bit first
and then asks whether to catch up finds itself already stopped and throws the
elapsed time away. This was a real defect and the ordering in `write_control_f`
is deliberate.

**Run the suite on the oldest Python supported, not only the newest.** Annotations
are evaluated eagerly before 3.14 and lazily from 3.14 on. Every module here
carries `from __future__ import annotations`; if you add one, add the import.

## What the model deliberately does not do

Recorded in `divergences.json` with the reason and what would change it.

- **No interrupt.** Control register E is stored and drives nothing. Its output is
  a pin on the module, and no document says the SPC7110 routes it anywhere a
  program can observe. Modelling one would be inventing a wire.
- **No crystal drift.** The manual gives the tolerance and the temperature
  equation, and both are recorded. They bound a population of modules and a
  temperature the model cannot know, so reporting a single number here would be
  reporting an average as a measurement.
- **No 125 microsecond lockout after a 30-second adjustment.** The bit clears
  itself, which is observable, but the window needs a sub-second time base this
  package does not have. Giving it one changes the public interface.

## Conventions

| Thing | Rule |
|:------|:-----|
| Language | Python only |
| Comments | None in source. Docstrings carry the reasoning, and say why rather than what |
| Test layout | `<module>.test.py` beside the module it covers |
| Test structure | Arrange, blank line, one act, blank line, assert. No section labels |
| Package manager for tooling | pnpm, never npm |
| Commits | Conventional Commits |
| Artifacts | None. This package needs no ROM, no firmware and no cartridge dump |
