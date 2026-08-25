# Open questions

What this project does not know for certain, and what it would take to find out.

Everything here is a place where being faithful to the silicon is still a claim
rather than a measurement. The list is long for one of the two parts and short
for the other, and the reason is the whole shape of this repository: the Epson
part has its manufacturer's application manual, so there is a document to
disagree with, and the Sharp part has none, so there is nothing to disagree with
and correspondingly nothing to be sure of.

The settled surface is 329,630 operations compared against an independent
implementation with no disagreements, and every figure the Epson manual prints
held against the model's own constants. What follows is the residue, and each
entry is also in [`conformance/divergences.json`](conformance/divergences.json)
with its status and severity, so a program can read what a person reads here.

## Why a recording cannot close these

The recording is a second implementation, not a measurement. Where it and the
manual disagree, the manual is a manufacturer describing its own part and the
recording is somebody's reading of the behaviour one cartridge needed. The manual
wins, and the disagreement is written down rather than settled quietly. That is
eight of the entries below.

Where the manual is silent, neither source is above the other, and the answer is
unknown rather than whichever is more convenient.

## What would settle almost all of them

A logic analyser on an RTC-4513, which is a part that was sold by the thousand
and is still findable. Most entries below name a capture of a few operations.

Two need something else. The Sharp part needs a Sharp data book entry, a
decapsulation, or a capture of the one cartridge that carries it. And three of
the Epson entries need a decision rather than a measurement: they turn on this
package having no sub-second time base, and giving it one would change the public
interface.

## Where the manual and the recording contradict each other

The manual wins in all of these. They are listed so a reader can see how far the
implementation everybody uses is from the document, and so nobody closes one by
changing the model to match the recording.

### Whether bit 1 of control register D adds a second.

**The document says.** It is CAL/HW, which selects how much of the counter chain
runs. It does not add time.

Source: Seiko Epson, *Application Manual: Real Time Clock Module RTC-4513*.

**What the recording does.** Treats a write of that bit as a request to add one
second, by backdating the recorded moment so the clock gains it on the next
catch-up.

**What this project follows.** The document.

**What would settle or reopen it.** A logic capture while CAL/HW is toggled,
showing whether the second counter moves. A read of the shipped cartridge program
would bound how much the answer matters, by establishing whether it ever writes
the bit at all.

### What HOLD does to the time that passes while it is set.

**The document says.** HOLD freezes only the visible one-second digit. The
counters behind it keep running, and releasing HOLD compensates the increment
that was suppressed.

**What the recording does.** Treats HOLD as a stop condition and discards every
second that passes while it is set.

**What this project follows.** The document.

**What would settle or reopen it.** A capture with HOLD asserted across a minute
boundary and then released.

### Whether six of the thirteen clock registers carry a digit narrower than the register.

**The document says.** They do. The count range column proves it without reading
a bit name: a register whose count stops at 5 is not holding a four-bit digit.
The spare bits are an oscillator flag, a read flag, an AM/PM flag, and free RAM
the manual explicitly invites a program to use.

**What the recording does.** Stores and reads all four bits of every register as
the digit, so a flag bit or a free-RAM bit written by a program is read back as
part of the time.

**What this project follows.** The document.

**What would settle or reopen it.** A capture reading a register back after
writing a free-RAM bit, showing whether the counter chain was disturbed.

### Whether the interrupt flag can be written.

**The document says.** It cannot. A write instruction for IRQ-F is not executed.

**What the recording does.** Stores all four bits of a write to register 13,
IRQ-F included.

**What this project follows.** The document.

**What would settle or reopen it.** A capture writing register 13 with bit 2 set
and reading it straight back.

### Whether the test bit clears itself.

**The document says.** TEST clears when CE goes low, and a RESET forces it to
zero.

**What the recording does.** Stores the bit and never clears it.

**What this project follows.** The document.

**What would settle or reopen it.** A capture setting TEST, dropping CE, and
reading the control register back.

### Whether the part runs in twelve-hour notation when the bit says so.

**The document says.** It does, whenever CF bit 2 is clear, with PM/AM in the
tens-of-hours register and the twenty bit held at zero.

**What the recording does.** Runs twenty-four hour notation unconditionally and
ignores the bit.

**What this project follows.** The document.

**What would settle or reopen it.** A capture toggling that bit with a known time
loaded, read back immediately.

### Whether the read and oscillation-stop flags exist.

**The document says.** They do. The read flag lets a program tell whether the
reading it just took straddled a tick; the oscillation flag records an
interruption and is how a program detects a flat battery.

**What the recording does.** Models neither. Those bits are whatever the digit
write left behind.

**What this project follows.** The document.

**What would settle or reopen it.** A capture holding CE high across a second
boundary and reading the tens-of-minutes register.

### What a write does while the part is in read mode.

**The document says.** Nothing directly. In read mode the data pin is an output
driven by the chip, so the manual never contemplates the host writing to it.

**What the recording does.** Treats every write after the mode code as another
index selection, so the address is re-chosen on each write rather than walking
forward.

**What this project follows.** The document, in the sense of the nearest
statement it does make.

**What would settle or reopen it.** A capture driving the data pin as an input
while the chip is in read mode, which is a bus contention a real board would
avoid, or a read of the shipped cartridge program establishing whether it ever
does this.

## Where nobody wrote it down

### Which century a two-digit year belongs to.

**The document says.** Nothing. The year is two BCD digits, and leap-year
compensation is stated for the Gregorian calendar with no range of years named.

**What this project follows.** The recording, which reads 90 and above as
nineteen hundred and below 90 as two thousand, giving a window of 1990 to 2089.

**Why.** A two-digit year has to be resolved somehow to answer a question about
leap years, and there is no document to resolve it from. The window is inherited
and named as inherited.

**What would settle or reopen it.** A statement from Epson naming the window,
which the manual does not make, or a read of the shipped cartridge program
showing which century it assumes.

### Everything about the Sharp part.

**The document says.** Nothing. No manufacturer document for it is known to
exist. The marking `S-RTC` is a Nintendo part designation in the style of
`S-DSP`, `S-SMP` and `S-PPU`, not a Sharp catalogue number. It was searched for;
the date and the search are in
[`conformance/hardware.json`](conformance/hardware.json) under
`"verified": false`.

**What this project follows.** The recording, which defines the whole protocol:
the marker, the thirteen-byte sequence, the command set, the derived weekday and
the three-digit year.

**Why.** There is nothing above it. What matters is that the record says so and a
test asserts it still does, because filling that block in from an emulator would
make a guess indistinguishable from a fact.

**What would settle or reopen it.** A Sharp data book entry for the part, a
decapsulation naming a catalogue number under the Nintendo marking, or a capture
of the cartridge bus while the one shipped title reads and writes the clock.

## Where the question is a modelling choice, not a fact

### Where the clock catches up, when a model has no continuous time base.

**The document says.** Nothing, and it could not. A real part counts continuously
off its own crystal and has nothing to catch up, so the manual describes no event
at which the time is recomputed because there is no such event.

**What this project follows.** The recording, which recomputes the stored time
when the chip is disabled rather than when it is enabled. A program that opens
the chip and reads immediately therefore gets the second the previous session
left.

**What would settle or reopen it.** Giving the model a continuous time base
driven by the caller, at which point the seam disappears rather than moving.

### The 125 microsecond lockout after a thirty-second adjustment.

**The document says.** For 125 microseconds the adjust bit reads back as 1 and
the clock registers cannot be written, after which the bit clears itself.

**What this project follows.** The document for the part that is observable
without a sub-second time base: the bit clears itself. The window during which
the registers cannot be written is not modelled.

**What would settle or reopen it.** A decision to give the model a sub-second
time base, at which point the window is directly implementable from the quoted
figure. It is a choice about this package's interface rather than a question
about the part.

### A stamp width that belongs to the recorder rather than to either part.

**The document says.** Nothing, and it could not. Neither part holds a timestamp
at all. The four stored bytes both models use to remember when they were last
read exist only because a model learns the time from a host rather than counting
it.

**What the recording does.** Tests that stamp for underflow against the maximum
of the host's `time_t` rather than against the range four bytes can hold, so a
64-bit build and a 32-bit build disagree about any interval past two billion
seconds.

**What this project follows.** Neither. An answer that turns on the width of a
type on the build machine is a property of the recorder, so it is excluded from
the comparison and named rather than allowed to decide.

**What would settle or reopen it.** Nothing available. There is no hardware
answer, because there is no stamp on the hardware.

## What is not in question

So the boundary is visible rather than implied:

- **Every figure the Epson manual prints.** Register widths, count ranges, what
  each control bit does, how a session is framed, what power-on leaves behind.
  Each is in [`conformance/hardware.json`](conformance/hardware.json) with the
  sentence it was read from, and
  [`conformance/hardware.test.py`](conformance/hardware.test.py) holds the
  model's constants to it, so a constant edited without the document is a failing
  test rather than a quiet change of claim.
- **That the two parts agree with the reference wherever the manual has not
  already answered differently.** 329,630 operations compared, no disagreements,
  with every comparison stopping at the first operation that reaches a declared
  divergence rather than counting the recording's answer as the part's.
- **That a divergence nobody wrote down fails the run.** The runner reads the
  list of ids out of the record on every script rather than trusting a constant.
- **That nothing starts cleared.** Epson prints "At power-on, all registers and
  the STD.P output are undefined", which is the one place the family convention
  and a manufacturer agree in as many words.

## What is deliberately not modelled

Absent rather than unknown, and absent on purpose:

- **A clock in the family's sense.** These parts tick and are still not driven by
  a budget of cycles. There is no instruction to step through, so none of the
  clocked interface appears here rather than appearing as a stub.
- **The interrupt output.** Control register E selects one of four periods and
  drives a pin. No document says the SPC7110 routes that pin anywhere a program
  can observe, so the register is stored and drives nothing. Modelling an
  interrupt that reaches nothing would be inventing a wire.
- **Crystal drift.** The manual gives the figures, and they are recorded. They
  are not simulated, because a tolerance bounds a population of modules rather
  than describing the one in a cartridge, and it depends on a temperature the
  model cannot know.
