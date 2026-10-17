# SNESカートリッジの時計

スーパーファミコンのカートリッジが搭載できた2つのリアルタイムクロック、シャープのS-RTCとエプソンのRTC-4513をPythonで実装したものです。エプソンのチップはセイコーエプソンのアプリケーションマニュアルに、両方のチップはピン留めしたsnes9xのビルドに合わせています。

[English](README.md) | 日本語 | [简体中文](README.zh-Hans.md) | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/snes-rtc-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/snes-rtc-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/snes-rtc-python)](https://github.com/gufranco/snes-rtc-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

時計**2**種、リファレンスと比較した操作**329,630**件、不一致**0**件、マニュアルとそのリファレンスが食い違う箇所**15**件、それぞれ記録済み、テスト**974**件、命令と分岐のカバレッジ**100%**、依存関係なし

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

この例では、ゼロで埋めたストアの上にシャープの時計を作り、こちらで制御する時刻源を渡しています。コマンド`0E`に続けて`00`を書くと書き込みが始まり、12桁で1996年8月18日12:30:00を秒から順に設定します。13桁目の曜日はチップが計算し、この日は日曜日なので0になります。コマンド`0D`で読み出しが始まります。時刻源を95秒進めて15回読むと、`F`マーカー、同じ日付の12:31:35、曜日、そして再びマーカーが返ります。

## インストール

| 必要なもの | バージョン |
|:--|:--|
| Python | 3.12以降 |
| git | 任意。クローン用 |
| C++17コンパイラ、`g++` | 差分テストが比較に使うリファレンスをビルドする場合のみ |

```bash
git clone https://github.com/gufranco/snes-rtc-python.git
cd snes-rtc-python
python3 snesrtc/doctor.py
```

このパッケージは標準ライブラリ以外を何もインポートしません。`pip install git+https://github.com/gufranco/snes-rtc-python.git`を実行すると、適合性テストスイートを除いてインストールされ、`snesrtc-doctor`コマンドが追加されます。

ドクターはマシンとチェックアウトを確認し、両方の時計を動かして、最後に1行を出力します。パッケージのチェックがすべて通れば0で、1つでも通らなければ1で終了します。バグ報告には出力全体を貼り付けてください。

```
  8 checks, nothing to report
```

リリースは[Semantic Versioning](https://semver.org/)に従い、semantic-releaseがコミット履歴から作成します。各リリースにはタグが付き、[リリースページ](https://github.com/gufranco/snes-rtc-python/releases)に掲載されます。

## インターフェース

`snesrtc.Chip(model, store=None, now=..., open_bus=0x00)`は時計を1つ作ります。`model`は必須です。`store`は`Store`で、省略すると時計がシード付きのストアを作ります。`now`は整数の秒を返す呼び出し可能オブジェクトで、時計はその下位32ビットを保持します。デフォルトは`time.time()`を読みます。`open_bus`はシャープのチップだけが受け付け、自分が担当しないアドレスで返す値です。エプソンのチップはそこで`0x00`を返します。

| モデル | 別名 | アドレス | 年 | 時間 |
|:--|:--|:--|:--|:--|
| `s-rtc` | `srtc`, `sharp`, `sharprtc` | `$2800`データ、`$2801`制御 | 3桁に1000を加算し、1000から1999 | 24 |
| `rtc-4513` | `rtc4513`, `epson`, `epsonrtc`, `spc7110`, `spc7110rtc` | `$4840`イネーブル、`$4841`データ、`$4842`ステータス | 2桁で、1990から2089と解釈 | 12または24。制御ビットで選択 |

名前は大文字小文字を問わず一致し、空白、ハイフン、アンダースコアは無視されます。名前がない場合や未知の名前の場合は`UnknownModelError`が送出され、そのメッセージには受け付ける名前が列挙されます。

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

### 両方の時計が受け付ける呼び出し

| 呼び出し | 効果 |
|:--|:--|
| `read(address)` | カートリッジバスから1バイト |
| `write(address, value)` | カートリッジバスへ1バイト。何も返しません |
| `reset()` | 本体のリセットが行うこと。シャープのチップは読み出しの先頭に戻り、時刻を最新にします。エプソンのチップは選択解除され、レジスタ0で書き込みモードに戻り、イネーブルとステータスがクリアされます。ストアには触れません。時計を返します |

| 属性 | 意味 |
|:--|:--|
| `model` | 正規のモデル名 |
| `store` | 時計が計時に使う`Store` |
| `now` | 時刻源 |

### モジュールの内容

| 名前 | 内容 |
|:--|:--|
| `snesrtc.MODELS` | 2つの`Model`レコード。正規名がキーです |
| `snesrtc.Model` | `name`、`summary`、`addresses`、`protocol`、`aliases`と、`Chip`が呼ぶ`build(store=None, **options)`を持つレコード |
| `snesrtc.models.lookup(name)` | どの綴りに対しても`Model`を返します。`UnknownModelError`を送出します |
| `snesrtc.Store(seed=UNSET_SEED, cleared=False, held=None)` | カートリッジがバッテリーで保持する20バイト。[最初からクリアされているものはない](#nothing-starts-cleared)を参照してください |
| `snesrtc.Built` | `Chip`が返す型。`epson.Chip`または`sharp.Chip` |
| `snesrtc.UnknownModelError` | パッケージが送出する唯一のエラーで、モデル名がない場合や未知の場合に使います。`snesrtc.errors`にあります |
| `snesrtc.__version__` | インストール済みのバージョン |
| `snesrtc.sharp`, `snesrtc.epson` | 各チップの`Chip`クラス、アドレス、コマンドコード、レジスタ定数 |
| `snesrtc.store` | `Store`とその定数`SIZE`、`STAMP_AT`、`STAMP_BYTES`、`UNSET_SEED` |
| `snesrtc.calendar` | 両方のチップが共有する暦の計算 |

### シャープS-RTC

`$2801`への書き込みはステートマシンを動かします。値の下位4ビットだけが読まれます。

| `$2801`への書き込み | 効果 |
|:--|:--|
| `0D` | 読み出しを開始します。次の`$2800`の読み出しで時刻が最新になり、`0F`マーカーが返ります |
| `0E` | コマンドを待ちます |
| `0E`、次に`00` | 書き込みを開始します。続く12回の書き込みが各桁で、13桁目の曜日はチップが計算します |
| `0E`、次に`04` | 13桁すべてを0にクリアします |
| `0E`、次にそれ以外の値 | 停止します。次の`0D`または`0E`まで書き込みは無視されます |
| `0F` | 無視されます |

読み出しシーケンスは`0F`マーカー、13桁、再びマーカーで、その後は最初からやり直します。読み出し中でなければ、`$2800`は`0x00`を返します。

| ストアのバイト | 桁 |
|:--|:--|
| 0, 1 | 秒。一の位、十の位の順 |
| 2, 3 | 分 |
| 4, 5 | 時 |
| 6, 7 | 日 |
| 8 | 月。1桁で1から12を保持 |
| 9, 10, 11 | 年から1000を引いた値。一の位、十の位、百の位の順 |
| 12 | 曜日。日曜日が0で、1900年1月1日月曜日から数えます |
| 16から19 | ストアが最後に最新にされた時刻。下位バイトが先 |

| 属性または呼び出し | 意味 |
|:--|:--|
| `mode` | `"read"`、`"command"`、`"write"`、`"ready"`のいずれか |
| `index` | シーケンス中の次の桁。マーカーの前は-1 |
| `open_bus` | チップが担当しないアドレスを読んだときの値 |
| `read_moment()`, `store_moment(moment)` | 13桁を`calendar.Moment`として取得し、また書き戻します |
| `elapsed()` | バイト16から19のスタンプからの秒数。2^31を超える差は0と読みます |
| `update()` | 桁を`elapsed()`だけ進め、スタンプを更新します |
| `command(value)`, `accept(value)` | コマンドバイト以降の`write`の2つの部分 |

`snesrtc.sharp`には`DATA`、`CONTROL`、`MARKER`、`LAST_INDEX`、`COMMAND_READ`、`COMMAND_BEGIN`、`COMMAND_NOTHING`、`COMMAND_WRITE`、`COMMAND_CLEAR`、`YEAR_BASE`、`STAMP_LIMIT`と、`mode`の4つの値`READING`、`COMMAND`、`WRITING`、`READY`があります。

### エプソンRTC-4513

SPC7110は、このチップの3線式シリアルインターフェースを3つのカートリッジアドレスに変換します。プログラムはセッション単位でこのチップとやり取りします。

| 手順 | バスアクセス | 効果 |
|:--|:--|:--|
| 選択 | ビット0を立てて`$4840`に書き込み | ステータスが`0x80`になります。チップはモードを待ちます |
| モード | `$4841`に`0x03`または`0x0C`を書き込み | 書き込みモードまたは読み出しモード。それ以外の値は無視されます |
| レジスタ | `$4841`に0から15を書き込み | 次のアクセスが始まるレジスタ |
| データ | `$4841`への書き込みまたは読み出し | 1ニブル。その後レジスタ番号が1つ進み、15の次は0に戻ります |
| 選択解除 | ビット0を落として`$4840`に書き込み | カウンタを最新にし、読み出しフラグをクリアし、TESTをクリアします |
| ステータス | `$4842`を読み出し | どのアクセスの後も`0x80`、次のアクセスまでは`0x00` |

`$4840`を読むと、最後に書き込んだ値が返ります。CDを読むとIRQ-Fがクリアされます。

| レジスタ | 番号 | D3 | D2 | D1 | D0 | カウント範囲 |
|:--|:--|:--|:--|:--|:--|:--|
| `S1` | 0 | s8 | s4 | s2 | s1 | 0から9 |
| `S10` | 1 | fo | s40 | s20 | s10 | 0から5 |
| `MI1` | 2 | mi8 | mi4 | mi2 | mi1 | 0から9 |
| `MI10` | 3 | fr | mi40 | mi20 | mi10 | 0から5 |
| `H1` | 4 | h8 | h4 | h2 | h1 | 0から9 |
| `H10` | 5 | fr | PM/AM | h20 | h10 | 0から2 |
| `D1` | 6 | d8 | d4 | d2 | d1 | 0から9 |
| `D10` | 7 | fr | フリーRAM | d20 | d10 | 0から3 |
| `MO1` | 8 | mo8 | mo4 | mo2 | mo1 | 0から9 |
| `MO10` | 9 | fr | フリーRAM | フリーRAM | mo10 | 0から1 |
| `Y1` | 10 | y8 | y4 | y2 | y1 | 0から9 |
| `Y10` | 11 | y80 | y40 | y20 | y10 | 0から9 |
| `W` | 12 | fr | w4 | w2 | w1 | 0から6 |
| `CD` | 13 | 30ADJ. | IRQ-F | CAL/HW | HOLD | |
| `CE` | 14 | t1 | t0 | INT/STND | MASK | |
| `CF` | 15 | TEST | 24/12 | STOP | RESET | |

`snesrtc.epson`は各レジスタを番号で`S1`から`CF`まで名付け、各制御ビットをマスクで名付けています。CDには`HOLD`、`CAL_HW`、`IRQ_F`、`ADJUST`、CFには`RESET`、`STOP`、`HOURS_24`、`TEST`、CEには`MASK`、`INT_STND`があります。ほかに`ENABLE`、`DATA`、`STATUS`、`WRITE_MODE`、`READ_MODE`、`READY`、`REGISTERS`、`DIGIT_MASK`、`OSC_FLAG`、`READ_FLAG`、`READ_FLAG_AT`、`CALENDAR_READ_FLAG_AT`、`PM`、`H20`、`STOPPED`、`NIBBLE`、`HALF_MINUTE`、`MINUTE`、`HOUR`、`WHOLE_SECONDS_PER_PERIOD`、`PERIOD_SHIFT`、`PERIOD_BITS`、`NOON`、`YEAR_PIVOT`、`STAMP_LIMIT`と、`state`の5つの値`INACTIVE`、`MODE_SELECT`、`INDEX_SELECT`、`READING`、`WRITING`があります。

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

各行はW、Y10からS1までの順です。曜日5、99-12-31、23:59:50です。15秒後の最初の読み出しはまだ古い時刻を示します。チップが追いつくのは選択解除されたときだからです。その次の読み出しは曜日6、00-01-01、00:00:05を示します。

| 属性または呼び出し | 意味 |
|:--|:--|
| `state` | `"inactive"`、`"mode"`、`"index"`、`"read"`、`"write"`のいずれか |
| `mode` | `0x03`または`0x0C`。最後に選んだモード |
| `index` | 次のデータアクセスが届くレジスタ |
| `enable`, `status` | 最後に`$4840`に書き込んだ値と、ステータスバイト |
| `moment()`, `store_moment(moment)` | S1からWまでのレジスタを`calendar.Moment`として取得し、また書き戻します。日付はCAL/HWが立っている間だけ保存されます |
| `hour()`, `store_hour(hour)` | 0から23の時。CFが選ぶ表記で読み書きします |
| `digit(index)`, `put_digit(index, value)` | レジスタの桁ビットだけを扱い、フラグビットには触れません |
| `twenty_four_hour()`, `dated()`, `stopped()` | 24/12が立っているか、CAL/HWが立っているか、RESETまたはSTOPが立っているか |
| `elapsed(current)` | スタンプから`current`までの秒数。2^31を超える差は0と読みます |
| `update(offset=0)` | HOLDが立っていなければカウンタを`now() - offset`まで進め、1秒でも経過していれば読み出しフラグを立てます |
| `set_read_flag()`, `clear_read_flag()` | frを持つ5つのレジスタでfrを立てる、またはクリアします |
| `read_data()`, `write_enable(value)`, `write_data(value)` | `$4841`の読み出し、`$4840`への書き込み、`$4841`への書き込みが行うこと |
| `write_register(value)`, `write_control_d(value)`, `write_control_f(value)` | 現在のレジスタへのデータ書き込みと、書き込まれたときに動作する2つの制御レジスタ |
| `release_hold()`, `adjust_to_nearest_minute()` | HOLDのクリアと30ADJ.の設定が行うこと |

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

ステータスは選択後に1回だけ`0x80`を返します。CDへの書き込みはCAL/HWに加えてIRQ-Fと30ADJ.も立てます。IRQ-Fは保存されず、30ADJ.は40秒を次の分に切り上げて自分自身をクリアします。TESTはCFへの書き込みで立ち、選択解除でクリアされます。

### 暦

`snesrtc.calendar`には、両方のチップが追いつくときに実行する計算があります。

| 名前 | 内容 |
|:--|:--|
| `Moment(year, month, day, hour, minute, second, weekday)` | 時計の1回分の読み取り。値で比較とハッシュを行います |
| `advance(moment, seconds)` | `seconds`後の時点。リファレンスと同じ数え方で数えます |
| `is_leap(year)` | グレゴリオ暦の規則 |
| `days_in(year, month)` | 28から31。1から12の範囲外の月は12を法として還元されます |
| `weekday(year, month, day)` | 日曜日が0で、1900年1月1日月曜日から数えます |
| `MONTHS`, `EPOCH_YEAR`, `EPOCH_WEEKDAY`, `WEEK`, `DAY`, `MASK` | これらを支える定数 |

```python
from snesrtc.calendar import Moment, advance, days_in, is_leap, weekday

print(advance(Moment(1999, 12, 31, 23, 59, 59, 5), 1))
print(is_leap(1900), is_leap(2000), days_in(1996, 2), weekday(1996, 8, 18))
```

```
<2000-01-01 00:00:00 weekday=6>
False True 29 0
```

### ドクター

| コマンド | 終了コード |
|:--|:--|
| リポジトリのルートで`python3 snesrtc/doctor.py` | パッケージのチェックがすべて通れば0、1つでも通らなければ1 |
| pipでインストールした後の`snesrtc-doctor` | 同じ |

引数は取りません。最初にマシンについて報告します。インタプリタ、エンコーディング、ファイルシステムの大文字小文字、改行コード、パスの長さ、空き容量、gitです。これらの行は助言であり、終了コードを変えることはありません。次にパッケージをチェックします。Pythonのバージョン、両方の時計の構築とリセット、固定時刻を与えた時計がそれを読み返せること、`$2802`がオープンバスとして読めること、[`conformance/pinned.json`](conformance/pinned.json)のピン、リファレンスドライバがビルド済みかどうかです。例外を送出したチェックは、その例外の型とメッセージとともに報告されます。

## 各答えの出どころ

2つの時計は異なる根拠に基づいています。

| 段 | 出典 | 決めること |
|:--|:--|:--|
| 1 | セイコーエプソン、*Application Manual: Real Time Clock Module RTC-4513* | エプソンがRTC-4513について印刷したすべて。レジスタの幅、カウント範囲、各制御ビットの働き、セッションの区切り方、電源投入後に残る状態 |
| 2 | コミットでピン留めしたsnes9xの記録 | マニュアルにないこと。SPC7110が3線式シリアルチップを3つのカートリッジアドレスに変換する方法、文書化された範囲外でのカウンタの動作、そしてシャープのチップのすべて |
| 3 | それ以外なし | なし |

段1の数値はすべて[`conformance/hardware.json`](conformance/hardware.json)に、読み取った元の文、文書のダイジェスト、読み取った日付とともに記録されています。[`conformance/hardware.test.py`](conformance/hardware.test.py)はパッケージの定数をそれと照合します。

マニュアルと記録が食い違う場合、パッケージはマニュアルに従います。15件の食い違いはそれぞれ[`conformance/divergences.json`](conformance/divergences.json)のエントリになっており、文書の記述、記録の動作、パッケージがどちらに従うか、何が決着をつける根拠になるかを示しています。

### シャープのチップにはデータシートがない

`S-RTC`は`S-DSP`、`S-SMP`、`S-PPU`と同じ形式の任天堂の部品名であり、シャープのカタログ番号ではありません。メーカーの文書は知られていません。2026-08-20付けの調査が`hardware.json`の`"verified": false`の下に記録されており、決着をつける3つの発見も併記されています。シャープのデータブックの項目、カタログ部品名が写ったダイ写真、またはだいかいじゅう物語IIが時計を動かしている間のバスのロジックキャプチャです。テストが、そのブロックがまだそう書いていることを確認します。

## マニュアルが決めること

**13個の時計レジスタのうち6個は、レジスタより狭い桁を持ちます。**カウント範囲の列がそれを示しています。S10とMI10は5、H10は2、D10は3、MO10は1、Wは6で止まります。余ったビットは発振フラグ、読み出しフラグ、PM/AMビット、そしてプログラムが使えるフリーRAMです。`epson.DIGIT_MASK`がこれらを分離するので、プログラムが保存したフラグが日付の一部として読み返されることはありません。

**HOLDは時計を止めません。**マニュアルには"The clock continues to run"とあり、HOLDが立っている間に失われた最初のインクリメントは"is compensated for when the hold condition is released (+1 second)."とあります。HOLDを解除すると1秒加算され、マニュアルの時計設定手順は書き込みを1秒以内に終えるよう警告しています。

**秒を加算する制御ビットはありません。**CDのビット1はCAL/HWです。クリアすると日付カウンタが止まり、それらのレジスタはRAMとして残ります。D10とMO10の読み出しフラグも同じ扱いで、CAL/HWがクリアされている間は、秒が進んでもチップの選択を解除しても変わりません。文書化された唯一のソフトウェアによる調整は、CDのビット3の30ADJ.です。

**電源投入時の状態は12時間表記です。**マニュアルには"At power-on, all registers and the STD.P output are undefined."とあります。ゼロで起動するレジスタファイルは24/12がクリアされており、これは12時間表記です。CAL/HWもクリアされており、これは日付を止めます。

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

午後11:59:59から1秒経過します。時は12になりPMがクリアされ、これは午前0時です。曜日カウンタは0から1に進み、CAL/HWがクリアされているので日は1のままです。

**IRQ-Fには書き込めません。**マニュアルには"A write instruction for the IRQ-F bit is not executed."とあります。CEのINT/STNDが立っていれば、t1とt0が選ぶ桁の繰り上がりでこのビットが立ち、CDを読むとクリアされます。MASKが立っている間は0と読め、MASKを立てるとすでに立っているフラグも下がります。固定周期モードではフラグが立つのは7.8 msだけで、モデルが数える1秒より短いため、そこでは立てません。

**表記ごとにH10の1ビットが0に固定されます。**12時間表記では"The h20 bit cannot be written and is fixed to "0"."、24時間表記では"A write attempt to the PM/AM bit is disregarded, and the bit will always read "0"."とあります。書き込みはそのビットを捨て、読み出しはレジスタの中身にかかわらず0を返します。

**TESTはチップが選択解除されたときにクリアされます。**RESETを立ててCFに書き込んだ場合もクリアされます。

**STOPはカウンタが最新にされた後に有効になります。**CFへの書き込みは先に時計を追いつかせてから新しいビットを保存するので、停止前に経過した時間は保持されます。

## 記録が決めること

マニュアルはこれらについて何も述べていません。この件についての唯一の文は"Do not set impossible values to prevent the possibility of clock malfunction."です。

**月が0の場合は30日の月になります。**カウンタは数える前に月から1を引き、符号なし32ビット演算で計算します。0は4,294,967,295になり、月の長さはその数を12で割った余りから読まれます。これは30日の月に当たり、同じ年の1月へ繰り上がります。

**範囲を超えたフィールドは還元されず、クリアされます。**100分は0に繰り上がって1時間加算されるので、60を超えた40分は失われます。

```python
from snesrtc.calendar import Moment, advance

print(advance(Moment(1996, 0, 30, 23, 59, 59, 0), 1))
print(advance(Moment(1996, 8, 18, 12, 100, 59, 0), 1))
```

```
<1996-01-01 00:00:00 weekday=1>
<1996-08-18 13:00:00 weekday=0>
```

**エプソンの時計は、選択されたときではなく選択解除されたときに追いつきます。**上のセッションの例が示すとおり、セッションは前のセッションが残した時刻を読みます。実物のチップは連続して計時するので、このような継ぎ目はありません。

**モードコードはバイト全体で比較されます。**シリアルチップは常に4ビットしか見ないので、これはどの文書にも記述されていないSPC7110ラッパーの性質です。

## 2つのチップ

これらは異なるメーカーの部品で、異なるパブリッシャーのカートリッジに載っています。

| | シャープS-RTC | エプソンRTC-4513 |
|:--|:--|:--|
| メーカーの文書 | 知られていない | アプリケーションマニュアル、1999年 |
| アクセス先 | `$2800`と`$2801` | SPC7110経由で`$4840`から`$4842` |
| 形 | マーカーで囲まれた固定シーケンス | 16個の4ビットレジスタからなるアドレス指定のファイル |
| 1つのフィールドを得る方法 | シーケンス全体を読んで数える | そのレジスタを指定する |
| 曜日 | 日付が書き込まれたときに日付から計算 | 0から6の独立したカウンタで、意味は付与されていない |
| 年 | 3桁に1000を加算 | 2桁。世紀はどこにも印刷されていない |
| 時間 | 24 | 12または24。制御ビットで選択 |
| 制御レジスタ | なし | 3個。名前付きのビットが16個 |
| 追いつくとき | 読み出しが始まるとき | チップが選択解除されたとき |

<a id="nothing-starts-cleared"></a>

## 最初からクリアされているものはない

バッテリーバックアップのカートリッジは保持していた内容を保持しており、工場出荷直後のものはシリコンが起動したときの内容を保持しています。エプソンは"At power-on, all registers and the STD.P output are undefined."と印刷しています。

`Store(seed=UNSET_SEED, cleared=False, held=None)`は20バイトを`seed`から埋めます。`cleared=True`はゼロで埋め、`held`はその上にバイトをコピーし、20で折り返します。`read(index)`と`write(index, value)`はインデックスを20で折り返し、値の下位8ビットを保持します。`bytes`はリストそのもので、`stamp`はバイト16から19を1つのリトルエンディアンの数として読み書きします。`snesrtc.store`には`SIZE`、`STAMP_AT`、`STAMP_BYTES`、`UNSET_SEED`があります。

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

シード付きのストアは読むたびに同じバイトを保持し、シードが違えば違うバイトを保持します。そのため、プログラムが一度も書き込んでいない内容に依存していないことをテストで示せます。ゼロが欲しい呼び出し側はゼロを要求し、カートリッジを復元する呼び出し側は持っていたバイトを渡します。

## 意図的にモデル化していないもの

それぞれが[`conformance/divergences.json`](conformance/divergences.json)のエントリで、理由と何がそれを変えるかが記されています。

**割り込みはありません。**CEは1/64秒、1秒、1分、1時間の4つの周期から1つを選び、STD.Pピンを駆動します。SPC7110がそのピンをスーパーファミコンのプログラムから読める場所へつないでいると述べた文書はないので、CEはどのピンも駆動せず、コンソールに届く割り込みもありません。CDでプログラムが読めるIRQ-Fへの作用はモデル化しています。

**水晶のずれはありません。**マニュアルには、25度Cで0プラスマイナス25 ppm、2次温度係数が1度Cの2乗あたり-0.035 ppm、そして"At 11.574 ppm, the daily clock error is about one second per day."とあります。これらの数値は記録に含まれています。これらはモデルが知り得ない温度でのモジュール群全体の範囲を示すものなので、シミュレーションはしません。

**30ADJ.後の125マイクロ秒のロックアウトはありません。**ビットが自分自身をクリアする動作はモデル化しています。S1からWまでに書き込めない期間には1秒より細かい時間軸が必要ですが、`now`インターフェースはそれを持ちません。

## 正しいのか

差分テストは、シードから生成したスクリプトで各チップを動かし、同じスクリプトをピン留めしたsnes9xのソースを中心にコンパイルしたドライバにも通し、2つの記録を1行ずつ比較します。

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

モデルがマニュアルに従い、記録が単なる記憶として扱う1つのフィールド、つまりCDのIRQ-Fや表記ごとに0に固定されるH10のビットでは、ランナーは比較を続け、そのフィールドだけを免除します。行のほかのビットはすべて一致しなければならず、それらの操作は別に数えます。それ以外の宣言済みの食い違いでは、スクリプトの比較はそれに達する最初の操作で止まります。その先では、マニュアルがすでに別の答えを出している問いに記録が答え、その状態は後の計算が読むフィールドで異なるので、それらの操作は別に数えて名前を付けます。ランナーが観測できる食い違いで`divergences.json`にないものは実行を失敗させます。ランナーはスクリプトごとにそのファイルから一覧を読みます。

シャープのチップはほぼ最初から最後まで比較されます。記録がその唯一の根拠だからです。唯一の除外は記録器に関するものです。記録器はスタンプをホストの`time_t`の最大値と比べるので、64ビットと32ビットのビルドは2^31秒を超える差で食い違います。

エプソンのスクリプトは200操作が上限です。比較は平均で約30操作、200スクリプトで6130操作の後に止まるので、このチップのカバレッジはスクリプトの長さではなく数に応じて増えます。

2つの時計は別々のスクリプトで動かします。テストハーネスでも記録でも両者は1つの20バイトのストアを共有しますが、両方のチップを載せたカートリッジはなかったので、実際のカートリッジでそうなったことはありません。リファレンスが壁時計を読むため、時刻もスクリプトで与えます。リファレンスのソースはビルド時に取得し、リポジトリには取り込みません。このリポジトリに属するのは[`conformance/ref/driver.cpp`](conformance/ref/driver.cpp)のドライバだけです。

| コマンド | 引数 | 終了コード |
|:--|:--|:--|
| `python3 -m conformance.build` | `--sources DIR`, `--output PATH`, `--pinned FILE`, `--driver-source FILE` | 0ビルド成功、1コンパイル失敗、2引数の誤りまたは取得失敗 |
| `python3 -m conformance.reference` | `--runs N`、デフォルト200、`--from N`, `--seed N`, `--length N`、デフォルト4000、`--driver PATH` | 0不一致なし、1不一致または未宣言の食い違い、2ドライバなしまたは引数の誤り |
| `python3 -m conformance.documents` | 取得せずに検証する`--check`、`--only SUBSTRING` | 0すべてのダイジェストが一致、1いずれかを拒否、一致なし、または引数の誤り |
| `python3 -m conformance.quotes` | なし | 記録中の引用が文書に見つからない、または引用箇所の確認が取れない場合は1、それ以外は0。文書がディスクにない場合も0 |
| `python3 -m conformance.speed` | なし | 読み出しが毎秒500,000回の下限を上回れば0、上回らなければ1 |
| `python3 -m conformance.cartridge CARTRIDGE OUT.json` | カートリッジのイメージと出力パス | 0書き込み成功、1時計ルーチンが見つからない、2引数の誤りまたはファイルがない |

失敗したスクリプトはシードから再生成できます。`reference.generate(seed, length, part)`は操作を返し、`reference.render(script)`はドライバが標準入力から読むテキストを返します。

```python
from conformance import reference

script = reference.generate(seed=22, length=4000, part="sharp")
print(len(script), reference.render(script).splitlines()[:4])
```

```
4000 ['time 1000000000', 'store 15 4', 'store 13 2', 'w 10241 12']
```

このスクリプトは時刻を設定し、エプソンの制御レジスタを構成してから、`$2801`に`0x0C`を書き込みます。`$2801`は10241です。

[`conformance/cartridge.json`](conformance/cartridge.json)は、天外魔境ZEROの時計ルーチンがチップに書き込む内容を、プログラムを実行せずに読み取って記録したものです。制御レジスタへの定数書き込みが5つあり、その中にはCFへの`0x07`と続く`0x04`、CDへの`0x06`があります。このファイルにはイメージのダイジェストだけがあり、イメージのバイトは1つも含まれていません。

## 開発に参加する

| 必要なもの | 場所 |
|:--|:--|
| すべてのゲートと実行順序 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| コーディングエージェント向けの同じ内容 | [AGENTS.md](AGENTS.md) |
| このリポジトリがファミリーの他のリポジトリと共有する基準 | [FAMILY.md](FAMILY.md) |
| 未解決の事項と、それを決着させるもの | [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) |
| バグ報告 | [GitHub Issues](https://github.com/gufranco/snes-rtc-python/issues) |
| セキュリティ報告 | [SECURITY.md](SECURITY.md) |
| 行動規範 | [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 mypy==1.14.1
python3 -m coverage erase
for file in $(find snesrtc conformance -name '*.test.py' | sort); do
  python3 -m coverage run -a "$file"
done
python3 -m coverage report
```

各モジュールには、その名前を付けたテストファイルが隣にあり、それぞれ単独で実行できます。カバレッジは命令と分岐の100%が必須のゲートで、mypyはstrictで実行します。

食い違いを、記録に合わせてモデルを変えることで解消しないでください。マニュアルが間違っているなら、ページを示して理由を述べてください。新しい不一致には、何が決着をつけるかを示した`divergences.json`のエントリが必要です。それがなければ差分テストが失敗します。

## 参考文献

- *Application Manual: Real Time Clock Module RTC-4513*、セイコーエプソン、1999年12月1日。18ページ、509,740バイト、SHA-256 `409b8a5a3030fe432dd7dafbf4719944abac890cc5cbebbf96fb8313f9caca33`。テキスト層のないファクスなので、引用箇所はページをレンダリングして確認します。
- *RTC-4513 catalogue extract*、セイコーエプソン、日付なし。2ページ、701,040バイト、SHA-256 `6496eb35fddc181d4e80832b98b8a45163bf5370eadd1e58002aefc83f12edcf`。同じ16行のレジスタ表を載せています。
- snes9x、`srtcemu.cpp`と`spc7110emu.cpp`およびそのヘッダ、コミット`2971061cf07fdc6fc7d18883edf4e648eb16a6d2`、https://github.com/snes9xgit/snes9x 、[`conformance/pinned.json`](conformance/pinned.json)でピン留め。両方のチップの比較対象となるリファレンスです。ビルド時に取得し、リポジトリには取り込みません。

エプソンの文書はどちらも再配布できず、このリポジトリにもありません。[`conformance/documents.json`](conformance/documents.json)にはそれぞれのダイジェスト、サイズ、アドレスがあり、`python3 -m conformance.documents`がそれらをgitが無視する`docs/`に取得し、ダイジェストが一致しないファイルは拒否します。

## 引用

[CITATION.cff](CITATION.cff)は、パッケージのバージョンを刻むスクリプトによってリリースごとに更新されます。

## ライセンス

MIT。[LICENSE](LICENSE)を参照してください。snes9xのソースは独自のライセンスに従う別の著作物で、ビルド時に取得し、ここでは再配布しません。
