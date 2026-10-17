# SNES 卡带时钟

用 Python 实现超级任天堂卡带可能搭载的两种实时时钟：Sharp S-RTC 与 Epson RTC-4513。Epson 部件以 Seiko Epson 的应用手册为准，两者都以一个固定版本的 snes9x 构建为参照。

[English](README.md) | [日本語](README.ja.md) | 简体中文 | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/snes-rtc-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/snes-rtc-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/snes-rtc-python)](https://github.com/gufranco/snes-rtc-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**2** 个时钟，**329,630** 次操作与参考实现比对，**0** 处不一致，**15** 处手册与该参考实现不同，每一处都有记录，**1,007** 个测试，**100%** 语句与分支覆盖率，无依赖

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

这个示例在一个清零的存储区上构建 Sharp 时钟，并交给它一个由示例控制的时间源。命令 `0E` 后跟 `00` 开始一次写入，十二个数字从秒开始，设定 1996 年 8 月 18 日 12:30:00。芯片自行算出第十三个数字，即星期，那个星期日为 0。命令 `0D` 开始一次读取。把时间源向前拨 95 秒并读取十五次，返回 `F` 标记、同一日期的 12:31:35、星期，然后再次返回标记。

## 安装

| 要求 | 版本 |
|:--|:--|
| Python | 3.12 或更高 |
| git | 任意版本，用于克隆 |
| C++17 编译器 `g++` | 仅在构建差分比对所用的参考实现时需要 |

```bash
git clone https://github.com/gufranco/snes-rtc-python.git
cd snes-rtc-python
python3 snesrtc/doctor.py
```

该包不导入标准库以外的任何内容。`pip install git+https://github.com/gufranco/snes-rtc-python.git` 会安装它，但不含一致性测试套件，并添加一个 `snesrtc-doctor` 命令。

诊断脚本检查机器与检出目录，驱动两个时钟，最后输出一行。包的每项检查都通过时退出码为 0，有一项未通过时为 1。提交缺陷报告时请粘贴它的完整输出。

```
  8 checks, nothing to report
```

版本遵循[语义化版本](https://semver.org/)，由 semantic-release 根据提交历史生成。每个版本都打了标签，并列在[版本发布页面](https://github.com/gufranco/snes-rtc-python/releases)上。

## 接口

`snesrtc.Chip(model, store=None, now=..., open_bus=0x00)` 构建一个时钟。`model` 是必需的。`store` 是一个 `Store`，省略时时钟会构建一个带种子的存储区。`now` 是一个返回整秒数的可调用对象，时钟保留其低 32 位；默认读取 `time.time()`。`open_bus` 只有 Sharp 部件接受，是它在不属于自己的地址上返回的值。Epson 部件在那里返回 `0x00`。

| 型号 | 别名 | 地址 | 年份 | 小时制 |
|:--|:--|:--|:--|:--|
| `s-rtc` | `srtc`, `sharp`, `sharprtc` | `$2800` 数据，`$2801` 控制 | 三位数字加 1000，即 1000 至 1999 | 24 |
| `rtc-4513` | `rtc4513`, `epson`, `epsonrtc`, `spc7110`, `spc7110rtc` | `$4840` 使能，`$4841` 数据，`$4842` 状态 | 两位数字，解读为 1990 至 2089 | 12 或 24，由一个控制位选择 |

名称匹配不区分大小写，空格、连字符和下划线都会被忽略。缺少名称或名称未知时抛出 `UnknownModelError`，其消息列出可接受的名称。

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

### 两个时钟共有的调用

| 调用 | 作用 |
|:--|:--|
| `read(address)` | 从卡带总线读取一个字节 |
| `write(address, value)` | 向卡带总线写入一个字节。无返回值 |
| `reset()` | 等同于主机的复位。Sharp 部件回到读取序列的开头，并把时间更新到当前。Epson 部件被取消选中，回到写模式、寄存器 0，使能与状态清零。存储区不受影响。返回该时钟 |

| 属性 | 含义 |
|:--|:--|
| `model` | 规范型号名 |
| `store` | 时钟在其中计数的 `Store` |
| `now` | 时间源 |

### 模块内容

| 名称 | 内容 |
|:--|:--|
| `snesrtc.MODELS` | 两条 `Model` 记录，以规范名称为键 |
| `snesrtc.Model` | 一条记录，含 `name`、`summary`、`addresses`、`protocol` 和 `aliases`，以及 `Chip` 调用的 `build(store=None, **options)` |
| `snesrtc.models.lookup(name)` | 任意写法对应的 `Model`。抛出 `UnknownModelError` |
| `snesrtc.Store(seed=UNSET_SEED, cleared=False, held=None)` | 卡带靠电池保存的 20 个字节。参见[没有什么从清零开始](#nothing-starts-cleared) |
| `snesrtc.Built` | `Chip` 返回的类型，即 `epson.Chip` 或 `sharp.Chip` |
| `snesrtc.UnknownModelError` | 该包唯一会抛出的错误，用于缺少或未知的型号名。它位于 `snesrtc.errors` |
| `snesrtc.__version__` | 已安装的版本 |
| `snesrtc.sharp`, `snesrtc.epson` | 各部件的 `Chip` 类、地址、命令码和寄存器常量 |
| `snesrtc.store` | `Store` 及其常量 `SIZE`、`STAMP_AT`、`STAMP_BYTES` 和 `UNSET_SEED` |
| `snesrtc.calendar` | 两个部件共用的日历运算 |

### Sharp S-RTC

对 `$2801` 的写入驱动一个状态机。只读取值的低四位。

| 写入 `$2801` | 作用 |
|:--|:--|
| `0D` | 开始读取。下一次读取 `$2800` 会把时间更新到当前，并返回 `0F` 标记 |
| `0E` | 等待命令 |
| `0E`，然后 `00` | 开始写入。接下来的十二次写入是各个数字，芯片计算第十三个数字，即星期 |
| `0E`，然后 `04` | 把全部十三个数字清为 0 |
| `0E`，然后任何其他值 | 停止。在下一个 `0D` 或 `0E` 之前忽略写入 |
| `0F` | 忽略 |

一个读取序列依次是 `0F` 标记、十三个数字、再一个标记，之后从头开始。不在读取中时，`$2800` 返回 `0x00`。

| 存储区字节 | 数字 |
|:--|:--|
| 0, 1 | 秒，先个位后十位 |
| 2, 3 | 分 |
| 4, 5 | 时 |
| 6, 7 | 日 |
| 8 | 月，一个数字表示 1 至 12 |
| 9, 10, 11 | 年份减 1000，依次为个位、十位、百位 |
| 12 | 星期，星期日为 0，从 1900 年 1 月 1 日星期一起算 |
| 16 至 19 | 存储区上次更新到当前的时间，低字节在前 |

| 属性或调用 | 含义 |
|:--|:--|
| `mode` | `"read"`、`"command"`、`"write"` 或 `"ready"` |
| `index` | 序列中的下一个数字，标记之前为 -1 |
| `open_bus` | 读取不属于该部件的地址时得到的值 |
| `read_moment()`, `store_moment(moment)` | 把十三个数字转为 `calendar.Moment`，以及反向转换 |
| `elapsed()` | 自字节 16 至 19 中时间戳以来的秒数。超过 2^31 的间隔读作 0 |
| `update()` | 把各数字推进 `elapsed()` 秒并重新打时间戳 |
| `command(value)`, `accept(value)` | `write` 在命令字节之后的两半 |

`snesrtc.sharp` 包含 `DATA`、`CONTROL`、`MARKER`、`LAST_INDEX`、`COMMAND_READ`、`COMMAND_BEGIN`、`COMMAND_NOTHING`、`COMMAND_WRITE`、`COMMAND_CLEAR`、`YEAR_BASE` 和 `STAMP_LIMIT`，以及四个 `mode` 值 `READING`、`COMMAND`、`WRITING` 和 `READY`。

### Epson RTC-4513

SPC7110 把该部件的三线串行接口变成三个卡带地址。程序以会话的方式与它通信。

| 步骤 | 总线访问 | 作用 |
|:--|:--|:--|
| 选中 | 写 `$4840`，置位 bit 0 | 状态变为 `0x80`。部件等待模式 |
| 模式 | 写 `$4841`，值为 `0x03` 或 `0x0C` | 写模式或读模式。其他值被忽略 |
| 寄存器 | 写 `$4841`，值为 0 至 15 | 下一次访问开始的寄存器 |
| 数据 | 写或读 `$4841` | 一个半字节。随后寄存器索引加一，超过 15 后回绕 |
| 取消选中 | 写 `$4840`，清除 bit 0 | 把计数器更新到当前，清除读取标志并清除 TEST |
| 状态 | 读 `$4842` | 任何访问之后为 `0x80`，然后为 `0x00`，直到下一次访问 |

读取 `$4840` 返回最后写入那里的值。读取 CD 会清除 IRQ-F。

| 寄存器 | 索引 | D3 | D2 | D1 | D0 | 计数范围 |
|:--|:--|:--|:--|:--|:--|:--|
| `S1` | 0 | s8 | s4 | s2 | s1 | 0 至 9 |
| `S10` | 1 | fo | s40 | s20 | s10 | 0 至 5 |
| `MI1` | 2 | mi8 | mi4 | mi2 | mi1 | 0 至 9 |
| `MI10` | 3 | fr | mi40 | mi20 | mi10 | 0 至 5 |
| `H1` | 4 | h8 | h4 | h2 | h1 | 0 至 9 |
| `H10` | 5 | fr | PM/AM | h20 | h10 | 0 至 2 |
| `D1` | 6 | d8 | d4 | d2 | d1 | 0 至 9 |
| `D10` | 7 | fr | 空闲 RAM | d20 | d10 | 0 至 3 |
| `MO1` | 8 | mo8 | mo4 | mo2 | mo1 | 0 至 9 |
| `MO10` | 9 | fr | 空闲 RAM | 空闲 RAM | mo10 | 0 至 1 |
| `Y1` | 10 | y8 | y4 | y2 | y1 | 0 至 9 |
| `Y10` | 11 | y80 | y40 | y20 | y10 | 0 至 9 |
| `W` | 12 | fr | w4 | w2 | w1 | 0 至 6 |
| `CD` | 13 | 30ADJ. | IRQ-F | CAL/HW | HOLD | |
| `CE` | 14 | t1 | t0 | INT/STND | MASK | |
| `CF` | 15 | TEST | 24/12 | STOP | RESET | |

`snesrtc.epson` 按索引命名每个寄存器，从 `S1` 到 `CF`，并按掩码命名每个控制位：CD 中的 `HOLD`、`CAL_HW`、`IRQ_F` 和 `ADJUST`，CF 中的 `RESET`、`STOP`、`HOURS_24` 和 `TEST`，以及 CE 中的 `MASK` 和 `INT_STND`。它还包含 `ENABLE`、`DATA`、`STATUS`、`WRITE_MODE`、`READ_MODE`、`READY`、`REGISTERS`、`DIGIT_MASK`、`OSC_FLAG`、`READ_FLAG`、`READ_FLAG_AT`、`CALENDAR_READ_FLAG_AT`、`PM`、`H20`、`STOPPED`、`NIBBLE`、`HALF_MINUTE`、`MINUTE`、`HOUR`、`WHOLE_SECONDS_PER_PERIOD`、`PERIOD_SHIFT`、`PERIOD_BITS`、`NOON`、`YEAR_PIVOT` 和 `STAMP_LIMIT`，以及五个 `state` 值 `INACTIVE`、`MODE_SELECT`、`INDEX_SELECT`、`READING` 和 `WRITING`。

```python
from snesrtc import Chip, Store, epson

seconds = [1_000_000_000]
held = Store(cleared=True)
held.write(epson.CF, epson.HOURS_24)
held.write(epson.CD, epson.CAL_HW)
held.stamp = seconds[0]
clock = Chip("rtc-4513", held, now=lambda: seconds[0])


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
seconds[0] += 15
print(session(epson.READ_MODE))
print(session(epson.READ_MODE))
```

```
5991231235950
5991231235950
6000101000005
```

每一行依次是 W、Y10 直到 S1：星期 5，99-12-31，23:59:50。十五秒后，第一次读取仍显示旧时间，因为部件在被取消选中时才追上时间。之后的读取显示星期 6，00-01-01，00:00:05。

| 属性或调用 | 含义 |
|:--|:--|
| `state` | `"inactive"`、`"mode"`、`"index"`、`"read"` 或 `"write"` |
| `mode` | `0x03` 或 `0x0C`，最后选择的模式 |
| `index` | 下一次数据访问到达的寄存器 |
| `enable`, `status` | 最后写入 `$4840` 的值，以及状态字节 |
| `moment()`, `store_moment(moment)` | 把寄存器 S1 至 W 转为 `calendar.Moment`，以及反向转换。只有在 CAL/HW 置位时才存储日期 |
| `hour()`, `store_hour(hour)` | 0 至 23 的小时，按 CF 选择的表示法读取或写入 |
| `digit(index)`, `put_digit(index, value)` | 只处理寄存器的数字位，不动其标志位 |
| `twenty_four_hour()`, `dated()`, `stopped()` | 24/12 是否置位、CAL/HW 是否置位、RESET 或 STOP 是否置位 |
| `elapsed(current)` | 从时间戳到 `current` 的秒数。超过 2^31 的间隔读作 0 |
| `update(offset=0)` | 把计数器推进到 `now() - offset`，除非 HOLD 置位；若有任何一秒经过，则设置读取标志 |
| `set_read_flag()`, `clear_read_flag()` | 在带有 fr 的五个寄存器中置位或清除 fr |
| `read_data()`, `write_enable(value)`, `write_data(value)` | 读取 `$4841`、写入 `$4840` 和写入 `$4841` 时执行的操作 |
| `write_register(value)`, `write_control_d(value)`, `write_control_f(value)` | 对当前寄存器的数据写入，以及写入时会起作用的两个控制寄存器 |
| `release_hold()`, `adjust_to_nearest_minute()` | 清除 HOLD 和设置 30ADJ. 时执行的操作 |

```python
from snesrtc import Chip, Store, epson

held = Store(cleared=True)
held.write(epson.CF, epson.HOURS_24)
held.write(epson.CD, epson.CAL_HW)
held.write(epson.D1, 1)
held.write(epson.MO1, 1)
held.write(epson.S10, 4)
held.stamp = 1_000_000_000
clock = Chip("rtc-4513", held, now=lambda: 1_000_000_000)

clock.write(epson.ENABLE, 0x01)
print(f"{clock.read(epson.STATUS):#04x} {clock.read(epson.STATUS):#04x}")
clock.write(epson.DATA, epson.WRITE_MODE)
clock.write(epson.DATA, epson.CD)
clock.write(epson.DATA, epson.CAL_HW | epson.IRQ_F | epson.ADJUST)
clock.write(epson.DATA, 0x0F)
clock.write(epson.DATA, epson.HOURS_24 | epson.TEST)
print(f"CD={held.read(epson.CD):#x} CF={held.read(epson.CF):#x}")
clock.write(epson.ENABLE, 0x00)
print(f"CF={held.read(epson.CF):#x}", clock.moment())
```

```
0x80 0x00
CD=0x2 CF=0xc
CF=0x4 <2000-01-01 00:01:00 weekday=0>
```

选中之后，状态只读到一次 `0x80`。对 CD 的写入除了 CAL/HW，还置位了 IRQ-F 和 30ADJ.。IRQ-F 不会被存储，30ADJ. 把 40 秒向上取整到下一分钟并自行清除。TEST 由对 CF 的写入置位，由取消选中清除。

### 日历

`snesrtc.calendar` 包含两个部件在追上时间时执行的运算。

| 名称 | 内容 |
|:--|:--|
| `Moment(year, month, day, hour, minute, second, weekday)` | 时钟的一次读数。按值比较和计算哈希 |
| `advance(moment, seconds)` | `seconds` 秒之后的时刻，按参考实现的方式计算 |
| `is_leap(year)` | 格里高利历规则 |
| `days_in(year, month)` | 28 至 31。超出 1 至 12 的月份按模 12 归约 |
| `weekday(year, month, day)` | 星期日为 0，从 1900 年 1 月 1 日星期一起算 |
| `MONTHS`, `EPOCH_YEAR`, `EPOCH_WEEKDAY`, `WEEK`, `DAY`, `MASK` | 它们背后的常量 |

```python
from snesrtc.calendar import Moment, advance, days_in, is_leap, weekday

print(advance(Moment(1999, 12, 31, 23, 59, 59, 5), 1))
print(is_leap(1900), is_leap(2000), days_in(1996, 2), weekday(1996, 8, 18))
```

```
<2000-01-01 00:00:00 weekday=6>
False True 29 0
```

### 诊断脚本

| 命令 | 退出码 |
|:--|:--|
| 在仓库根目录运行 `python3 snesrtc/doctor.py` | 包的每项检查都通过时为 0，有一项未通过时为 1 |
| pip 安装后运行 `snesrtc-doctor` | 同上 |

它不接受参数。它先报告机器情况：解释器、编码、文件系统大小写、换行符、路径长度、剩余空间和 git。这些行只作建议，从不改变退出码。然后它检查包：Python 版本、两个时钟的构建与复位、设定固定时间的时钟能否读回该时间、`$2802` 是否读作开路总线、[`conformance/pinned.json`](conformance/pinned.json) 中的固定版本，以及参考驱动是否已构建。抛出异常的检查会连同异常的类型和消息一起报告。

## 每个答案的来源

两个时钟依据的证据不同。

| 层级 | 来源 | 解决的问题 |
|:--|:--|:--|
| 1 | Seiko Epson，*Application Manual: Real Time Clock Module RTC-4513* | Epson 关于 RTC-4513 印出的一切：寄存器宽度、计数范围、每个控制位的作用、会话如何构成、上电后留下什么 |
| 2 | snes9x 的一份录制结果，按提交固定 | 手册没有说明的内容：SPC7110 如何把三线串行部件变成三个卡带地址，计数器在文档范围之外的行为，以及 Sharp 部件的全部内容 |
| 3 | 别无其他 | 无 |

第 1 层的每个数值都记录在 [`conformance/hardware.json`](conformance/hardware.json) 中，附有其出处的原句、文档的摘要值和读取日期。[`conformance/hardware.test.py`](conformance/hardware.test.py) 驱动该包，并据此检查其行为。

手册与录制结果不一致时，包以手册为准。15 处不一致中的每一处都是 [`conformance/divergences.json`](conformance/divergences.json) 中的一个条目，写明文档怎么说、录制结果怎么做、包遵循哪一方，以及什么证据能解决该问题。

### Sharp 部件没有数据手册

`S-RTC` 是任天堂的部件编号，风格与 `S-DSP`、`S-SMP` 和 `S-PPU` 相同，不是 Sharp 的目录型号。目前不知道有任何关于它的厂商文档。这次查找的日期为 2026-08-20，以 `"verified": false` 记录在 `hardware.json` 中，并列出能解决问题的三种发现：Sharp 数据手册中的条目、标明目录型号的芯片裸片照片，或在《Daikaijuu Monogatari II》驱动时钟时对总线的逻辑采集。有一个测试断言该区块仍然这样写。

## 手册解决的问题

**十三个时钟寄存器中有六个所含的数字比寄存器窄。** 计数范围一列说明了这一点：S10 和 MI10 最大为 5，H10 为 2，D10 为 3，MO10 为 1，W 为 6。多余的位是振荡标志、读取标志、PM/AM 位以及程序可以使用的空闲 RAM。`epson.DIGIT_MASK` 把它们分开，因此程序存入的标志永远不会被当作日期的一部分读回。

**HOLD 不会停止时钟。** 手册写道 "The clock continues to run"，并说 HOLD 置位期间错过的第一次递增 "is compensated for when the hold condition is released (+1 second)." 释放 HOLD 会加一秒，手册中设置时钟的步骤也警告写入必须在一秒内完成。

**没有哪个控制位会加一秒。** CD bit 1 是 CAL/HW。清除时，它关闭日期计数器，让这些寄存器作为 RAM 使用。D10 和 MO10 中的读取标志也一样：CAL/HW 清除期间，时间前进或取消选中芯片都不会改动它们。唯一有文档记载的软件调整是 CD bit 3 上的 30ADJ.。

**十二小时制是上电状态。** 手册写道："At power-on, all registers and the STD.P output are undefined." 上电后全为零的寄存器组中 24/12 是清除的，即十二小时制；CAL/HW 也是清除的，即日期停止。

```python
from snesrtc import Chip, Store, epson

seconds = [1_000_000_000]
held = Store(cleared=True)
held.stamp = seconds[0]
written = {epson.S1: 9, epson.S10: 5, epson.MI1: 9, epson.MI10: 5, epson.H1: 1, epson.D1: 1}
for index, digit in written.items():
    held.write(index, digit)
held.write(epson.H10, 1 | epson.PM)
clock = Chip("rtc-4513", held, now=lambda: seconds[0])

seconds[0] += 1
clock.write(epson.ENABLE, 0x01)
clock.write(epson.ENABLE, 0x00)

print([held.read(index) for index in (epson.H10, epson.H1, epson.D10, epson.D1, epson.W)])
print(clock.moment())
```

```
[1, 2, 0, 1, 1]
<2000-00-01 00:00:00 weekday=1>
```

在 11:59:59 PM 经过一秒。小时变为 12 且 PM 清除，即午夜。星期计数器从 0 变为 1，日期保持为 1，因为 CAL/HW 是清除的。

**IRQ-F 不能写入。** 手册写道："A write instruction for the IRQ-F bit is not executed." CE 的 INT/STND 置位时，t1 和 t0 所选数位的进位会置位它，读取 CD 时清除。MASK 置位期间它读出 0，置位 MASK 也会清除已经置位的标志。固定周期模式下标志只保持 7.8 ms，短于模型计数的一秒，所以在该模式下不会置位。

**每种时制都把 H10 的一个位固定为 0。** 十二小时制："The h20 bit cannot be written and is fixed to "0"." 二十四小时制："A write attempt to the PM/AM bit is disregarded, and the bit will always read "0"." 写入时该位被丢弃，读取时无论寄存器内容如何都读出 0。

**芯片被取消选中时 TEST 清除**，在 RESET 置位的情况下写入 CF 也会清除它。

**STOP 在计数器更新到当前之后生效。** 对 CF 的写入先让时钟追上时间，再存入新的位，因此停止之前经过的时间会被保留。

## 录制结果解决的问题

手册对这些只字未提。它在这方面唯一的一句话是 "Do not set impossible values to prevent the possibility of clock malfunction."

**月份为零时是一个 30 天的月。** 计数器在计数前把月份减一，使用无符号 32 位运算。零变成 4,294,967,295，月份长度由该数模 12 得出，落在一个 30 天的月上，然后进入同一年的一月。

**超出范围的字段会被清零，而不是归约。** 分钟为 100 时进位为 0 并加一小时，因此超出 60 的 40 分钟丢失了。

```python
from snesrtc.calendar import Moment, advance

print(advance(Moment(1996, 0, 30, 23, 59, 59, 0), 1))
print(advance(Moment(1996, 8, 18, 12, 100, 59, 0), 1))
```

```
<1996-01-01 00:00:00 weekday=1>
<1996-08-18 13:00:00 weekday=0>
```

**Epson 时钟在被取消选中时追上时间**，而不是在被选中时。一次会话读到的是上一次会话留下的时间，正如上面的会话示例所示。真实部件连续计数，没有这样的接缝。

**模式码按整个字节比较。** 串行部件只看到四位，所以这是 SPC7110 包装层的性质，没有任何文档描述它。

## 两种芯片

它们是不同厂商的部件，装在不同发行商的卡带上。

| | Sharp S-RTC | Epson RTC-4513 |
|:--|:--|:--|
| 厂商文档 | 未知 | 应用手册，1999 年 |
| 访问地址 | `$2800` 和 `$2801` | `$4840` 至 `$4842`，经由 SPC7110 |
| 形式 | 一个由标记包裹的固定序列 | 一组按地址访问的十六个 4 位寄存器 |
| 获取某一字段 | 读取整个序列并计数 | 指定其寄存器 |
| 星期 | 写入日期时由日期计算得出 | 独立的计数器，0 至 6，不附带任何含义 |
| 年份 | 三位数字加 1000 | 两位数字，任何地方都没有印出世纪 |
| 小时制 | 24 | 12 或 24，由一个控制位选择 |
| 控制寄存器 | 无 | 三个，共有十六个命名位 |
| 追上时间的时机 | 开始读取时 | 芯片被取消选中时 |

<a id="nothing-starts-cleared"></a>

## 没有什么从清零开始

靠电池供电的卡带保存着它原本保存的内容，刚出厂的卡带则保存着硅片上电时的任意状态。Epson 印着 "At power-on, all registers and the STD.P output are undefined."

`Store(seed=UNSET_SEED, cleared=False, held=None)` 根据 `seed` 填充其 20 个字节。`cleared=True` 用零填充，`held` 把字节覆盖在上面，超过 20 时回绕。`read(index)` 和 `write(index, value)` 把索引按 20 回绕，并保留值的低八位。`bytes` 就是列表本身，`stamp` 把字节 16 至 19 作为一个小端序数字读取或写入。`snesrtc.store` 包含 `SIZE`、`STAMP_AT`、`STAMP_BYTES` 和 `UNSET_SEED`。

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

带种子的存储区每次读取都返回相同的字节，种子不同则字节不同，因此测试可以证明程序不依赖它从未写入的内容。需要零的调用方自己请求零，恢复卡带的调用方传入卡带原有的字节。

## 刻意未建模的内容

每一项都是 [`conformance/divergences.json`](conformance/divergences.json) 中的一个条目，附有原因以及什么会改变它。

**没有中断。** CE 从四个周期中选择一个：1/64 秒、1 秒、1 分钟或 1 小时，并驱动 STD.P 引脚。没有文档说明 SPC7110 把该引脚连到超级任天堂程序可以读取的任何地方，因此 CE 不驱动任何引脚，也没有中断到达主机。它对 IRQ-F 的作用已经建模，程序可以在 CD 中读到 IRQ-F。

**没有晶振漂移。** 手册给出 25 摄氏度时为 0 正负 25 ppm，二次温度系数为每摄氏度平方 -0.035 ppm，以及 "At 11.574 ppm, the daily clock error is about one second per day." 这些数值已记录在案。它们界定的是一批模块在某个温度下的范围，而模型无法知道该温度，因此不做模拟。

**30ADJ. 之后没有 125 微秒的锁定。** 该位自行清除，这一点已建模。S1 至 W 不可写入的时间窗口需要比一秒更精细的时间基准，而 `now` 接口不提供这种精度。

## 它是否正确

差分比对用由种子生成的脚本驱动每个部件，把同样的脚本交给一个围绕固定版本 snes9x 源码编译的驱动程序运行，并逐行比较两份记录。

```bash
python3 -m conformance.build
python3 -m conformance.reference
```

```
epson: 200 scripts, 6129 operations compared whole, 1 compared except excused fields, 9772 not compared, 0 disagreed
  fields excused under epson-irqf-not-writable on 1 operations
  not compared past epson-digit-fields-narrower-than-registers, reached by 195 scripts
  not compared past epson-oscillation-flag-cannot-be-originated, reached by 134 scripts
  ...
sharp: 200 scripts, 323500 operations compared whole, 0 compared except excused fields, 155 not compared, 0 disagreed
  not compared past stamp-width-platform-dependent, reached by 2 scripts
```

如果模型在某个字段遵循手册，而录制结果只把该字段当作普通存储，即 CD 中的 IRQ-F 或某种时制固定为 0 的 H10 位，运行器会继续比较，只豁免该字段：该行的其他位仍须一致，这些操作单独计数。其他已声明的分歧会让脚本的比较停在第一个触及它的操作，因为从那一点起，录制结果回答的是手册已经给出不同答案的问题，而且它的状态在之后运算读取的字段上已经不同，所以这些操作单独计数并注明名称。运行器能观察到、却不在 `divergences.json` 中的分歧会使运行失败，运行器在每个脚本上都从该文件读取列表。

Sharp 部件几乎从头到尾都被比较，因为录制结果是它唯一的依据。唯一的排除项与录制程序有关：它用主机 `time_t` 的最大值检查时间戳，因此 64 位构建和 32 位构建在超过 2^31 秒的任何间隔上结果不同。

Epson 脚本的上限为 200 个操作。比较平均在大约 30 个操作后停止，200 个脚本共 6130 个，所以该部件的覆盖率随脚本数量增长，而不是随脚本长度增长。

两个时钟由各自的脚本驱动。在测试框架和录制结果中，它们共用一个 20 字节的存储区，而没有哪个卡带是这样的，因为没有卡带同时搭载这两个部件。时间也由脚本给出，因为参考实现读取的是挂钟时间。参考源码在构建时获取，从不纳入仓库。只有 [`conformance/ref/driver.cpp`](conformance/ref/driver.cpp) 中的驱动程序属于本仓库。

| 命令 | 参数 | 退出码 |
|:--|:--|:--|
| `python3 -m conformance.build` | `--sources DIR`, `--output PATH`, `--pinned FILE`, `--driver-source FILE` | 0 构建成功，1 编译失败，2 参数错误或获取失败 |
| `python3 -m conformance.reference` | `--runs N`，默认 200，`--from N`, `--seed N`, `--length N`，默认 4000，`--driver PATH` | 0 无不一致，1 有不一致或未声明的分歧，2 没有驱动程序或参数错误 |
| `python3 -m conformance.documents` | `--check` 只验证不获取，`--only SUBSTRING` | 0 每个摘要值都匹配，1 有文件被拒绝、没有匹配或参数错误 |
| `python3 -m conformance.quotes` | 无 | 记录中的引文在其文档中找不到或引用核对不通过时为 1，否则为 0，包括磁盘上没有文档的情况 |
| `python3 -m conformance.speed` | 无 | 读取速度超过每秒 500,000 次的下限时为 0，否则为 1 |
| `python3 -m conformance.cartridge CARTRIDGE OUT.json` | 一个卡带镜像和一个输出路径 | 0 已写入，1 未找到时钟例程，2 参数错误或文件不存在 |

失败的脚本可以根据其种子重新生成。`reference.generate(seed, length, part)` 返回操作序列，`reference.render(script)` 返回驱动程序从标准输入读取的文本。

```python
from conformance import reference

script = reference.generate(seed=22, length=4000, part="sharp")
print(len(script), reference.render(script).splitlines()[:4])
```

```
4000 ['time 1000000000', 'store 15 4', 'store 13 2', 'w 10241 12']
```

该脚本先设置时间并配置 Epson 控制寄存器，然后向 `$2801`（即 10241）写入 `0x0C`。

[`conformance/cartridge.json`](conformance/cartridge.json) 记录了《Tengai Makyou Zero》的时钟例程写入该部件的内容，这些内容是在不运行程序的情况下从程序中读出的：五次对控制寄存器的常量写入，其中包括把 CF 设为 `0x07` 再设为 `0x04`，以及把 CD 设为 `0x06`。该文件保存的是镜像的摘要值，不含镜像的任何字节。

## 参与开发

| 需求 | 位置 |
|:--|:--|
| 每项门禁检查及其运行顺序 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 面向编码代理的相同内容 | [AGENTS.md](AGENTS.md) |
| 本仓库与同系列其他仓库共享的标准 | [FAMILY.md](FAMILY.md) |
| 尚未解决的问题，以及什么能解决它们 | [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) |
| 缺陷报告 | [GitHub Issues](https://github.com/gufranco/snes-rtc-python/issues) |
| 安全报告 | [SECURITY.md](SECURITY.md) |
| 行为准则 | [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) |

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

每个模块旁边都有一个以其命名的测试文件，每个测试文件都能单独运行。覆盖率是一项硬性门禁检查，要求 100% 语句与分支覆盖，mypy 以严格模式运行。

不要通过修改模型去迎合录制结果来解决分歧。如果手册有误，请说明原因并给出页码。新的不一致需要在 `divergences.json` 中添加一个条目，写明什么能解决它，否则差分比对会失败。

## 参考资料

- *Application Manual: Real Time Clock Module RTC-4513*，Seiko Epson，1999 年 12 月 1 日。18 页，509,740 字节，SHA-256 `409b8a5a3030fe432dd7dafbf4719944abac890cc5cbebbf96fb8313f9caca33`。这是一份没有文本层的传真件，因此对它的引用通过渲染页面来核对。
- *RTC-4513 catalogue extract*，Seiko Epson，未注明日期。2 页，701,040 字节，SHA-256 `6496eb35fddc181d4e80832b98b8a45163bf5370eadd1e58002aefc83f12edcf`。它印有同样的十六行寄存器表。
- snes9x 的 `srtcemu.cpp` 和 `spc7110emu.cpp` 及其头文件，提交 `2971061cf07fdc6fc7d18883edf4e648eb16a6d2`，https://github.com/snes9xgit/snes9x ，固定在 [`conformance/pinned.json`](conformance/pinned.json) 中。两个部件都与之比对的参考实现。在构建时获取，从不纳入仓库。

两份 Epson 文档都不可再分发，也不在本仓库中。[`conformance/documents.json`](conformance/documents.json) 记录了每份文档的摘要值、大小和地址，`python3 -m conformance.documents` 把它们获取到 git 忽略的 `docs/` 中，并拒绝摘要值不匹配的任何文件。

## 引用本项目

[CITATION.cff](CITATION.cff) 在每次发布时由写入包版本号的脚本更新。

## 许可证

MIT。参见 [LICENSE](LICENSE)。snes9x 源码是一个独立的作品，适用其自身的许可证，在构建时获取，从不在此处再分发。
