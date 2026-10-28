# SNES Cartridge Clocks

The Sharp S-RTC and the Epson RTC-4513, the two real-time clocks a Super Nintendo cartridge could carry, in Python, the Epson part held to Seiko Epson's application manual and both held to a pinned build of snes9x.

English | [日本語](README.ja.md) | [简体中文](README.zh-Hans.md) | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/snes-rtc-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/snes-rtc-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/snes-rtc-python)](https://github.com/gufranco/snes-rtc-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**2** clocks, **329,630** operations compared against the reference, **0** disagreements, **15** places where the manual and that reference differ, each one written down, **1,160** tests, **100%** statement and branch coverage, no dependencies

```python
from snesrtc import Chip, Store

seconds = [1_000_000_000]
clock = Chip("s-rtc", Store(cleared=True), now=lambda: seconds[0]).reset()

clock.write(0x2801, 0x0E)
clock.write(0x2801, 0x00)
for digit in (0, 0, 0, 3, 2, 1, 8, 1, 8, 6, 9, 9):
    clock.write(0x2801, digit)
clock.write(0x2801, 0x0D)

seconds[0] += 95
print(" ".join(f"{clock.read(0x2800):X}" for _ in range(15)))
```

```
F 5 3 1 3 2 1 8 1 8 6 9 9 0 F
```

The example builds the Sharp clock over a zeroed store and hands it a time source it controls. Command `0E` followed by `00` opens a write, and twelve digits set 12:30:00 on 18 August 1996, seconds first. The chip works out the thirteenth digit, the weekday, which is 0 for that Sunday. Command `0D` starts a read. Moving the time source on by 95 seconds and reading fifteen times returns the `F` marker, 12:31:35 on the same date, the weekday, and the marker again.

## Install

| Requirement             | Version                                                       |
| :---------------------- | :------------------------------------------------------------ |
| Python                  | 3.12 or newer                                                 |
| git                     | Any, to clone                                                 |
| A C++17 compiler, `g++` | Only to build the reference the differential compares against |

```bash
git clone https://github.com/gufranco/snes-rtc-python.git
cd snes-rtc-python
python3 snesrtc/doctor.py
```

The package imports nothing outside the standard library. `pip install git+https://github.com/gufranco/snes-rtc-python.git` installs it without the conformance suite and adds a `snesrtc-doctor` command.

The doctor checks the machine and the checkout, drives both clocks, and ends with one line. It exits 0 when every check of the package passes and 1 when one does not. Paste its whole output into any bug report.

```
  8 checks, nothing to report
```

Releases follow [Semantic Versioning](https://semver.org/) and are cut from the commit history by semantic-release. Every release is tagged and listed on the [releases page](https://github.com/gufranco/snes-rtc-python/releases).

## The interface

`snesrtc.Chip(model, store=None, now=..., open_bus=0x00, rate=epson.CRYSTAL_HZ)` builds one clock. `model` is required. `store` is a `Store`, and the clock builds a seeded one when it is left out. `now` is a callable returning the time, and the clock keeps the low 32 bits of the whole seconds in it. The Sharp part reads `now` as whole seconds, and its default reads `time.time()`. `open_bus` is accepted by the Sharp part only and is what it answers at an address it does not own. The Epson part answers `0x00` there. `rate` is accepted by the Epson part only: how many counts of `now` make one second, and its default `now` reads the machine's clock in those counts. The default, `epson.CRYSTAL_HZ`, counts cycles of the part's 32,768 Hz crystal the way the manual describes: the part catches up at every access, raises IRQ-F on the 1/64 s period, holds IRQ-F and STD.P low for 256 cycles, 7.8 ms, in fixed-period mode, and holds 30ADJ. for 4 cycles, 125 microseconds rounded to whole cycles. `rate=epson.WHOLE_SECONDS` counts whole seconds and catches up when the chip is deselected, the shape the recording is compared in; it has no 1/64 s period, no fixed-period pulse and no lockout.

| Model      | Aliases                                                 | Addresses                                    | Year                                    | Hours                             |
| :--------- | :------------------------------------------------------ | :------------------------------------------- | :-------------------------------------- | :-------------------------------- |
| `s-rtc`    | `srtc`, `sharp`, `sharprtc`                             | `$2800` data, `$2801` control                | Three digits plus 1000, so 1000 to 1999 | 24                                |
| `rtc-4513` | `rtc4513`, `epson`, `epsonrtc`, `spc7110`, `spc7110rtc` | `$4840` enable, `$4841` data, `$4842` status | Two digits, read as 1990 to 2089        | 12 or 24, chosen by a control bit |

A name matches whatever its case, and spaces, hyphens and underscores are ignored. A missing or unknown name raises `UnknownModelError`, whose message lists the names accepted.

```python
import snesrtc
from snesrtc import MODELS

for name, model in MODELS.items():
    print(name, model.aliases, [f"{at:#06x}" for at in model.addresses])

print(snesrtc.Chip("Sharp RTC").model, snesrtc.Chip("SPC_7110").model)

for asked in (None, "s-dsp"):
    try:
        snesrtc.Chip(asked)
    except snesrtc.UnknownModelError as error:
        print(error)
```

```
s-rtc ('srtc', 'sharp', 'sharprtc') ['0x2800', '0x2801']
rtc-4513 ('rtc4513', 'epson', 'epsonrtc', 'spc7110', 'spc7110rtc') ['0x4840', '0x4841', '0x4842']
s-rtc rtc-4513
no model was named, and this package will not choose one for you. Name one of: rtc-4513, s-rtc
s-dsp is not a clock this package covers; it has rtc-4513, s-rtc
```

### Calls both clocks take

| Call                    | Effect                                                                                                                                                                                                                                                  |
| :---------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `read(address)`         | One byte from the cartridge bus                                                                                                                                                                                                                         |
| `write(address, value)` | One byte to the cartridge bus. Returns nothing                                                                                                                                                                                                          |
| `reset()`               | What the console's reset does. The Sharp part goes back to the start of a read and brings its time current. The Epson part is deselected, back in write mode at register 0, with enable and status cleared. The store is not touched. Returns the clock |

| Attribute | Meaning                         |
| :-------- | :------------------------------ |
| `model`   | The canonical model name        |
| `store`   | The `Store` the clock counts in |
| `now`     | The time source                 |

### Module contents

| Name                                                       | Content                                                                                                                                                                                                                                                                                               |
| :--------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `snesrtc.MODELS`                                           | The two `Model` records, keyed by canonical name                                                                                                                                                                                                                                                      |
| `snesrtc.Model`                                            | A record with `name`, `summary`, `addresses`, `protocol` and `aliases`, and `build(store=None, **options)`, which `Chip` calls                                                                                                                                                                        |
| `snesrtc.models.lookup(name)`                              | The `Model` for any spelling. Raises `UnknownModelError`                                                                                                                                                                                                                                              |
| `snesrtc.Store(seed=UNSET_SEED, cleared=False, held=None)` | The 20 bytes the cartridge keeps on a battery. See [Nothing starts cleared](#nothing-starts-cleared)                                                                                                                                                                                                  |
| `snesrtc.Built`                                            | The type `Chip` returns, `epson.Chip` or `sharp.Chip`                                                                                                                                                                                                                                                 |
| `snesrtc.UnknownModelError`                                | The one error the package raises, for a missing or unknown model name. It lives in `snesrtc.errors`                                                                                                                                                                                                   |
| `snesrtc.__version__`                                      | The installed version                                                                                                                                                                                                                                                                                 |
| `snesrtc.sharp`, `snesrtc.epson`                           | Each part's `Chip` class, addresses, command codes and register constants                                                                                                                                                                                                                             |
| `snesrtc.store`                                            | `Store` and its constants `SIZE`, `STAMP_AT`, `STAMP_BYTES` and `UNSET_SEED`                                                                                                                                                                                                                          |
| `snesrtc.calendar`                                         | The calendar arithmetic both parts share                                                                                                                                                                                                                                                              |
| `snesrtc.crystal`                                          | `CRYSTAL_HZ`, the pin levels `LOW` and `OPEN`, the printed `LOW_SECONDS` and `LOCKOUT_SECONDS`, `FAST_HZ`, `WHOLE_SECONDS`, `NANOSECONDS`, `whole_ticks(rate, seconds)`, `machine_clock(rate)`, the machine's time in counts of `rate`, and `Crystal(rate)`, the sub-second state an Epson chip keeps |

### The Sharp S-RTC

A write to `$2801` drives a state machine. Only the low four bits of a value are read.

| Write to `$2801`           | Effect                                                                                                  |
| :------------------------- | :------------------------------------------------------------------------------------------------------ |
| `0D`                       | Start a read. The next read of `$2800` brings the time current and answers the `0F` marker              |
| `0E`                       | Wait for a command                                                                                      |
| `0E`, then `00`            | Start a write. The next twelve writes are the digits, and the chip computes the thirteenth, the weekday |
| `0E`, then `04`            | Clear all thirteen digits to 0                                                                          |
| `0E`, then any other value | Stop. Writes are ignored until the next `0D` or `0E`                                                    |
| `0F`                       | Ignored                                                                                                 |

A read sequence is the `0F` marker, thirteen digits, then the marker again, after which it starts over. Outside a read, `$2800` answers `0x00`.

| Store byte | Digit                                                       |
| :--------- | :---------------------------------------------------------- |
| 0, 1       | Seconds, ones then tens                                     |
| 2, 3       | Minutes                                                     |
| 4, 5       | Hours                                                       |
| 6, 7       | Day                                                         |
| 8          | Month, one digit holding 1 to 12                            |
| 9, 10, 11  | Year minus 1000, ones then tens then hundreds               |
| 12         | Weekday, 0 for Sunday, counted from Monday 1 January 1900   |
| 16 to 19   | The time the store was last brought current, low byte first |

| Attribute or call                       | Meaning                                                               |
| :-------------------------------------- | :-------------------------------------------------------------------- |
| `mode`                                  | `"read"`, `"command"`, `"write"` or `"ready"`                         |
| `index`                                 | The next digit in the sequence, -1 before the marker                  |
| `open_bus`                              | What an address the part does not own reads as                        |
| `read_moment()`, `store_moment(moment)` | The thirteen digits as a `calendar.Moment`, and back                  |
| `elapsed()`                             | Seconds since the stamp in bytes 16 to 19. A gap over 2^31 reads as 0 |
| `update()`                              | Advance the digits by `elapsed()` and restamp                         |
| `command(value)`, `accept(value)`       | The two halves of `write` after the command byte                      |

`snesrtc.sharp` carries `DATA`, `CONTROL`, `MARKER`, `LAST_INDEX`, `COMMAND_READ`, `COMMAND_BEGIN`, `COMMAND_NOTHING`, `COMMAND_WRITE`, `COMMAND_CLEAR`, `YEAR_BASE` and `STAMP_LIMIT`, and the four `mode` values as `READING`, `COMMAND`, `WRITING` and `READY`.

### The Epson RTC-4513

The SPC7110 turns the part's three-wire serial interface into three cartridge addresses. A program talks to it in sessions.

| Step     | Bus access                          | Effect                                                                 |
| :------- | :---------------------------------- | :--------------------------------------------------------------------- |
| Select   | Write `$4840` with bit 0 set        | Status becomes `0x80`. The part waits for a mode                       |
| Mode     | Write `$4841` with `0x03` or `0x0C` | Write mode or read mode. Any other value is ignored                    |
| Register | Write `$4841` with 0 to 15          | The register the next access starts at                                 |
| Data     | Write or read `$4841`               | One nibble. The register index then moves on by one and wraps after 15 |
| Deselect | Write `$4840` with bit 0 clear      | Brings the counters current, clears the read flags and clears TEST     |
| Status   | Read `$4842`                        | `0x80` after any access, then `0x00` until the next one                |

Reading `$4840` returns the last value written there. Reading CD clears IRQ-F.

| Register | Index | D3     | D2       | D1       | D0    | Count range |
| :------- | :---- | :----- | :------- | :------- | :---- | :---------- |
| `S1`     | 0     | s8     | s4       | s2       | s1    | 0 to 9      |
| `S10`    | 1     | fo     | s40      | s20      | s10   | 0 to 5      |
| `MI1`    | 2     | mi8    | mi4      | mi2      | mi1   | 0 to 9      |
| `MI10`   | 3     | fr     | mi40     | mi20     | mi10  | 0 to 5      |
| `H1`     | 4     | h8     | h4       | h2       | h1    | 0 to 9      |
| `H10`    | 5     | fr     | PM/AM    | h20      | h10   | 0 to 2      |
| `D1`     | 6     | d8     | d4       | d2       | d1    | 0 to 9      |
| `D10`    | 7     | fr     | free RAM | d20      | d10   | 0 to 3      |
| `MO1`    | 8     | mo8    | mo4      | mo2      | mo1   | 0 to 9      |
| `MO10`   | 9     | fr     | free RAM | free RAM | mo10  | 0 to 1      |
| `Y1`     | 10    | y8     | y4       | y2       | y1    | 0 to 9      |
| `Y10`    | 11    | y80    | y40      | y20      | y10   | 0 to 9      |
| `W`      | 12    | fr     | w4       | w2       | w1    | 0 to 6      |
| `CD`     | 13    | 30ADJ. | IRQ-F    | CAL/HW   | HOLD  |             |
| `CE`     | 14    | t1     | t0       | INT/STND | MASK  |             |
| `CF`     | 15    | TEST   | 24/12    | STOP     | RESET |             |

`snesrtc.epson` names each register by its index, `S1` through `CF`, and each control bit by its mask: `HOLD`, `CAL_HW`, `IRQ_F` and `ADJUST` in CD, `RESET`, `STOP`, `HOURS_24` and `TEST` in CF, and `MASK` and `INT_STND` in CE. It also carries `ENABLE`, `DATA`, `STATUS`, `WRITE_MODE`, `READ_MODE`, `READY`, `REGISTERS`, `DIGIT_MASK`, `OSC_FLAG`, `READ_FLAG`, `READ_FLAG_AT`, `CALENDAR_READ_FLAG_AT`, `PM`, `H20`, `STOPPED`, `NIBBLE`, `HALF_MINUTE`, `MINUTE`, `HOUR`, `WHOLE_SECONDS_PER_PERIOD`, `PERIOD_SHIFT`, `PERIOD_BITS`, `NOON`, `YEAR_PIVOT`, `STAMP_LIMIT`, `STAMP_MASK`, `CLOCK_REGISTERS`, `FAST_PERIOD`, `CRYSTAL_HZ` and `WHOLE_SECONDS`, and the five `state` values as `INACTIVE`, `MODE_SELECT`, `INDEX_SELECT`, `READING` and `WRITING`.

```python
from snesrtc import Chip, Store, epson

cycles = [1_000_000_000 * epson.CRYSTAL_HZ]
held = Store(cleared=True)
held.write(epson.CF, epson.HOURS_24)
held.write(epson.CD, epson.CAL_HW)
held.stamp = 1_000_000_000
clock = Chip("rtc-4513", held, now=lambda: cycles[0])


def session(mode, values=()):
    clock.write(epson.ENABLE, 0x01)
    clock.write(epson.DATA, mode)
    clock.write(epson.DATA, epson.S1)
    for value in values:
        clock.write(epson.DATA, value)
    shown = [clock.read(epson.DATA) for _ in range(13)] if mode == epson.READ_MODE else []
    clock.write(epson.ENABLE, 0x00)
    return "".join(f"{nibble:X}" for nibble in reversed(shown))


session(epson.WRITE_MODE, (0, 5, 9, 5, 3, 2, 1, 3, 2, 1, 9, 9, 5))
print(session(epson.READ_MODE))
cycles[0] += 15 * epson.CRYSTAL_HZ
print(session(epson.READ_MODE))
```

```
5991231235950
6000101000005
```

Each line is W, Y10 down to S1: weekday 5, 99-12-31, 23:59:50. Fifteen seconds later the read shows weekday 6, 00-01-01, 00:00:05, because the part counts its crystal and is current whenever it is read. A chip built with `rate=epson.WHOLE_SECONDS` would show the old time on that read and the new one only after it had been deselected once.

| Attribute or call                                                           | Meaning                                                                                                                                                            |
| :-------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `state`                                                                     | `"inactive"`, `"mode"`, `"index"`, `"read"` or `"write"`                                                                                                           |
| `mode`                                                                      | `0x03` or `0x0C`, the last mode chosen                                                                                                                             |
| `index`                                                                     | The register the next data access reaches                                                                                                                          |
| `enable`, `status`                                                          | The last value written to `$4840`, and the status byte                                                                                                             |
| `moment()`, `store_moment(moment)`                                          | Registers S1 through W as a `calendar.Moment`, and back. The date is stored only while CAL/HW is set                                                               |
| `hour()`, `store_hour(hour)`                                                | The hour from 0 to 23, read or written in the notation CF selects                                                                                                  |
| `digit(index)`, `put_digit(index, value)`                                   | A register's digit bits alone, leaving its flag bits alone                                                                                                         |
| `twenty_four_hour()`, `dated()`, `stopped()`                                | Whether 24/12 is set, CAL/HW is set, and RESET or STOP is set                                                                                                      |
| `elapsed(current)`                                                          | Seconds from the stamp to `current`. A gap over 2^31 reads as 0                                                                                                    |
| `update(offset=0)`                                                          | Advance the counters to `now() - offset`, unless HOLD is set, and set the read flags if any second passed                                                          |
| `set_read_flag()`, `clear_read_flag()`                                      | Set or clear fr in the five registers that carry it                                                                                                                |
| `read_data()`, `write_enable(value)`, `write_data(value)`                   | What a read of `$4841`, a write of `$4840` and a write of `$4841` do                                                                                               |
| `write_register(value)`, `write_control_d(value)`, `write_control_f(value)` | A data write to the current register, and the two control registers that act when written                                                                          |
| `release_hold()`, `adjust_to_nearest_minute(behind=0)`                      | What clearing HOLD and setting 30ADJ. do. `behind` is how many seconds ago the adjustment landed                                                                   |
| `std_p`                                                                     | The STD.P pin: `crystal.LOW` or `crystal.OPEN`. Low while IRQ-F is up in interrupt cycle mode, for 7.8 ms after an increment in fixed-period mode, open under MASK |
| `interrupt_oscillation()`, `restore_oscillation()`                          | Stop the oscillator, which sets fo, and start it again. The time between the two is lost                                                                           |
| `rate`, `crystal`, `oscillating`                                            | Counts of `now` per second, the `crystal.Crystal` that holds the sub-second state, and whether the oscillator runs                                                 |
| `seconds()`, `keep_time()`                                                  | `now()` in whole seconds, and the catch-up a crystal-rate chip makes at every access                                                                               |

```python
from snesrtc import Chip, Store, epson

held = Store(cleared=True)
held.write(epson.CF, epson.HOURS_24)
held.write(epson.CD, epson.CAL_HW)
held.write(epson.D1, 1)
held.write(epson.MO1, 1)
held.write(epson.S10, 4)
held.stamp = 1_000_000_000
cycles = [1_000_000_000 * epson.CRYSTAL_HZ]
clock = Chip("rtc-4513", held, now=lambda: cycles[0])

clock.write(epson.ENABLE, 0x01)
print(f"{clock.read(epson.STATUS):#04x} {clock.read(epson.STATUS):#04x}")
clock.write(epson.DATA, epson.WRITE_MODE)
clock.write(epson.DATA, epson.CD)
clock.write(epson.DATA, epson.CAL_HW | epson.IRQ_F | epson.ADJUST)
clock.write(epson.DATA, 0x0F)
clock.write(epson.DATA, epson.HOURS_24 | epson.TEST)
print(f"CD={held.read(epson.CD):#x} CF={held.read(epson.CF):#x}")
cycles[0] += 5
clock.write(epson.ENABLE, 0x00)
print(f"CD={held.read(epson.CD):#x} CF={held.read(epson.CF):#x}", clock.moment())
```

```
0x80 0x00
CD=0xa CF=0xc
CD=0x2 CF=0x4 <2000-01-01 00:01:00 weekday=0>
```

Status reads `0x80` once after the select. The write to CD sets IRQ-F and 30ADJ. as well as CAL/HW. IRQ-F is not stored. 30ADJ. reads 1 for the 125 microsecond lockout, 4 crystal cycles, then rounds 40 seconds up to the next minute and clears itself. TEST is set by the write to CF and cleared by the deselect.

### Calendar

`snesrtc.calendar` holds the arithmetic both parts run when they catch up.

| Name                                                           | Content                                                          |
| :------------------------------------------------------------- | :--------------------------------------------------------------- |
| `Moment(year, month, day, hour, minute, second, weekday)`      | One reading of a clock. Compares and hashes by value             |
| `advance(moment, seconds)`                                     | The moment `seconds` later, counted the way the reference counts |
| `is_leap(year)`                                                | The Gregorian rule                                               |
| `days_in(year, month)`                                         | 28 to 31. A month outside 1 to 12 is reduced modulo 12           |
| `weekday(year, month, day)`                                    | 0 for Sunday, counted from Monday 1 January 1900                 |
| `MONTHS`, `EPOCH_YEAR`, `EPOCH_WEEKDAY`, `WEEK`, `DAY`, `MASK` | The constants behind them                                        |

```python
from snesrtc.calendar import Moment, advance, days_in, is_leap, weekday

print(advance(Moment(1999, 12, 31, 23, 59, 59, 5), 1))
print(is_leap(1900), is_leap(2000), days_in(1996, 2), weekday(1996, 8, 18))
```

```
<2000-01-01 00:00:00 weekday=6>
False True 29 0
```

### The doctor

| Command                                              | Exit code                                                     |
| :--------------------------------------------------- | :------------------------------------------------------------ |
| `python3 snesrtc/doctor.py` from the repository root | 0 when every check of the package passes, 1 when one does not |
| `snesrtc-doctor`, after a pip install                | The same                                                      |

It takes no arguments. It reports the machine first: interpreter, encodings, filesystem case, line endings, path length, free space and git. Those lines advise and never change the exit code. Then it checks the package: the Python version, both clocks built and reset, a clock given a fixed time reading it back, `$2802` reading as open bus, the pin in [`conformance/pinned.json`](conformance/pinned.json), and whether the reference driver is built. A check that raises is reported with the exception's type and message.

## Where each answer comes from

The two clocks rest on different evidence.

| Rung | Source                                                             | Settles                                                                                                                                                                                   |
| :--- | :----------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | Seiko Epson, _Application Manual: Real Time Clock Module RTC-4513_ | Anything Epson printed about the RTC-4513: register widths, count ranges, what each control bit does, how a session is framed, what power-on leaves behind                                |
| 2    | A recording from snes9x, pinned by commit                          | What the manual does not: how the SPC7110 turns a three-wire serial part into three cartridge addresses, what the counters do outside a documented range, and the whole of the Sharp part |
| 3    | Nothing else                                                       | Nothing                                                                                                                                                                                   |

Every figure on rung 1 is in [`conformance/hardware.json`](conformance/hardware.json) with the sentence it was read from, the document's digest and the date it was read. [`conformance/hardware.test.py`](conformance/hardware.test.py) drives the package and checks what it does against it.

Where the manual and the recording disagree, the package follows the manual. Each of the 15 disagreements is an entry in [`conformance/divergences.json`](conformance/divergences.json) naming what the document says, what the recording does, which one the package follows, and what evidence would settle it.

### The Sharp part has no datasheet

`S-RTC` is a Nintendo part designation in the style of `S-DSP`, `S-SMP` and `S-PPU`, not a Sharp catalogue number. No manufacturer document for it is known. The search, dated 2026-08-20, is recorded in `hardware.json` under `"verified": false` with the three findings that would settle it: a Sharp data book entry, a die photograph naming a catalogue part, or a logic capture of the bus while Daikaijuu Monogatari II drives the clock. A test asserts that the block still says so.

## What the manual settles

**Six of the thirteen clock registers carry a digit narrower than the register.** The count range column shows it: S10 and MI10 stop at 5, H10 at 2, D10 at 3, MO10 at 1 and W at 6. The spare bits are the oscillation flag, the read flag, the PM/AM bit and free RAM a program may use. `epson.DIGIT_MASK` keeps them apart, so a flag a program stores is never read back as part of the date.

**HOLD does not stop the clock.** The manual says "The clock continues to run", and that the first increment missed while HOLD is set "is compensated for when the hold condition is released (+1 second)." Releasing HOLD adds one second, and the manual's procedure for setting the clock warns that the write must finish within one second.

**No control bit adds a second.** CD bit 1 is CAL/HW. Clear, it switches the date counters off and leaves those registers as RAM. The read flags in D10 and MO10 go with them: neither a tick nor deselecting the chip touches them while CAL/HW is clear. The one documented software adjustment is 30ADJ. on CD bit 3.

**Twelve-hour notation is the power-on state.** The manual: "At power-on, all registers and the STD.P output are undefined." A register file that powers up as zeroes has 24/12 clear, which is twelve-hour notation, and CAL/HW clear, which stops the date.

```python
from snesrtc import Chip, Store, epson

cycles = [1_000_000_000 * epson.CRYSTAL_HZ]
held = Store(cleared=True)
held.stamp = 1_000_000_000
written = {epson.S1: 9, epson.S10: 5, epson.MI1: 9, epson.MI10: 5, epson.H1: 1, epson.D1: 1}
for index, digit in written.items():
    held.write(index, digit)
held.write(epson.H10, 1 | epson.PM)
clock = Chip("rtc-4513", held, now=lambda: cycles[0])

cycles[0] += epson.CRYSTAL_HZ
clock.write(epson.ENABLE, 0x01)
clock.write(epson.ENABLE, 0x00)

print([held.read(index) for index in (epson.H10, epson.H1, epson.D10, epson.D1, epson.W)])
print(clock.moment())
```

```
[1, 2, 0, 1, 1]
<2000-00-01 00:00:00 weekday=1>
```

At 11:59:59 PM one second passes. The hour becomes 12 with PM clear, which is midnight. The weekday counter moves from 0 to 1, and the day stays at 1 because CAL/HW is clear.

**IRQ-F cannot be written.** The manual: "A write instruction for the IRQ-F bit is not executed." With INT/STND set in CE, the increment that t1 and t0 select raises it, and reading CD clears it. While MASK is set it reads 0, and setting MASK puts down a flag already raised. In fixed-period mode the flag stays up for 7.8 ms. A chip counting crystal cycles holds it for 256 of them; a chip counting whole seconds cannot, and does not raise it there.

**Each notation fixes one bit of H10 at 0.** In twelve-hour notation "The h20 bit cannot be written and is fixed to "0"." In twenty-four hour notation "A write attempt to the PM/AM bit is disregarded, and the bit will always read "0"." A write drops that bit, and a read shows 0 whatever the register holds.

**TEST clears when the chip is deselected**, and a write to CF with RESET set clears it too.

**STOP takes effect after the counters are brought current.** A write to CF catches the clock up first and then stores the new bits, so time that passed before the stop is kept.

## What the recording settles

The manual says nothing on these. Its one sentence on the subject is "Do not set impossible values to prevent the possibility of clock malfunction."

**A month of zero is a 30-day month.** The counters subtract one from the month before counting, in unsigned 32-bit arithmetic. Zero becomes 4,294,967,295, and the month length is read from that number modulo 12, which lands on a 30-day month that rolls into January of the same year.

**A field above its range is cleared, not reduced.** A minute of 100 carries to 0 and adds one hour, so the 40 minutes above 60 are lost.

```python
from snesrtc.calendar import Moment, advance

print(advance(Moment(1996, 0, 30, 23, 59, 59, 0), 1))
print(advance(Moment(1996, 8, 18, 12, 100, 59, 0), 1))
```

```
<1996-01-01 00:00:00 weekday=1>
<1996-08-18 13:00:00 weekday=0>
```

**An Epson clock counting whole seconds catches up when it is deselected**, not when it is selected. Built with `rate=epson.WHOLE_SECONDS`, a session reads the time as the previous session left it. The default chip counts its crystal and catches up at every access, as the session example above shows, so it has no such seam, and neither does a real part. The whole-second placement stays because the recording is compared in it.

**The mode code is compared as a whole byte.** The serial part only ever sees four bits, so this is a property of the SPC7110 wrapper, which no document describes.

## The two chips

They are parts from different makers, on cartridges from different publishers.

|                       | Sharp S-RTC                                     | Epson RTC-4513                                                    |
| :-------------------- | :---------------------------------------------- | :---------------------------------------------------------------- |
| Manufacturer document | None known                                      | Application manual, 1999                                          |
| Reached at            | `$2800` and `$2801`                             | `$4840` through `$4842`, through the SPC7110                      |
| Shape                 | A fixed sequence wrapped in a marker            | An addressed file of sixteen 4-bit registers                      |
| Getting at one field  | Read the whole sequence and count               | Name its register                                                 |
| Weekday               | Computed from the date when the date is written | A counter of its own, 0 to 6, with no meaning attached            |
| Year                  | Three digits plus 1000                          | Two digits, no century printed anywhere                           |
| Hours                 | 24                                              | 12 or 24, chosen by a control bit                                 |
| Control registers     | None                                            | Three, with sixteen named bits                                    |
| Catches up            | When a read starts                              | At every access, or when deselected at `rate=epson.WHOLE_SECONDS` |

## Nothing starts cleared

A battery-backed cartridge holds what it held, and one fresh from the factory holds whatever the silicon powered up with. Epson prints "At power-on, all registers and the STD.P output are undefined."

`Store(seed=UNSET_SEED, cleared=False, held=None)` fills its 20 bytes from `seed`. `cleared=True` fills them with zeroes, and `held` copies bytes over the top, wrapping at 20. `read(index)` and `write(index, value)` wrap the index at 20 and keep the low eight bits of a value. `bytes` is the list itself, and `stamp` reads or writes bytes 16 to 19 as one little-endian number. `snesrtc.store` carries `SIZE`, `STAMP_AT`, `STAMP_BYTES` and `UNSET_SEED`.

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

A seeded store holds the same bytes on every read and different bytes for a different seed, so a test can show a program does not depend on what it never wrote. A caller who means zeroes asks for them, and a caller restoring a cartridge passes the bytes it had.

## What is deliberately not modelled

Each is an entry in [`conformance/divergences.json`](conformance/divergences.json) with the reason and what would change it.

**No interrupt.** CE selects one of four periods, 1/64 second, 1 second, 1 minute or 1 hour, and drives the STD.P pin. No document says the SPC7110 routes that pin anywhere a Super Nintendo program can read, so CE drives no pin and no interrupt reaches the console. What it does to IRQ-F, which a program reads in CD, is modelled.

**No crystal drift.** The manual gives 0 plus or minus 25 ppm at 25 degrees C, a secondary temperature coefficient of -0.035 ppm per degree C squared, and "At 11.574 ppm, the daily clock error is about one second per day." The figures are in the record. They bound a population of modules at a temperature the model cannot know, so they are not simulated.

**No 125 microsecond lockout after 30ADJ.** The bit clears itself, which is modelled. The window in which S1 through W cannot be written needs a time base finer than one second, which the `now` interface does not carry.

## Is it right

The differential drives each part with scripts generated from a seed, runs the same scripts through a driver compiled around the pinned snes9x sources, and compares the two transcripts line by line.

```bash
python3 -m conformance.build
python3 -m conformance.reference
```

```
epson: 200 scripts, 6129 operations compared whole, 1 compared except excused fields, 9772 not compared, 0 disagreed
  fields excused under epson-irqf-not-writable on 1 operations
  not compared past epson-digit-fields-narrower-than-registers, reached by 195 scripts
  not compared past epson-read-and-oscillation-flags, reached by 134 scripts
  ...
sharp: 200 scripts, 323500 operations compared whole, 0 compared except excused fields, 155 not compared, 0 disagreed
  not compared past stamp-width-platform-dependent, reached by 2 scripts
```

Where the model follows the manual in one field the recording keeps as plain storage, IRQ-F in CD or the bit of H10 a notation fixes at 0, the runner keeps comparing and excuses that field alone: every other bit of the line still has to agree, and those operations are counted apart. Every other declared divergence stops the script's comparison at the first operation that reaches it, because past that point the recording answers a question the manual already answered differently and its state differs in fields later arithmetic reads, so those operations are counted apart and named. A divergence the runner can witness that is not in `divergences.json` fails the run, and the runner reads the list from that file on every script.

The Sharp part is compared almost end to end, because the recording is its only authority. The one exclusion is about the recorder: it tests its stamp against the maximum of the host's `time_t`, so a 64-bit and a 32-bit build disagree on any gap past 2^31 seconds.

Epson scripts are capped at 200 operations. Comparison stops after about 30 on average, 6130 over 200 scripts, so the part's coverage grows with the number of scripts and not their length.

The two clocks are driven by separate scripts. In the harness and in the recording they share one 20-byte store, which no cartridge did, since none carried both parts. Time is scripted too, because the reference reads the wall clock. The reference sources are fetched at build time and never vendored. Only the driver in [`conformance/ref/driver.cpp`](conformance/ref/driver.cpp) belongs to this repository.

| Command                                                     | Arguments                                                                                    | Exit code                                                                                                                                      |
| :---------------------------------------------------------- | :------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------- |
| `python3 -m conformance.build`                              | `--sources DIR`, `--output PATH`, `--pinned FILE`, `--driver-source FILE`                    | 0 built, 1 compile failed, 2 bad arguments or fetch failed                                                                                     |
| `python3 -m conformance.reference`                          | `--runs N`, default 200, `--from N`, `--seed N`, `--length N`, default 4000, `--driver PATH` | 0 no disagreement, 1 a disagreement or an undeclared divergence, 2 no driver or bad arguments                                                  |
| `python3 -m conformance.documents`                          | `--check` to verify without fetching, `--only SUBSTRING`                                     | 0 every digest matched; 1 a document was refused, none matched, or the arguments were bad                                                      |
| `python3 -m conformance.quotes`                             | None                                                                                         | 1 when a quote in the record is not found in its document or a citation does not check out, 0 otherwise, including when no document is on disk |
| `python3 -m conformance.speed`                              | None                                                                                         | 0 when reads beat the floor of 500,000 per second, 1 when they do not                                                                          |
| `python3 -m conformance.cartridge CARTRIDGE OUT.json`       | A cartridge image and an output path                                                         | 0 written, 1 no clock routine found, 2 bad arguments or no such file                                                                           |
| `python3 -m conformance.sharp_cartridge CARTRIDGE OUT.json` | A cartridge image and an output path                                                         | 0 written, 1 no clock script table found, 2 bad arguments or no such file                                                                      |

A failing script is regenerated from its seed. `reference.generate(seed, length, part)` returns the operations and `reference.render(script)` the text the driver reads on standard input.

```python
from conformance import reference

script = reference.generate(seed=22, length=4000, part="sharp")
print(len(script), reference.render(script).splitlines()[:4])
```

```
4000 ['time 1000000000', 'store 15 4', 'store 13 2', 'w 10241 12']
```

The script opens by setting the time and configuring the Epson control registers, then writes `0x0C` to `$2801`, which is 10241.

[`conformance/cartridge.json`](conformance/cartridge.json) records what the clock routine of Tengai Makyou Zero writes to the part, read out of the program without running it: five constant writes to the control registers, among them CF set to `0x07` and then `0x04`, and CD set to `0x06`. It also records that each of the program's five read sessions writes the data port once, to choose the index, and never again while the part is in read mode; that the program reads a two-digit year as 1995 to 2094, adding 1900 at 95 and above and 2000 below; and that its initialisation loads 1995-12-22 12:00:00. The file holds digests of the image and no byte of it.

[`conformance/sharp_cartridge.json`](conformance/sharp_cartridge.json) records the same kind of reading for Daikaijuu Monogatari II and the Sharp part: the program keeps its clock traffic as a table of steps, and the table holds nine scripts. It reads the marker `0x0F`, thirteen digits and the marker again, which is the sequence the recording gives. It writes `0x0E`, then `0x00` and the twelve digits from seconds to the hundreds of years, then `0x0D`, and leaves the weekday out, which the recording derives. It also sends `0x0E` and `0x04` on its own, which the recording reads as clearing the clock, and six commands the recording ignores: `0x01`, `0x02` and `0x03`, each followed by the eight digits from hours to the hundreds of years, and `0x05`, `0x06` and `0x07` on their own. What the part does with those six is not known. The file holds digests of the image and no byte of it.

## Working on it

| Need                                                            | Where                                                               |
| :-------------------------------------------------------------- | :------------------------------------------------------------------ |
| Every gate and the order to run them                            | [CONTRIBUTING.md](CONTRIBUTING.md)                                  |
| The same material for a coding agent                            | [AGENTS.md](AGENTS.md)                                              |
| The standard this repository shares with the rest of the family | [FAMILY.md](FAMILY.md)                                              |
| What is not settled, and what would settle it                   | [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md)                              |
| Bug reports                                                     | [GitHub Issues](https://github.com/gufranco/snes-rtc-python/issues) |
| Security reports                                                | [SECURITY.md](SECURITY.md)                                          |
| Conduct                                                         | [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)                            |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 mypy==1.14.1
cov=(uvx --python 3.12 --from coverage==7.6.10 --with setuptools==84.0.0 coverage)
"${cov[@]}" erase
for file in $(find snesrtc conformance -name '*.test.py' | sort); do
  "${cov[@]}" run -a "$file"
done
"${cov[@]}" report
```

Each module has a test file beside it, named after it, and each runs on its own. Coverage is a hard gate at 100% statement and branch, and mypy runs strict.

Do not resolve a divergence by changing the model to match the recording. If the manual is wrong, say why, with the page. A new disagreement needs an entry in `divergences.json` naming what would settle it, or the differential fails.

## References

- _Application Manual: Real Time Clock Module RTC-4513_, Seiko Epson, 1 December 1999. 18 pages, 509,740 bytes, SHA-256 `409b8a5a3030fe432dd7dafbf4719944abac890cc5cbebbf96fb8313f9caca33`. A fax with no text layer, so a citation into it is checked by rendering the page.
- _RTC-4513 catalogue extract_, Seiko Epson, undated. 2 pages, 701,040 bytes, SHA-256 `6496eb35fddc181d4e80832b98b8a45163bf5370eadd1e58002aefc83f12edcf`. It prints the same sixteen-row register table.
- snes9x, `srtcemu.cpp` and `spc7110emu.cpp` with their headers, at commit `2971061cf07fdc6fc7d18883edf4e648eb16a6d2`, https://github.com/snes9xgit/snes9x, pinned in [`conformance/pinned.json`](conformance/pinned.json). The reference both parts are compared against. Fetched at build time and never vendored.

Neither Epson document is redistributable or in this repository. [`conformance/documents.json`](conformance/documents.json) carries the digest, size and address of each, and `python3 -m conformance.documents` fetches them into `docs/`, which git ignores, and refuses any file whose digest does not match.

## Citing this

[CITATION.cff](CITATION.cff) is updated with each release by the script that stamps the package version.

## License

MIT. See [LICENSE](LICENSE). The snes9x sources are a separate work under their own licence, fetched at build time and never redistributed here.
