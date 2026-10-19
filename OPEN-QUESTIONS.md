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
the Epson entries are modelling choices. A chip built with
`rate=epson.CRYSTAL_HZ` counts cycles of the part's crystal, which settles two of
them for that chip; the whole-second chip the recording is compared in keeps
them, and they are listed so nobody mistakes its seams for the part's.

## Where the manual and the recording contradict each other

The manual wins in all of these. They are listed so a reader can see how far the
implementation everybody uses is from the document, and so nobody closes one by
changing the model to match the recording.

### Whether bit 1 of control register D adds a second.

**The document says.** It is CAL/HW, which selects how much of the counter chain
runs. It does not add time.

Source: Seiko Epson, _Application Manual: Real Time Clock Module RTC-4513_.

**What the recording does.** Treats a write of that bit as a request to add one
second, by backdating the recorded moment so the clock gains it on the next
catch-up.

**What this project follows.** The document.

**The cartridge writes it.** That half is settled, and it was the half that
bounded how much the answer matters. Read out of the shipped program's own code
on 2026-08-25, without running any of it, the routine that initialises the clock
runs this sequence:

| Write                                      |  Value | Bits                  |
| :----------------------------------------- | -----: | :-------------------- |
| CD                                         | `0x01` | HOLD                  |
| CE                                         | `0x0f` | none named            |
| CF                                         | `0x07` | RESET, STOP, HOURS_24 |
| the thirteen clock registers, from a table |        |                       |
| CF                                         | `0x04` | HOURS_24              |
| CD                                         | `0x06` | CAL_HW, IRQ_F         |

So the last thing the routine does is set CAL/HW. Under the recording's reading
that gains a second every time a clock is initialised in the one title carrying
this part; under the manual's it selects the counter chain. The two readings part
company in a shipped game rather than only in principle.

The reading is in [`conformance/cartridge.json`](conformance/cartridge.json) with
the cartridge's four digests and none of its bytes, and
[`conformance/cartridge.py`](conformance/cartridge.py) reproduces it from a copy
you own.

**What would settle or reopen it.** A logic capture while CAL/HW is toggled,
showing whether the second counter moves. What the cartridge could answer, it
has: the bit is written. What the silicon does with it needs the capture.

### What HOLD does to the time that passes while it is set.

**The document says.** HOLD freezes only the visible one-second digit. The
counters behind it keep running, and releasing HOLD compensates the increment
that was suppressed.

**What the recording does.** Treats HOLD as a stop condition and discards every
second that passes while it is set.

**What this project follows.** The document.

**What the cartridge does with it.** Asserts it across a register load and
releases it afterwards, which is the usage the manual describes. The clock
initialisation opens with `CD = 0x01`, which is HOLD on its own, writes the
thirteen clock registers, and closes with `CD = 0x06`, which drops HOLD in the
same write that raises CAL/HW. That is a program using HOLD as a shutter over the
visible digit, not as a way to stop the clock.

It does not settle the question. A routine that is about to overwrite every clock
register does not care whether the seconds behind the shutter kept running, so
the sequence is consistent with either reading. What it does rule out is the idea
that no shipped program uses the bit.

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

### Whether the interrupt flag can be written, and what raises it.

**The document says.** It cannot be written. A write instruction for IRQ-F is
not executed. The increment t1 and t0 select raises it, a read of CD clears it,
and while MASK is set it cannot be 1. In fixed-period mode it falls again after
7.8 ms.

**What the recording does.** Stores all four bits of a write to register 13,
IRQ-F included, never raises the bit itself, and treats MASK as plain storage.

**What this project follows.** The document. In interrupt cycle mode the flag
holds until CD is read. In fixed-period mode a chip counting crystal cycles holds
it for 256 cycles, 7.8 ms, after each increment; a chip counting whole seconds
cannot hold it that briefly and never raises it there.

**What would settle or reopen it.** A capture writing register 13 with bit 2 set
and reading it straight back, and one reading CD before and after a second ticks
in interrupt cycle mode, then again with MASK set.

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

**What this project follows.** The document. The read flag rises when a second
increments while CE is high and clears when CE falls. The oscillator flag rises
when the caller interrupts the oscillation with `interrupt_oscillation()`, and
the time until `restore_oscillation()` is lost. What supply voltage interrupts a
real oscillator is not printed, and the model has no supply.

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

**The shipped program never does it.** Read out of its own code on 2026-10-19 by
[`conformance/cartridge.py`](conformance/cartridge.py), each of the program's
five read sessions writes the data port once, to choose the index, and closes
the chip without writing it again. Two further openings have no close within
reach of the scan; no `jsr`, `jmp`, `jsl` or `jml` in the image reaches either.
So the question matters to no software that shipped for this part.

**What would settle or reopen it.** A capture driving the data pin as an input
while the chip is in read mode, which is a bus contention a real board would
avoid.

## Where nobody wrote it down

### Which century a two-digit year belongs to.

**The document says.** No window. The year is two BCD digits, and leap-year
compensation is stated for the Gregorian calendar with no range of years named.
Its examples do place two years: the register table reads a 1-year digit of 2 as
the 2 of 1992, and the leap-year example sets February 29, 1993. So 92 and 93
belong to the nineteen hundreds in the manufacturer's own reading.

**What the shipped program does.** Reads 95 and above as nineteen hundred and
below 95 as two thousand, a window of 1995 to 2094. Read out of its own code on
2026-10-19 by [`conformance/cartridge.py`](conformance/cartridge.py): one routine
adds 100 to a year below 95, the one beside it adds 1900, and the clock
initialisation loads 1995-12-22. That puts 92 and 93 in the two thousands, which
the manual's examples do not.

**What this project follows.** The recording's window, 1990 to 2089, which reads
90 and above as nineteen hundred and agrees with both of the manual's examples.
The program's window disagrees with the manual on 90 to 94, and the manual is
the higher rung. Every year the two windows share gets the same leap rule, so a
program reading the digits back sees no difference either way.

**What would settle or reopen it.** For the program, nothing more: it is read.
For the part, a capture that rolls a year 99 into 00 across February and shows
whether the 29th follows, which is the one place a window could reach the
silicon. The part holds two digits and no century to keep a window in.

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

**What the shipped program sends it.** Read out of Daikaijuu Monogatari II's own
code on 2026-10-19 by
[`conformance/sharp_cartridge.py`](conformance/sharp_cartridge.py), which records
it in [`conformance/sharp_cartridge.json`](conformance/sharp_cartridge.json). The
program keeps its clock traffic as a table of steps holding nine scripts. Three of
them agree with the recording: it reads the marker `0x0F`, thirteen digits and the
marker again; it writes `0x0E`, `0x00`, the twelve digits from seconds to the
hundreds of years and `0x0D`, leaving out the weekday the recording derives; and
it sends `0x0E` and `0x04` alone, which the recording reads as clearing the
clock. The other six send commands the recording ignores: `0x01`, `0x02` and
`0x03`, each followed by the eight digits from hours to the hundreds of years,
and `0x05`, `0x06` and `0x07` alone. The program's half of the protocol is now
read rather than inferred; the part's answer to those six is not.

**What would settle or reopen it.** A Sharp data book entry for the part, a
decapsulation naming a catalogue number under the Nintendo marking, or a capture
of the cartridge bus while the program sends one of the six commands the
recording ignores.

## Where the question is a modelling choice, not a fact

### Where the clock catches up, when a model has no continuous time base.

**The document says.** Nothing, and it could not. A real part counts continuously
off its own crystal and has nothing to catch up, so the manual describes no event
at which the time is recomputed because there is no such event.

**What this project follows.** The recording, which recomputes the stored time
when the chip is disabled rather than when it is enabled. A program that opens
the chip and reads immediately therefore gets the second the previous session
left.

**What a crystal-rate chip does.** Built with `rate=epson.CRYSTAL_HZ` and a time
source counting crystal cycles, the chip catches up at every access, so it shows
the current second whenever it is read and the seam is gone. The whole-second
chip keeps the recording's placement because that is the shape the recording is
compared in.

**What would settle or reopen it.** Nothing more for the crystal-rate chip. The
whole-second placement is a property of the comparison, not of the part.

### The 125 microsecond lockout after a thirty-second adjustment.

**The document says.** For 125 microseconds the adjust bit reads back as 1 and
the clock registers cannot be written, after which the bit clears itself.

**What this project follows.** The document. A chip counting crystal cycles holds
the bit at 1 and refuses writes to S1 through W for 4 cycles after the write,
lands the adjustment at the second the window ends in, and cancels it if RESET
comes first.
125 microseconds is 4.096 cycles, and the model rounds to 4. A chip counting
whole seconds has no window: the bit clears and the adjustment lands at once.

**What would settle or reopen it.** A capture timing how many crystal cycles the
bit reads 1, which says whether the silicon rounds to 4 or to 5.

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
  with a field the model takes from the manual excused alone, and every other
  declared divergence stopping the comparison at the first operation that
  reaches it rather than counting the recording's answer as the part's.
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
- **The interrupt reaching the console.** Control register E selects one of four
  periods and drives the STD.P pin, and the model drives it: `std_p` reads low or
  open. No document says the SPC7110 routes that pin anywhere a program can
  observe, so nothing outside the model reads it. Connecting it to the console
  would be inventing a wire.
- **Crystal drift.** The manual gives the figures, and they are recorded. They
  are not simulated, because a tolerance bounds a population of modules rather
  than describing the one in a cartridge, and it depends on a temperature the
  model cannot know.
