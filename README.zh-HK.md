# SNES 卡帶時鐘

Sharp S-RTC 與 Epson RTC-4513，即 Super Nintendo 卡帶可搭載的兩款實時時鐘，以 Python 實現；Epson 部件以 Seiko Epson 的應用手冊為準，兩者均以一個固定版本的 snes9x 建置為準。

[English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-Hans.md) | 繁體中文（香港）

[![CI](https://github.com/gufranco/snes-rtc-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/snes-rtc-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/snes-rtc-python)](https://github.com/gufranco/snes-rtc-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**2** 個時鐘，**329,630** 次操作與參照實現比對，**0** 處不一致，**15** 處手冊與該參照實現不同之處，每處均有記錄，**1,011** 個測試，**100%** 語句及分支覆蓋率，無任何依賴

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

此示例在一個清零的儲存區上建立 Sharp 時鐘，並交給它一個由示例控制的時間來源。命令 `0E` 後接 `00` 開始寫入，十二個數字設定 1996 年 8 月 18 日 12:30:00，秒先寫。晶片自行算出第十三個數字，即星期，該日為星期日，故為 0。命令 `0D` 開始讀取。把時間來源向前撥 95 秒並讀取十五次，返回 `F` 標記、同一日期的 12:31:35、星期，然後再次返回標記。

## 安裝

| 需求 | 版本 |
|:--|:--|
| Python | 3.12 或更新 |
| git | 任何版本，用於複製儲存庫 |
| C++17 編譯器，`g++` | 僅用於建置差分比對所用的參照實現 |

```bash
git clone https://github.com/gufranco/snes-rtc-python.git
cd snes-rtc-python
python3 snesrtc/doctor.py
```

套件只匯入標準庫內的模組。`pip install git+https://github.com/gufranco/snes-rtc-python.git` 會安裝套件但不含一致性測試套件，並新增 `snesrtc-doctor` 命令。

診斷腳本檢查機器與檢出的程式碼，驅動兩個時鐘，最後輸出一行。套件的每項檢查都通過時以 0 退出，有一項不通過時以 1 退出。提交錯誤報告時請貼上其完整輸出。

```
  8 checks, nothing to report
```

發佈版本遵循[語義化版本](https://semver.org/)，由 semantic-release 根據提交歷史生成。每個版本都有標籤，並列於[發佈頁面](https://github.com/gufranco/snes-rtc-python/releases)。

## 介面

`snesrtc.Chip(model, store=None, now=..., open_bus=0x00)` 建立一個時鐘。`model` 為必填。`store` 是一個 `Store`，若省略，時鐘會建立一個帶種子的儲存區。`now` 是返回整數秒的可呼叫物件，時鐘保留其低 32 位元；預設讀取 `time.time()`。`open_bus` 只有 Sharp 部件接受，是它在不屬於自己的位址上返回的值。Epson 部件在該處返回 `0x00`。

| 型號 | 別名 | 位址 | 年份 | 小時制 |
|:--|:--|:--|:--|:--|
| `s-rtc` | `srtc`、`sharp`、`sharprtc` | `$2800` 數據，`$2801` 控制 | 三位數字加 1000，即 1000 至 1999 | 24 |
| `rtc-4513` | `rtc4513`、`epson`、`epsonrtc`、`spc7110`、`spc7110rtc` | `$4840` 啟用，`$4841` 數據，`$4842` 狀態 | 兩位數字，讀作 1990 至 2089 | 12 或 24，由一個控制位元選擇 |

名稱不分大小寫，空格、連字號和底線都會被忽略。缺少名稱或名稱未知時拋出 `UnknownModelError`，其訊息列出可接受的名稱。

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

### 兩個時鐘都支援的呼叫

| 呼叫 | 效果 |
|:--|:--|
| `read(address)` | 從卡帶匯流排讀取一個位元組 |
| `write(address, value)` | 向卡帶匯流排寫入一個位元組。無返回值 |
| `reset()` | 主機重設時的行為。Sharp 部件回到讀取的起點，並把時間更新至當前。Epson 部件被取消選取，回到暫存器 0 的寫入模式，啟用與狀態均清零。儲存區不受影響。返回該時鐘 |

| 屬性 | 含義 |
|:--|:--|
| `model` | 正式型號名稱 |
| `store` | 時鐘用來計數的 `Store` |
| `now` | 時間來源 |

### 模組內容

| 名稱 | 內容 |
|:--|:--|
| `snesrtc.MODELS` | 兩個 `Model` 記錄，以正式名稱為鍵 |
| `snesrtc.Model` | 一個包含 `name`、`summary`、`addresses`、`protocol` 和 `aliases` 的記錄，以及 `Chip` 所呼叫的 `build(store=None, **options)` |
| `snesrtc.models.lookup(name)` | 任何拼寫所對應的 `Model`。可拋出 `UnknownModelError` |
| `snesrtc.Store(seed=UNSET_SEED, cleared=False, held=None)` | 卡帶以電池保存的 20 個位元組。見[初始狀態並非清零](#nothing-starts-cleared) |
| `snesrtc.Built` | `Chip` 返回的類型，即 `epson.Chip` 或 `sharp.Chip` |
| `snesrtc.UnknownModelError` | 套件唯一會拋出的錯誤，用於缺少或未知的型號名稱。定義於 `snesrtc.errors` |
| `snesrtc.__version__` | 已安裝的版本 |
| `snesrtc.sharp`、`snesrtc.epson` | 各部件的 `Chip` 類別、位址、命令代碼及暫存器常數 |
| `snesrtc.store` | `Store` 及其常數 `SIZE`、`STAMP_AT`、`STAMP_BYTES` 和 `UNSET_SEED` |
| `snesrtc.calendar` | 兩個部件共用的日曆運算 |

### Sharp S-RTC

寫入 `$2801` 會驅動一個狀態機。只讀取值的低四位元。

| 寫入 `$2801` | 效果 |
|:--|:--|
| `0D` | 開始讀取。下一次讀取 `$2800` 會把時間更新至當前，並返回 `0F` 標記 |
| `0E` | 等待命令 |
| `0E`，然後 `00` | 開始寫入。接下來的十二次寫入為各個數字，晶片計算第十三個數字，即星期 |
| `0E`，然後 `04` | 將全部十三個數字清為 0 |
| `0E`，然後任何其他值 | 停止。直至下一個 `0D` 或 `0E` 之前，寫入均被忽略 |
| `0F` | 忽略 |

讀取序列為 `0F` 標記、十三個數字，再次為標記，之後從頭開始。不在讀取狀態時，`$2800` 返回 `0x00`。

| 儲存區位元組 | 數字 |
|:--|:--|
| 0, 1 | 秒，先個位後十位 |
| 2, 3 | 分 |
| 4, 5 | 時 |
| 6, 7 | 日 |
| 8 | 月，一個數字，取值 1 至 12 |
| 9, 10, 11 | 年份減 1000，依次為個位、十位、百位 |
| 12 | 星期，星期日為 0，自 1900 年 1 月 1 日星期一起計算 |
| 16 至 19 | 儲存區上次更新至當前的時間，低位元組在前 |

| 屬性或呼叫 | 含義 |
|:--|:--|
| `mode` | `"read"`、`"command"`、`"write"` 或 `"ready"` |
| `index` | 序列中的下一個數字，標記之前為 -1 |
| `open_bus` | 不屬於該部件的位址所讀出的值 |
| `read_moment()`、`store_moment(moment)` | 以 `calendar.Moment` 表示的十三個數字，以及反向轉換 |
| `elapsed()` | 自位元組 16 至 19 中的時間戳記起經過的秒數。超過 2^31 的差距讀作 0 |
| `update()` | 將數字推進 `elapsed()` 秒並重新加上時間戳記 |
| `command(value)`、`accept(value)` | `write` 在命令位元組之後的兩個部分 |

`snesrtc.sharp` 包含 `DATA`、`CONTROL`、`MARKER`、`LAST_INDEX`、`COMMAND_READ`、`COMMAND_BEGIN`、`COMMAND_NOTHING`、`COMMAND_WRITE`、`COMMAND_CLEAR`、`YEAR_BASE` 和 `STAMP_LIMIT`，以及四個 `mode` 值 `READING`、`COMMAND`、`WRITING` 和 `READY`。

### Epson RTC-4513

SPC7110 把該部件的三線串列介面轉為三個卡帶位址。程式以會話方式與它通訊。

| 步驟 | 匯流排存取 | 效果 |
|:--|:--|:--|
| 選取 | 寫入 `$4840`，位元 0 設為 1 | 狀態變為 `0x80`。部件等待模式 |
| 模式 | 向 `$4841` 寫入 `0x03` 或 `0x0C` | 寫入模式或讀取模式。其他值均被忽略 |
| 暫存器 | 向 `$4841` 寫入 0 至 15 | 下一次存取的起始暫存器 |
| 數據 | 寫入或讀取 `$4841` | 一個半位元組。之後暫存器索引加一，超過 15 後回繞 |
| 取消選取 | 寫入 `$4840`，位元 0 清零 | 把計數器更新至當前，清除讀取旗標並清除 TEST |
| 狀態 | 讀取 `$4842` | 任何存取後為 `0x80`，之後直至下一次存取為 `0x00` |

讀取 `$4840` 返回最後寫入該處的值。讀取 CD 會清除 IRQ-F。

| 暫存器 | 索引 | D3 | D2 | D1 | D0 | 計數範圍 |
|:--|:--|:--|:--|:--|:--|:--|
| `S1` | 0 | s8 | s4 | s2 | s1 | 0 至 9 |
| `S10` | 1 | fo | s40 | s20 | s10 | 0 至 5 |
| `MI1` | 2 | mi8 | mi4 | mi2 | mi1 | 0 至 9 |
| `MI10` | 3 | fr | mi40 | mi20 | mi10 | 0 至 5 |
| `H1` | 4 | h8 | h4 | h2 | h1 | 0 至 9 |
| `H10` | 5 | fr | PM/AM | h20 | h10 | 0 至 2 |
| `D1` | 6 | d8 | d4 | d2 | d1 | 0 至 9 |
| `D10` | 7 | fr | 空閒 RAM | d20 | d10 | 0 至 3 |
| `MO1` | 8 | mo8 | mo4 | mo2 | mo1 | 0 至 9 |
| `MO10` | 9 | fr | 空閒 RAM | 空閒 RAM | mo10 | 0 至 1 |
| `Y1` | 10 | y8 | y4 | y2 | y1 | 0 至 9 |
| `Y10` | 11 | y80 | y40 | y20 | y10 | 0 至 9 |
| `W` | 12 | fr | w4 | w2 | w1 | 0 至 6 |
| `CD` | 13 | 30ADJ. | IRQ-F | CAL/HW | HOLD | |
| `CE` | 14 | t1 | t0 | INT/STND | MASK | |
| `CF` | 15 | TEST | 24/12 | STOP | RESET | |

`snesrtc.epson` 以索引命名每個暫存器，由 `S1` 至 `CF`，並以遮罩命名每個控制位元：CD 中的 `HOLD`、`CAL_HW`、`IRQ_F` 和 `ADJUST`，CF 中的 `RESET`、`STOP`、`HOURS_24` 和 `TEST`，以及 CE 中的 `MASK` 和 `INT_STND`。它還包含 `ENABLE`、`DATA`、`STATUS`、`WRITE_MODE`、`READ_MODE`、`READY`、`REGISTERS`、`DIGIT_MASK`、`OSC_FLAG`、`READ_FLAG`、`READ_FLAG_AT`、`CALENDAR_READ_FLAG_AT`、`PM`、`H20`、`STOPPED`、`NIBBLE`、`HALF_MINUTE`、`MINUTE`、`HOUR`、`WHOLE_SECONDS_PER_PERIOD`、`PERIOD_SHIFT`、`PERIOD_BITS`、`NOON`、`YEAR_PIVOT` 和 `STAMP_LIMIT`，以及五個 `state` 值 `INACTIVE`、`MODE_SELECT`、`INDEX_SELECT`、`READING` 和 `WRITING`。

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

每行依次為 W、Y10 至 S1：星期 5，99-12-31，23:59:50。十五秒後，第一次讀取仍顯示舊時間，因為部件在取消選取時才追上時間。再下一次讀取顯示星期 6，00-01-01，00:00:05。

| 屬性或呼叫 | 含義 |
|:--|:--|
| `state` | `"inactive"`、`"mode"`、`"index"`、`"read"` 或 `"write"` |
| `mode` | `0x03` 或 `0x0C`，即最後選擇的模式 |
| `index` | 下一次數據存取所到達的暫存器 |
| `enable`、`status` | 最後寫入 `$4840` 的值，以及狀態位元組 |
| `moment()`、`store_moment(moment)` | 以 `calendar.Moment` 表示的暫存器 S1 至 W，以及反向轉換。只有在 CAL/HW 已設定時才會儲存日期 |
| `hour()`、`store_hour(hour)` | 0 至 23 的小時，以 CF 所選的記法讀取或寫入 |
| `digit(index)`、`put_digit(index, value)` | 只處理暫存器的數字位元，不改動其旗標位元 |
| `twenty_four_hour()`、`dated()`、`stopped()` | 24/12 是否已設定、CAL/HW 是否已設定，以及 RESET 或 STOP 是否已設定 |
| `elapsed(current)` | 由時間戳記至 `current` 的秒數。超過 2^31 的差距讀作 0 |
| `update(offset=0)` | 除非 HOLD 已設定，否則將計數器推進至 `now() - offset`，若已過去至少一秒則設定讀取旗標 |
| `set_read_flag()`、`clear_read_flag()` | 在帶有 fr 的五個暫存器中設定或清除 fr |
| `read_data()`、`write_enable(value)`、`write_data(value)` | 讀取 `$4841`、寫入 `$4840` 及寫入 `$4841` 時的行為 |
| `write_register(value)`、`write_control_d(value)`、`write_control_f(value)` | 對當前暫存器的數據寫入，以及兩個在寫入時生效的控制暫存器 |
| `release_hold()`、`adjust_to_nearest_minute()` | 清除 HOLD 及設定 30ADJ. 時的行為 |

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

選取後，狀態只有一次讀出 `0x80`。寫入 CD 時除了 CAL/HW，還設定了 30ADJ. 與 IRQ-F。IRQ-F 不會被儲存，30ADJ. 把 40 秒進位至下一分鐘並自行清除。TEST 由寫入 CF 設定，並由取消選取清除。

### 日曆

`snesrtc.calendar` 包含兩個部件追上時間時所執行的運算。

| 名稱 | 內容 |
|:--|:--|
| `Moment(year, month, day, hour, minute, second, weekday)` | 時鐘的一次讀數。按值比較及計算雜湊 |
| `advance(moment, seconds)` | `seconds` 秒後的時刻，計算方式與參照實現相同 |
| `is_leap(year)` | 格里曆規則 |
| `days_in(year, month)` | 28 至 31。1 至 12 以外的月份按模 12 化簡 |
| `weekday(year, month, day)` | 星期日為 0，自 1900 年 1 月 1 日星期一起計算 |
| `MONTHS`、`EPOCH_YEAR`、`EPOCH_WEEKDAY`、`WEEK`、`DAY`、`MASK` | 它們背後的常數 |

```python
from snesrtc.calendar import Moment, advance, days_in, is_leap, weekday

print(advance(Moment(1999, 12, 31, 23, 59, 59, 5), 1))
print(is_leap(1900), is_leap(2000), days_in(1996, 2), weekday(1996, 8, 18))
```

```
<2000-01-01 00:00:00 weekday=6>
False True 29 0
```

### 診斷腳本

| 命令 | 退出碼 |
|:--|:--|
| 在儲存庫根目錄執行 `python3 snesrtc/doctor.py` | 套件的每項檢查都通過時為 0，有一項不通過時為 1 |
| 以 pip 安裝後執行 `snesrtc-doctor` | 相同 |

它不接受參數。它先報告機器：直譯器、編碼、檔案系統大小寫、行尾、路徑長度、可用空間和 git。這些行僅供參考，從不改變退出碼。然後檢查套件：Python 版本、兩個時鐘的建立與重設、給定固定時間的時鐘能否讀回該時間、`$2802` 是否讀作開路匯流排、[`conformance/pinned.json`](conformance/pinned.json) 中的固定版本，以及參照驅動程式是否已建置。拋出例外的檢查會連同例外的類型和訊息一併報告。

## 每個答案的來源

兩個時鐘依據的證據不同。

| 層級 | 來源 | 決定 |
|:--|:--|:--|
| 1 | Seiko Epson，*Application Manual: Real Time Clock Module RTC-4513* | Epson 就 RTC-4513 印出的一切：暫存器寬度、計數範圍、每個控制位元的作用、會話的結構、上電後的狀態 |
| 2 | snes9x 的一份錄製，以提交固定 | 手冊未涉及的部分：SPC7110 如何把三線串列部件轉為三個卡帶位址、計數器在文件記載範圍以外的行為，以及 Sharp 部件的全部 |
| 3 | 別無其他 | 無 |

層級 1 的每個數值都記錄在 [`conformance/hardware.json`](conformance/hardware.json) 中，附有其出處的句子、文件的摘要值和閱讀日期。[`conformance/hardware.test.py`](conformance/hardware.test.py) 驅動套件，並據此檢查其行為。

手冊與錄製不一致時，套件依從手冊。15 處分歧各自是 [`conformance/divergences.json`](conformance/divergences.json) 中的一個條目，寫明文件所述、錄製的行為、套件依從哪一方，以及什麼證據可以定案。

### Sharp 部件沒有數據手冊

`S-RTC` 是 Nintendo 的部件編號，與 `S-DSP`、`S-SMP` 和 `S-PPU` 屬同一風格，並非 Sharp 的目錄型號。目前未知有任何製造商文件。日期為 2026-08-20 的搜尋記錄在 `hardware.json` 的 `"verified": false` 之下，並附有三項可以定案的發現：Sharp 數據彙編中的條目、顯示目錄型號的晶片裸片照片，或 Daikaijuu Monogatari II 驅動時鐘時的匯流排邏輯擷取。一個測試斷言該區塊仍如此記載。

## 手冊決定的事項

**十三個時鐘暫存器中，有六個所載的數字比暫存器窄。** 計數範圍一欄顯示了這點：S10 和 MI10 止於 5，H10 止於 2，D10 止於 3，MO10 止於 1，W 止於 6。多出的位元是振盪旗標、讀取旗標、PM/AM 位元，以及程式可使用的空閒 RAM。`epson.DIGIT_MASK` 把它們分開，因此程式儲存的旗標永遠不會被讀回作為日期的一部分。

**HOLD 不會停止時鐘。** 手冊說「The clock continues to run」，並說 HOLD 設定期間錯過的第一次遞增「is compensated for when the hold condition is released (+1 second).」釋放 HOLD 會加一秒，而手冊中設定時鐘的程序亦警告寫入必須在一秒內完成。

**沒有控制位元會加一秒。** CD 位元 1 是 CAL/HW。清零時，它關閉日期計數器，令這些暫存器作為 RAM 使用。D10 和 MO10 中的讀取旗標亦一樣：CAL/HW 清零期間，時間前進或取消選取晶片都不會改動它們。唯一有文件記載的軟件調整，是 CD 位元 3 上的 30ADJ. 位元。

**十二小時制是上電時的狀態。** 手冊：「At power-on, all registers and the STD.P output are undefined.」上電時全為零的暫存器組中，24/12 為清零，即十二小時制，CAL/HW 亦為清零，日期因而停止。

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

在 11:59:59 PM 過了一秒。小時變為 12 且 PM 清零，即午夜。星期計數器由 0 變為 1，而日仍停在 1，因為 CAL/HW 為清零。

**IRQ-F 不能寫入。** 手冊：「A write instruction for the IRQ-F bit is not executed.」CE 的 INT/STND 已設定時，t1 和 t0 所選位數的進位會設定它，讀取 CD 會清除它。MASK 設定期間它讀出 0，設定 MASK 亦會清除已設定的旗標。固定週期模式下旗標只維持 7.8 ms，短於模型計算的一秒，所以在該模式下不會設定。

**每種時制都把 H10 的一個位元固定為 0。** 十二小時制：「The h20 bit cannot be written and is fixed to "0".」二十四小時制：「A write attempt to the PM/AM bit is disregarded, and the bit will always read "0".」寫入時該位元被捨棄，讀取時不論暫存器內容都讀出 0。

**取消選取晶片時 TEST 會清除**，在 RESET 已設定時寫入 CF 也會清除它。

**STOP 在計數器更新至當前之後才生效。** 寫入 CF 會先讓時鐘追上時間，然後才儲存新的位元，因此停止前經過的時間得以保留。

## 錄製決定的事項

手冊未有提及這些事項。它在這方面唯一的一句是「Do not set impossible values to prevent the possibility of clock malfunction.」

**月份為零時是一個 30 日的月份。** 計數器在計數前先把月份減一，使用無號 32 位元運算。零變成 4,294,967,295，月份長度由此數模 12 取得，結果落在一個 30 日的月份上，並滾入同一年的一月。

**超出範圍的欄位會被清零，而非化簡。** 分鐘為 100 時進位為 0 並加一小時，因此超出 60 的 40 分鐘會遺失。

```python
from snesrtc.calendar import Moment, advance

print(advance(Moment(1996, 0, 30, 23, 59, 59, 0), 1))
print(advance(Moment(1996, 8, 18, 12, 100, 59, 0), 1))
```

```
<1996-01-01 00:00:00 weekday=1>
<1996-08-18 13:00:00 weekday=0>
```

**Epson 時鐘在取消選取時追上時間**，而非在選取時。一次會話讀到的時間是上一次會話留下的狀態，如上方的會話示例所示。真實部件持續計數，沒有這種接縫。

**模式代碼以整個位元組比較。** 串列部件只會看到四個位元，因此這是 SPC7110 包裝層的屬性，沒有任何文件描述它。

## 兩款晶片

它們是不同製造商的部件，裝在不同發行商的卡帶上。

| | Sharp S-RTC | Epson RTC-4513 |
|:--|:--|:--|
| 製造商文件 | 未知有任何文件 | 應用手冊，1999 年 |
| 存取位置 | `$2800` 和 `$2801` | `$4840` 至 `$4842`，經由 SPC7110 |
| 結構 | 包在標記中的固定序列 | 由十六個 4 位元暫存器組成、可按位址存取的暫存器組 |
| 取得單一欄位 | 讀取整個序列並計數 | 指定其暫存器 |
| 星期 | 寫入日期時由日期計算 | 獨立的計數器，0 至 6，不附帶任何含義 |
| 年份 | 三位數字加 1000 | 兩位數字，任何地方都沒有印出世紀 |
| 小時制 | 24 | 12 或 24，由一個控制位元選擇 |
| 控制暫存器 | 無 | 三個，共十六個具名位元 |
| 追上時間 | 讀取開始時 | 晶片被取消選取時 |

<a id="nothing-starts-cleared"></a>

## 初始狀態並非清零

由電池供電的卡帶保存它原有的內容，而剛出廠的卡帶保存的是矽晶片上電時的任何狀態。Epson 印明「At power-on, all registers and the STD.P output are undefined.」

`Store(seed=UNSET_SEED, cleared=False, held=None)` 由 `seed` 填充其 20 個位元組。`cleared=True` 以零填充，`held` 則把位元組覆蓋在上面，超過 20 時回繞。`read(index)` 和 `write(index, value)` 把索引按 20 回繞，並保留值的低八位元。`bytes` 就是該列表本身，`stamp` 把位元組 16 至 19 作為一個小端序數字讀取或寫入。`snesrtc.store` 包含 `SIZE`、`STAMP_AT`、`STAMP_BYTES` 和 `UNSET_SEED`。

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

帶種子的儲存區每次讀取都保存相同的位元組，不同種子則有不同的位元組，因此測試可以證明程式並不依賴它從未寫入的內容。需要零的呼叫者須明確要求，而還原卡帶的呼叫者則傳入卡帶原有的位元組。

## 刻意不模擬的部分

每項都是 [`conformance/divergences.json`](conformance/divergences.json) 中的一個條目，附有原因及什麼會改變它。

**沒有中斷。** CE 選擇四個週期之一：1/64 秒、1 秒、1 分鐘或 1 小時，並驅動 STD.P 引腳。沒有文件說明 SPC7110 把該引腳接到 Super Nintendo 程式可以讀取的任何地方，因此 CE 不驅動任何引腳，亦沒有中斷到達主機。它對 IRQ-F 的作用則有建模，程式可在 CD 中讀到 IRQ-F。

**沒有晶體漂移。** 手冊給出 25 攝氏度時為 0 加減 25 ppm，二次溫度係數為每攝氏度平方 -0.035 ppm，以及「At 11.574 ppm, the daily clock error is about one second per day.」這些數值已在記錄中。它們界定的是一批模組在某個溫度下的範圍，而模型無法得知該溫度，因此不作模擬。

**30ADJ. 之後沒有 125 微秒的鎖定期。** 該位元會自行清除，這點有模擬。S1 至 W 不能寫入的時間窗需要比一秒更細的時基，而 `now` 介面並不提供。

## 它是否正確

差分測試以由種子生成的腳本驅動每個部件，讓同樣的腳本通過以固定版本 snes9x 原始碼編譯的驅動程式，並逐行比對兩份記錄。

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

若模型在某個欄位依從手冊，而錄製只把該欄位當作普通儲存，即 CD 中的 IRQ-F 或某種時制固定為 0 的 H10 位元，執行器會繼續比對，只豁免該欄位：該行其他位元仍須一致，這些操作另行計數。其他已聲明的分歧則令腳本的比對停在第一個觸及它的操作，因為過了這一點，錄製回答的是手冊已給出不同答案的問題，而其狀態在之後運算會讀取的欄位上已不同，因此這些操作會另行計數並列名。執行器能觀察到但不在 `divergences.json` 中的分歧會使該次執行失敗，而執行器在每個腳本上都會從該檔案讀取清單。

Sharp 部件幾乎從頭到尾都有比對，因為錄製是它唯一的依據。唯一的排除與錄製器有關：它把時間戳記與主機 `time_t` 的最大值比較，因此 64 位元與 32 位元的建置在任何超過 2^31 秒的差距上結果不同。

Epson 腳本上限為 200 個操作。比對平均在約 30 個操作後停止，200 個腳本合共 6130 個，因此該部件的覆蓋率隨腳本數量而非長度增長。

兩個時鐘由不同的腳本驅動。在測試框架和錄製中，它們共用一個 20 位元組的儲存區，而實際上沒有卡帶如此，因為沒有卡帶同時搭載兩個部件。時間也由腳本設定，因為參照實現讀取的是掛鐘時間。參照原始碼在建置時取得，從不納入儲存庫。只有 [`conformance/ref/driver.cpp`](conformance/ref/driver.cpp) 中的驅動程式屬於此儲存庫。

| 命令 | 參數 | 退出碼 |
|:--|:--|:--|
| `python3 -m conformance.build` | `--sources DIR`、`--output PATH`、`--pinned FILE`、`--driver-source FILE` | 0 已建置，1 編譯失敗，2 參數錯誤或取得失敗 |
| `python3 -m conformance.reference` | `--runs N`，預設 200，`--from N`、`--seed N`、`--length N`，預設 4000，`--driver PATH` | 0 無不一致，1 有不一致或未聲明的分歧，2 無驅動程式或參數錯誤 |
| `python3 -m conformance.documents` | `--check` 只驗證不下載，`--only SUBSTRING` | 0 每個摘要值都相符，1 有一個被拒絕、全部不相符或參數錯誤 |
| `python3 -m conformance.quotes` | 無 | 記錄中的引文在其文件中找不到或引用核對不符時為 1，否則為 0，包括磁碟上沒有任何文件時 |
| `python3 -m conformance.speed` | 無 | 讀取速度高於每秒 500,000 次的下限時為 0，否則為 1 |
| `python3 -m conformance.cartridge CARTRIDGE OUT.json` | 一個卡帶映像檔及一個輸出路徑 | 0 已寫入，1 找不到時鐘例程，2 參數錯誤或檔案不存在 |

失敗的腳本可從其種子重新生成。`reference.generate(seed, length, part)` 返回操作，`reference.render(script)` 返回驅動程式從標準輸入讀取的文字。

```python
from conformance import reference

script = reference.generate(seed=22, length=4000, part="sharp")
print(len(script), reference.render(script).splitlines()[:4])
```

```
4000 ['time 1000000000', 'store 15 4', 'store 13 2', 'w 10241 12']
```

該腳本先設定時間並配置 Epson 控制暫存器，然後向 `$2801` 寫入 `0x0C`，即 10241。

[`conformance/cartridge.json`](conformance/cartridge.json) 記錄了 Tengai Makyou Zero 的時鐘例程寫入該部件的內容，這是在不執行程式的情況下從程式中讀出的：五次對控制暫存器的常數寫入，其中包括把 CF 設為 `0x07` 再設為 `0x04`，以及把 CD 設為 `0x06`。該檔案保存映像檔的摘要值，不含映像檔的任何位元組。

## 參與開發

| 需要 | 位置 |
|:--|:--|
| 所有關卡檢查及其執行順序 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 供程式編寫代理使用的同一份資料 | [AGENTS.md](AGENTS.md) |
| 此儲存庫與同系列其他儲存庫共用的標準 | [FAMILY.md](FAMILY.md) |
| 尚未定案的事項，以及什麼可以定案 | [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) |
| 錯誤報告 | [GitHub Issues](https://github.com/gufranco/snes-rtc-python/issues) |
| 保安報告 | [SECURITY.md](SECURITY.md) |
| 行為準則 | [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) |

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

每個模組旁邊都有一個以其命名的測試檔案，各自可單獨執行。覆蓋率是 100% 語句及分支的硬性關卡，mypy 以嚴格模式執行。

不要通過修改模型以配合錄製來解決分歧。若手冊有誤，請說明原因並註明頁碼。新的不一致需要在 `divergences.json` 中有一個寫明什麼可以定案的條目，否則差分測試會失敗。

## 參考資料

- *Application Manual: Real Time Clock Module RTC-4513*，Seiko Epson，1999 年 12 月 1 日。18 頁，509,740 位元組，SHA-256 `409b8a5a3030fe432dd7dafbf4719944abac890cc5cbebbf96fb8313f9caca33`。這是沒有文字層的傳真文件，因此引用其中內容時以渲染頁面來核對。
- *RTC-4513 catalogue extract*，Seiko Epson，無日期。2 頁，701,040 位元組，SHA-256 `6496eb35fddc181d4e80832b98b8a45163bf5370eadd1e58002aefc83f12edcf`。它印有同一份十六行的暫存器表。
- snes9x，`srtcemu.cpp` 和 `spc7110emu.cpp` 及其標頭檔，位於提交 `2971061cf07fdc6fc7d18883edf4e648eb16a6d2`，https://github.com/snes9xgit/snes9x ，固定於 [`conformance/pinned.json`](conformance/pinned.json)。兩個部件都與之比對的參照實現。於建置時取得，從不納入儲存庫。

兩份 Epson 文件都不可再分發，也不在此儲存庫中。[`conformance/documents.json`](conformance/documents.json) 記載每份文件的摘要值、大小和地址，`python3 -m conformance.documents` 會把它們下載到 git 忽略的 `docs/`，並拒絕任何摘要值不相符的檔案。

## 引用本專案

[CITATION.cff](CITATION.cff) 會在每次發佈時，由寫入套件版本的腳本更新。

## 授權

MIT。見 [LICENSE](LICENSE)。snes9x 原始碼是另一項作品，受其自身授權約束，於建置時取得，從不在此再分發。
