import json
import sys
import unittest
from fractions import Fraction
from pathlib import Path
from typing import override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesrtc import calendar, epson, sharp, store

HARDWARE = Path(__file__).resolve().parent / "hardware.json"

DIVERGENCES = Path(__file__).resolve().parent / "divergences.json"

HELD = json.loads(HARDWARE.read_text())

PARTS = {part["part"]: part for part in HELD["parts"]}

EPSON = PARTS["Epson RTC-4513"]

SHARP = PARTS["Sharp S-RTC"]

FACTS = EPSON["facts"]

ROWS = FACTS["registerTable"]["rows"]

FROZEN = 1_000_000_000

DAY = 86_400

HOUR = 3_600

DIGITS = (0, 0, 0, 3, 2, 1, 8, 1, 8, 0, 6, 2)

EXAMPLE_YEAR = 1993

UNIT_SECONDS = {"s": 1, "second": 1, "minute": 60, "hour": 3600}

PERIOD_BITS = FACTS["controlRegisterE"]["bits"]

EVERY_SECOND = epson.INT_STND | PERIOD_BITS["t0"]["mask"]

A_MINUTE_TURNING = (9, 5, 8, 5, 2, 1)

A_SECOND_TURNING = (8, 5, 9, 5, 2, 1)

AN_HOUR_TURNING = (9, 5, 9, 5, 2, 1)

MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def a_clock(
    hand: list[int], control_f: int = epson.HOURS_24, control_d: int = epson.CAL_HW
) -> epson.Chip:
    held = store.Store(cleared=True)
    held.stamp = hand[0]
    held.write(epson.CF, control_f)
    held.write(epson.CD, control_d)
    return epson.Chip(held, now=lambda: hand[0])


def opened(chip: epson.Chip, mode: int, index: int) -> None:
    chip.write(epson.ENABLE, 0x01)
    chip.write(epson.DATA, mode)
    chip.write(epson.DATA, index)


def written(chip: epson.Chip, index: int, *nibbles: int) -> None:
    opened(chip, epson.WRITE_MODE, index)
    for one in nibbles:
        chip.write(epson.DATA, one)


def read_back(chip: epson.Chip, index: int) -> int:
    opened(chip, epson.READ_MODE, index)
    return chip.read(epson.DATA)


def stepped(chip: epson.Chip) -> int:
    at = chip.index
    chip.read(epson.DATA)
    return at


def located(spelled: str) -> tuple[int, int]:
    name, _, bit = spelled.strip().partition(".")
    address = next(row["address"] for row in ROWS if row["name"] == name)
    return address, 1 << int(bit.removeprefix("D"))


def a_day(text: str) -> tuple[int, int, int]:
    if "-" in text:
        year, month, day = (int(part) for part in text.split("-"))
        return year, month, day
    month_name, day_text = text.split()
    return EXAMPLE_YEAR, MONTH_NAMES.index(month_name) + 1, int(day_text)


def a_second_before_midnight(year: int, month: int, day: int) -> tuple[int, ...]:
    short = year % 100
    return (9, 5, 9, 5, 3, 2, day % 10, day // 10, month % 10, month // 10, short % 10, short // 10)


def a_second_after(date: tuple[int, int, int]) -> tuple[int, int, int]:
    hand = [FROZEN]
    chip = a_clock(hand)
    written(chip, epson.S1, *a_second_before_midnight(*date))
    hand[0] += 1
    chip.write(epson.ENABLE, 0x00)
    moment = chip.moment()
    return moment.year, moment.month, moment.day


def disregarded(code: int) -> bool:
    chip = a_clock([FROZEN])
    chip.store.write(0x05, 0x0A)
    before = list(chip.store.bytes)
    chip.write(epson.ENABLE, 0x01)
    chip.write(epson.DATA, code)
    chip.write(epson.DATA, 0x05)
    chip.write(epson.DATA, 0x09)
    return chip.store.bytes == before and chip.read(epson.DATA) == 0x00


def registers_at_power_on(seed: int) -> list[int]:
    chip = epson.Chip(store.Store(seed=seed), now=lambda: FROZEN)
    opened(chip, epson.READ_MODE, epson.S1)
    return [chip.read(epson.DATA) for _ in range(epson.REGISTERS)]


def the_top_held(row: dict[str, object]) -> int:
    chip = a_clock([FROZEN])
    address = int(str(row["address"]))
    top = row["countRange"]
    assert isinstance(top, list)
    written(chip, address, top[1])
    return chip.digit(address)


def tens_of_hours(control_f: int) -> set[int]:
    chip = a_clock([FROZEN], control_f=control_f)
    seen = set()
    for hour in range(24):
        chip.store_hour(hour)
        seen.add(chip.digit(epson.H10))
    return seen


def weekdays_counted(days: int) -> list[int]:
    hand = [FROZEN]
    chip = a_clock(hand)
    written(chip, epson.S1, *DIGITS[:12], 0)
    counted = []
    for _ in range(days):
        hand[0] += DAY
        chip.write(epson.ENABLE, 0x00)
        counted.append(chip.digit(epson.W))
    return counted


def flag_written(address: int, values: tuple[int, ...]) -> list[int]:
    chip = a_clock([FROZEN])
    kept = []
    for value in values:
        written(chip, address, value)
        kept.append(read_back(chip, address))
    return kept


def hour_read(control_f: int, tens: int) -> int:
    chip = a_clock([FROZEN], control_f=control_f)
    written(chip, epson.H1, 3, tens)
    return chip.hour()


def hours_moved(*control_f: int) -> int:
    hand = [FROZEN]
    chip = a_clock(hand)
    written(chip, epson.S1, *DIGITS)
    for value in control_f:
        written(chip, epson.CF, value)
    hand[0] += HOUR
    chip.write(epson.ENABLE, 0x00)
    return chip.digit(epson.H1) - DIGITS[epson.H1]


def named_bit(name: str) -> tuple[int, int]:
    return next(
        (row["address"], 1 << at)
        for row in ROWS
        for at, key in enumerate(("d0", "d1", "d2", "d3"))
        if row[key] == name
    )


def period_in_seconds(period: str) -> Fraction:
    count, unit = period.split()
    return Fraction(count) * UNIT_SECONDS[unit]


def flag_after_a_second(control_e: int, start: tuple[int, ...]) -> int:
    hand = [FROZEN]
    chip = a_clock(hand)
    written(chip, epson.S1, *start, *DIGITS[6:])
    written(chip, epson.CE, control_e)
    chip.write(epson.ENABLE, 0x00)
    hand[0] += 1
    chip.write(epson.ENABLE, 0x00)
    return read_back(chip, epson.CD) & epson.IRQ_F


def adjusted(seconds: int, mask: int) -> tuple[int, int, int]:
    chip = a_clock([FROZEN])
    written(chip, epson.S1, seconds % 10, seconds // 10, *DIGITS[2:])
    written(chip, epson.CD, epson.CAL_HW | mask)
    chip.write(epson.ENABLE, 0x00)
    second = chip.digit(epson.S1) + chip.digit(epson.S10) * 10
    return second, chip.digit(epson.MI1), chip.store.read(epson.CD) & mask


class DocumentTest(unittest.TestCase):
    def source(self, key: str) -> dict[str, object]:
        held = EPSON["documents"][key]
        assert isinstance(held, dict)
        return held

    def test_the_epson_part_is_backed_by_a_named_document(self) -> None:
        self.assertEqual(self.source("applicationManual")["publisher"], "Seiko Epson Corporation")

    def test_the_document_carries_a_digest_so_the_reading_can_be_repeated(self) -> None:
        self.assertRegex(str(self.source("applicationManual")["sha256"]), r"^[0-9a-f]{64}$")

    def test_and_a_second_document_that_corroborates_the_register_table(self) -> None:
        self.assertRegex(str(self.source("catalogueExtract")["sha256"]), r"^[0-9a-f]{64}$")

    def test_the_second_one_says_which_one_it_corroborates(self) -> None:
        self.assertEqual(self.source("catalogueExtract")["corroborates"], "applicationManual")

    def test_the_two_documents_are_not_the_same_file(self) -> None:
        self.assertNotEqual(
            self.source("applicationManual")["sha256"],
            self.source("catalogueExtract")["sha256"],
        )

    def test_the_sharp_part_declares_an_empty_block_rather_than_none(self) -> None:
        self.assertEqual(SHARP["documents"], {})

    def test_every_fact_carries_the_sentence_it_came_from(self) -> None:
        unquoted = [
            name for name, fact in FACTS.items() if isinstance(fact, dict) and not _quoted(fact)
        ]

        self.assertEqual(unquoted, [])


def _quoted(fact: object) -> bool:
    if isinstance(fact, dict):
        if "quote" in fact:
            return True
        return any(_quoted(value) for value in fact.values())
    if isinstance(fact, list):
        return any(_quoted(value) for value in fact)
    return False


class QuoteSearchTest(unittest.TestCase):
    def test_a_fact_with_its_own_quote_is_quoted(self) -> None:
        self.assertTrue(_quoted({"value": 1, "quote": "printed here"}))

    def test_a_fact_whose_quote_is_nested_deeper_is_quoted_too(self) -> None:
        self.assertTrue(_quoted({"bits": {"hold": {"quote": "printed here"}}}))

    def test_and_one_hidden_in_a_list(self) -> None:
        self.assertTrue(_quoted({"rows": [{"quote": "printed here"}]}))

    def test_a_bare_value_is_not_a_quote(self) -> None:
        self.assertFalse(_quoted(16))

    def test_and_neither_is_a_fact_that_only_asserts(self) -> None:
        self.assertFalse(_quoted({"value": 16, "why": "because"}))


class RegisterTableTest(unittest.TestCase):
    def test_the_table_has_one_row_for_every_register(self) -> None:
        self.assertEqual(len(ROWS), FACTS["registerCount"]["value"])

    def test_the_model_holds_as_many_registers_as_the_manual_gives(self) -> None:
        self.assertEqual(epson.REGISTERS, FACTS["registerCount"]["value"])

    def test_the_rows_are_in_address_order(self) -> None:
        self.assertEqual([row["address"] for row in ROWS], list(range(len(ROWS))))

    def test_the_digit_masks_the_model_uses_are_the_ones_the_manual_prints(self) -> None:
        self.assertEqual(
            list(epson.DIGIT_MASK),
            [row.get("digitMask", epson.NIBBLE) for row in ROWS],
        )

    def test_every_digit_mask_reaches_the_top_of_that_register_count_range(self) -> None:
        undersized = [
            row["name"]
            for row in ROWS
            if row["countRange"] and row["countRange"][1] > row["digitMask"]
        ]

        self.assertEqual(undersized, [])

    def test_and_no_mask_is_wider_than_the_count_range_needs(self) -> None:
        oversized = [
            row["name"]
            for row in ROWS
            if row["countRange"] and row["digitMask"] > 2 ** row["countRange"][1].bit_length() - 1
        ]

        self.assertEqual(oversized, [])

    def test_the_control_registers_sit_where_the_manual_puts_them(self) -> None:
        named = {row["name"]: row["address"] for row in ROWS}

        self.assertEqual((named["CD"], named["CE"], named["CF"]), (epson.CD, epson.CE, epson.CF))

    def test_the_clock_registers_sit_where_the_manual_puts_them(self) -> None:
        named = {row["name"]: row["address"] for row in ROWS}

        self.assertEqual(
            (
                named["S1"],
                named["S10"],
                named["MI1"],
                named["MI10"],
                named["H1"],
                named["H10"],
                named["D1"],
                named["D10"],
                named["MO1"],
                named["MO10"],
                named["Y1"],
                named["Y10"],
                named["W"],
            ),
            (
                epson.S1,
                epson.S10,
                epson.MI1,
                epson.MI10,
                epson.H1,
                epson.H10,
                epson.D1,
                epson.D10,
                epson.MO1,
                epson.MO10,
                epson.Y1,
                epson.Y10,
                epson.W,
            ),
        )

    def test_the_read_flag_sits_in_every_register_whose_top_bit_the_manual_calls_fr(
        self,
    ) -> None:
        printed = tuple(row["address"] for row in ROWS if row["d3"] == "fr")

        self.assertEqual(printed, epson.READ_FLAG_AT)

    def test_the_oscillator_flag_sits_where_the_manual_calls_it_fo(self) -> None:
        printed = [row["address"] for row in ROWS if row["d3"] == "fo"]

        self.assertEqual(printed, [epson.S10])

    def test_the_afternoon_flag_sits_where_the_manual_puts_it(self) -> None:
        row = ROWS[epson.H10]

        self.assertEqual((row["d2"], epson.PM), ("PM/AM", 0x4))


class ProtocolTest(unittest.TestCase):
    def test_the_write_mode_code_is_the_one_the_manual_names(self) -> None:
        self.assertEqual(epson.WRITE_MODE, FACTS["writeModeCode"]["value"])

    def test_and_the_read_mode_code(self) -> None:
        self.assertEqual(epson.READ_MODE, FACTS["readModeCode"]["value"])

    def test_a_register_is_as_wide_as_the_manual_says(self) -> None:
        self.assertEqual(epson.NIBBLE, 2 ** FACTS["registerWidthBits"]["value"] - 1)

    def test_the_weekday_counts_over_the_range_the_manual_gives(self) -> None:
        low, high = FACTS["weekdayCountsZeroToSix"]["value"]

        self.assertEqual((low, high + 1), (0, calendar.WEEK))


class ControlBitTest(unittest.TestCase):
    def test_control_register_d_bits_carry_the_manual_masks(self) -> None:
        bits = FACTS["controlRegisterD"]["bits"]

        self.assertEqual(
            (epson.HOLD, epson.CAL_HW, epson.IRQ_F, epson.ADJUST),
            (
                bits["hold"]["mask"],
                bits["calHw"]["mask"],
                bits["irqF"]["mask"],
                bits["thirtySecondAdjust"]["mask"],
            ),
        )

    def test_control_register_f_bits_carry_the_manual_masks(self) -> None:
        bits = FACTS["controlRegisterF"]["bits"]

        self.assertEqual(
            (epson.RESET, epson.STOP, epson.HOURS_24, epson.TEST),
            (
                bits["reset"]["mask"],
                bits["stop"]["mask"],
                bits["twentyFourTwelve"]["mask"],
                bits["test"]["mask"],
            ),
        )

    def test_the_interrupt_flag_is_marked_read_only(self) -> None:
        self.assertTrue(FACTS["controlRegisterD"]["bits"]["irqF"]["readOnly"])

    def test_the_two_bits_that_stop_the_clock_are_the_two_the_manual_says_stop_it(
        self,
    ) -> None:
        bits = FACTS["controlRegisterF"]["bits"]

        self.assertEqual(epson.STOPPED, bits["reset"]["mask"] | bits["stop"]["mask"])

    def test_and_hold_is_not_one_of_them(self) -> None:
        held = store.Store(cleared=True)
        held.write(epson.CD, epson.HOLD)

        self.assertFalse(epson.Chip(held).stopped())

    def test_the_stopping_bits_are_named_in_control_register_f_and_not_in_d(self) -> None:
        stopping = {"reset", "stop"}

        self.assertEqual(stopping & set(FACTS["controlRegisterD"]["bits"]), set())

    def test_control_register_d_has_no_bit_that_adds_a_second(self) -> None:
        named = set(FACTS["controlRegisterD"]["bits"])

        self.assertEqual(named, {"hold", "calHw", "irqF", "thirtySecondAdjust"})


class ContradictionTest(unittest.TestCase):
    def test_six_registers_carry_a_digit_narrower_than_the_register(self) -> None:
        narrow = [row["name"] for row in ROWS[:13] if row["digitMask"] != epson.NIBBLE]

        self.assertEqual(narrow, ["S10", "MI10", "H10", "D10", "MO10", "W"])

    def test_the_tens_of_months_register_carries_a_single_bit(self) -> None:
        self.assertEqual(ROWS[epson.MO10]["digitMask"], 1)

    def test_the_free_ram_bits_are_the_ones_the_manual_marks(self) -> None:
        marked = {
            row["name"]: [key for key in ("d3", "d2", "d1", "d0") if row[key] == "*"]
            for row in ROWS[:13]
        }

        self.assertEqual(
            {name: bits for name, bits in marked.items() if bits},
            {"D10": ["d2"], "MO10": ["d2", "d1"]},
        )


class UnverifiedTest(unittest.TestCase):
    def test_the_sharp_part_is_marked_unverified_rather_than_left_looking_documented(
        self,
    ) -> None:
        self.assertFalse(SHARP["verified"])

    def test_it_carries_no_document_block(self) -> None:
        self.assertNotIn("document", SHARP)

    def test_it_names_who_asserts_what_it_holds(self) -> None:
        self.assertIn("assertedBy", SHARP["unverified"])

    def test_and_what_would_settle_it(self) -> None:
        self.assertNotEqual(SHARP["unverified"]["wouldSettleIt"], [])

    def test_its_recorded_facts_are_labelled_as_recorded_rather_than_as_facts(self) -> None:
        self.assertNotIn("facts", SHARP)

    def test_the_model_answers_where_the_recorded_block_says_it_does(self) -> None:
        recorded = SHARP["recordedFacts"]

        self.assertEqual(
            (sharp.DATA, sharp.CONTROL), (recorded["dataAddress"], recorded["controlAddress"])
        )

    def test_the_model_carries_the_sequence_length_the_recorded_block_gives(self) -> None:
        self.assertEqual(sharp.LAST_INDEX + 1, SHARP["recordedFacts"]["sequenceLength"])

    def test_and_the_marker(self) -> None:
        self.assertEqual(sharp.MARKER, SHARP["recordedFacts"]["marker"])

    def test_and_the_year_base(self) -> None:
        self.assertEqual(sharp.YEAR_BASE, SHARP["recordedFacts"]["yearBase"])

    def test_and_the_weekday_epoch(self) -> None:
        self.assertEqual(calendar.EPOCH_WEEKDAY, SHARP["recordedFacts"]["weekdayEpoch"]["value"])


class NotStatedTest(unittest.TestCase):
    def test_the_century_window_is_recorded_as_a_convention_rather_than_a_fact(self) -> None:
        self.assertIn("centuryWindow", EPSON["notStated"])

    def test_the_wrapper_is_recorded_as_undocumented(self) -> None:
        self.assertIn("spc7110Mapping", EPSON["notStated"])

    def test_the_year_pivot_the_model_uses_appears_in_no_fact_block(self) -> None:
        self.assertNotIn("yearPivot", FACTS)


class DivergenceTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.entries = json.loads(DIVERGENCES.read_text())["divergences"]

    def test_no_two_entries_share_an_id(self) -> None:
        names = [entry["id"] for entry in self.entries]

        self.assertEqual(len(names), len(set(names)))

    def test_every_entry_names_the_parts_it_is_about(self) -> None:
        missing = [entry["id"] for entry in self.entries if not entry.get("parts")]

        self.assertEqual(missing, [])

    def test_every_entry_says_which_side_the_package_follows(self) -> None:
        missing = [entry["id"] for entry in self.entries if not entry.get("packageFollows")]

        self.assertEqual(missing, [])

    def test_every_open_entry_says_what_would_settle_it(self) -> None:
        missing = [
            entry["id"]
            for entry in self.entries
            if entry["status"] == "open" and not entry.get("wouldSettleIt")
        ]

        self.assertEqual(missing, [])

    def test_every_closed_entry_says_what_would_reopen_it(self) -> None:
        missing = [
            entry["id"]
            for entry in self.entries
            if entry["status"] == "closed" and not entry.get("wouldReopenIt")
        ]

        self.assertEqual(missing, [])

    def test_every_contradiction_quotes_the_document_it_contradicts(self) -> None:
        unquoted = [
            entry["id"]
            for entry in self.entries
            if entry["severity"] == "contradiction" and "quote" not in entry["documentSays"]
        ]

        self.assertEqual(unquoted, [])

    def test_every_entry_that_follows_the_document_is_about_a_documented_part(self) -> None:
        wrong = [
            entry["id"]
            for entry in self.entries
            if entry["packageFollows"].startswith("document")
            and not all(PARTS[name]["verified"] for name in entry["parts"])
        ]

        self.assertEqual(wrong, [])

    def test_the_parts_named_are_parts_the_hardware_file_knows(self) -> None:
        unknown = [
            entry["id"]
            for entry in self.entries
            if any(name not in PARTS for name in entry["parts"])
        ]

        self.assertEqual(unknown, [])


class RecordSaysWhatTheModelDoesTest(unittest.TestCase):
    def divergences(self) -> list[dict[str, object]]:
        where = Path(__file__).resolve().parent / "divergences.json"
        held: list[dict[str, object]] = json.loads(where.read_text())["divergences"]
        return held

    def a_chip(self) -> epson.Chip:
        return epson.Chip(store.Store())

    def in_twelve_hour_notation(self, chip: epson.Chip) -> epson.Chip:
        chip.store.write(epson.CF, chip.store.read(epson.CF) & ~epson.HOURS_24 & epson.NIBBLE)
        return chip

    def test_every_hour_of_the_day_survives_twelve_hour_notation(self) -> None:
        chip = self.in_twelve_hour_notation(self.a_chip())

        read_back = []
        for hour in range(24):
            chip.store_hour(hour)
            read_back.append(chip.hour())

        self.assertEqual(read_back, list(range(24)))

    def test_and_the_tens_of_hours_bit_stays_down_throughout(self) -> None:
        chip = self.in_twelve_hour_notation(self.a_chip())

        tens = []
        for hour in range(24):
            chip.store_hour(hour)
            tens.append(chip.digit(epson.H10) & 0x2)

        self.assertEqual(tens, [0] * 24)

    def test_so_no_entry_calls_that_notation_unmodelled(self) -> None:
        named = [
            one["id"]
            for one in self.divergences()
            if "twelve" in str(one["id"]) and "unmodelled" in str(one["id"])
        ]

        self.assertEqual(named, [])

    def test_no_entry_at_all_calls_something_unmodelled_in_its_name(self) -> None:
        named = [one["id"] for one in self.divergences() if "unmodelled" in str(one["id"])]

        self.assertEqual(named, [])

    def test_every_entry_carries_a_status_the_family_recognises(self) -> None:
        allowed = {"open", "closed", "narrowed", "notModelled", "notADisagreement", "acknowledged"}

        stray = [one["id"] for one in self.divergences() if one.get("status") not in allowed]

        self.assertEqual(stray, [])


class PrintedBehaviourTest(unittest.TestCase):
    def test_the_address_returns_to_zero_after_the_last_register(self) -> None:
        # Arrange
        printed = FACTS["registerCount"]["value"]
        chip = a_clock([FROZEN])
        opened(chip, epson.READ_MODE, epson.S1)

        # Act
        visited = [stepped(chip) for _ in range(printed + 1)]

        # Assert
        self.assertEqual(visited, [*range(printed), 0])

    def test_a_register_holds_the_printed_number_of_bits(self) -> None:
        # Arrange
        printed = FACTS["registerWidthBits"]["value"]
        chip = a_clock([FROZEN])
        written(chip, epson.MI1, 0xFF)

        # Act
        answered = read_back(chip, epson.MI1)

        # Assert
        self.assertEqual(answered, 2**printed - 1)

    def test_the_printed_write_code_opens_a_session_that_writes(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        chip.write(epson.ENABLE, 0x01)
        chip.write(epson.DATA, FACTS["writeModeCode"]["value"])
        chip.write(epson.DATA, epson.MI1)

        # Act
        chip.write(epson.DATA, 0x05)

        # Assert
        self.assertEqual(chip.store.read(epson.MI1), 0x05)

    def test_the_printed_read_code_opens_a_session_that_reads(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, epson.MI1, 0x07)
        chip.write(epson.ENABLE, 0x01)
        chip.write(epson.DATA, FACTS["readModeCode"]["value"])
        chip.write(epson.DATA, epson.MI1)

        # Act
        answered = chip.read(epson.DATA)

        # Assert
        self.assertEqual(answered, 0x07)

    def test_every_other_mode_code_leaves_the_data_that_follows_disregarded(self) -> None:
        # Arrange
        named = {FACTS["writeModeCode"]["value"], FACTS["readModeCode"]["value"]}
        others = [code for code in range(epson.NIBBLE + 1) if code not in named]

        # Act
        ignored = all(disregarded(code) for code in others)

        # Assert
        self.assertEqual(ignored, FACTS["otherModeCodesIgnored"]["value"])

    def test_nibbles_after_the_first_land_at_the_following_addresses(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])

        # Act
        written(chip, epson.MI1, 1, 2, 3)

        # Assert
        landed = [chip.store.read(at) for at in (epson.MI1, epson.MI10, epson.H1)]
        self.assertEqual(landed == [1, 2, 3], FACTS["addressAutoIncrements"]["value"])

    def test_the_registers_come_up_holding_whatever_the_seed_left(self) -> None:
        # Arrange
        seeds = (1, 2)

        # Act
        seen = [registers_at_power_on(seed) for seed in seeds]

        # Assert
        self.assertEqual(seen[0] != seen[1], FACTS["powerOnStateUndefined"]["value"])

    def test_a_digit_carries_into_the_next_one_at_ten(self) -> None:
        # Arrange
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, epson.S1, 9, 0, *DIGITS[2:])
        hand[0] += 1

        # Act
        chip.write(epson.ENABLE, 0x00)

        # Assert
        carried = (chip.digit(epson.S1), chip.digit(epson.S10))
        self.assertEqual("bcd" if carried == (0, 1) else "binary", FACTS["encoding"]["value"])

    def test_an_impossible_value_the_manual_warns_against_can_still_be_set(self) -> None:
        # Arrange
        chip = a_clock([FROZEN])
        written(chip, epson.S1, 0x0C)

        # Act
        answered = read_back(chip, epson.S1)

        # Assert
        self.assertEqual(answered == 0x0C, FACTS["outOfRangeValuesNotSpecified"]["value"])

    def test_each_printed_impossible_date_corrects_to_the_printed_one(self) -> None:
        # Arrange
        examples = FACTS["impossibleDateCorrection"]["examples"]

        # Act
        corrected = [a_second_after(a_day(example["set"])) for example in examples]

        # Assert
        self.assertEqual(corrected, [a_day(example["corrects"]) for example in examples])

    def test_february_gains_a_day_in_a_leap_year_and_only_then(self) -> None:
        # Arrange
        eves = ((2024, 2, 28), (2023, 2, 28))

        # Act
        found = [a_second_after(eve) for eve in eves]

        # Assert
        self.assertEqual(
            found == [(2024, 2, 29), (2023, 3, 1)], FACTS["leapYearCompensation"]["value"]
        )

    def test_every_counted_register_holds_the_top_of_its_printed_range(self) -> None:
        # Arrange
        counted = [row for row in FACTS["registerTable"]["rows"] if row["countRange"]]

        # Act
        held = [the_top_held(row) for row in counted]

        # Assert
        self.assertEqual(held, [row["countRange"][1] for row in counted])

    def test_the_tens_of_hours_counts_to_one_or_to_two_by_notation(self) -> None:
        # Arrange
        row = next(one for one in FACTS["registerTable"]["rows"] if "countRangeQuote" in one)
        low, _, tops = row["countRangeQuote"].partition("~")
        twelve, twenty_four = (int(top) for top in tops.split(","))

        # Act
        seen = (tens_of_hours(0), tens_of_hours(epson.HOURS_24))

        # Assert
        self.assertEqual(
            seen,
            (set(range(int(low), twelve + 1)), set(range(row["countRange"][0], twenty_four + 1))),
        )

    def test_the_weekday_counts_up_to_six_and_back_to_zero(self) -> None:
        # Arrange
        low, high = FACTS["weekdayCountsZeroToSix"]["value"]

        # Act
        counted = weekdays_counted(high - low + 1)

        # Assert
        self.assertEqual(counted, [*range(low + 1, high + 1), low])

    def test_the_oscillator_flag_can_be_set_and_cleared_by_writing_it(self) -> None:
        # Arrange
        address, mask = located(FACTS["oscFlag"]["bit"])

        # Act
        kept = flag_written(address, (mask | 0x1, 0x1))

        # Assert
        self.assertEqual(kept, [mask | 0x1, 0x1])

    def test_a_second_ticking_while_ce_is_high_raises_every_read_flag(self) -> None:
        # Arrange
        flags = [located(one) for one in FACTS["readFlag"]["bit"].split(",")]
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, epson.S1, *DIGITS)
        chip.write(epson.ENABLE, 0x00)
        hand[0] += 5
        opened(chip, epson.WRITE_MODE, epson.CF)

        # Act
        chip.write(epson.DATA, epson.HOURS_24)

        # Assert
        self.assertEqual(
            [chip.store.read(address) & mask for address, mask in flags],
            [mask for _, mask in flags],
        )

    def test_ce_falling_clears_every_read_flag(self) -> None:
        # Arrange
        flags = [located(one) for one in FACTS["readFlag"]["bit"].split(",")]
        chip = a_clock([FROZEN])
        for address, mask in flags:
            chip.store.write(address, chip.store.read(address) | mask)

        # Act
        chip.write(epson.ENABLE, 0x00)

        # Assert
        self.assertEqual(
            [chip.store.read(address) & mask for address, mask in flags], [0] * len(flags)
        )

    def test_the_afternoon_bit_is_one_for_pm_and_zero_for_am(self) -> None:
        # Arrange
        _, afternoon = located(FACTS["pmAmBit"]["bit"])

        # Act
        read = (hour_read(0, afternoon), hour_read(0, 0))

        # Assert
        self.assertEqual(read, (15, 3))

    def test_releasing_hold_hands_back_one_second_however_long_it_lasted(self) -> None:
        # Arrange
        hold = FACTS["controlRegisterD"]["bits"]["hold"]["mask"]
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, epson.S1, *DIGITS)
        written(chip, epson.CD, epson.CAL_HW | hold)
        hand[0] += 300

        # Act
        written(chip, epson.CD, epson.CAL_HW)

        # Assert
        self.assertEqual(
            (chip.digit(epson.S1), chip.digit(epson.MI1)),
            (DIGITS[epson.S1] + 1, DIGITS[epson.MI1]),
        )

    def test_the_thirty_second_adjust_rounds_to_the_nearer_minute_and_clears(self) -> None:
        # Arrange
        mask = FACTS["controlRegisterD"]["bits"]["thirtySecondAdjust"]["mask"]

        # Act
        rounded = (adjusted(29, mask), adjusted(30, mask))

        # Assert
        self.assertEqual(rounded, ((0, DIGITS[epson.MI1], 0), (0, DIGITS[epson.MI1] + 1, 0)))

    def test_reset_zeroes_the_seconds_and_forces_the_test_bit_down(self) -> None:
        # Arrange
        reset = FACTS["controlRegisterF"]["bits"]["reset"]["mask"]
        chip = a_clock([FROZEN], control_f=epson.HOURS_24 | epson.TEST)
        written(chip, epson.S1, 5, 2, *DIGITS[2:])
        opened(chip, epson.WRITE_MODE, epson.CF)

        # Act
        chip.write(epson.DATA, epson.HOURS_24 | epson.TEST | reset)

        # Assert
        self.assertEqual(
            (chip.digit(epson.S1), chip.digit(epson.S10), chip.store.read(epson.CF) & epson.TEST),
            (0, 0, 0),
        )

    def test_reset_stops_the_clock_until_it_is_cleared(self) -> None:
        # Arrange
        reset = FACTS["controlRegisterF"]["bits"]["reset"]["mask"]

        # Act
        moved = (
            hours_moved(epson.HOURS_24 | reset),
            hours_moved(epson.HOURS_24 | reset, epson.HOURS_24),
        )

        # Assert
        self.assertEqual(moved, (0, 1))

    def test_stop_stops_the_clock_until_it_is_cleared(self) -> None:
        # Arrange
        stop = FACTS["controlRegisterF"]["bits"]["stop"]["mask"]

        # Act
        moved = (
            hours_moved(epson.HOURS_24 | stop),
            hours_moved(epson.HOURS_24 | stop, epson.HOURS_24),
        )

        # Assert
        self.assertEqual(moved, (0, 1))

    def test_the_notation_bit_chooses_twenty_four_hours_when_set(self) -> None:
        # Arrange
        notation = FACTS["controlRegisterF"]["bits"]["twentyFourTwelve"]["mask"]

        # Act
        read = (hour_read(notation, epson.PM), hour_read(0, epson.PM))

        # Assert
        self.assertEqual(read, (3, 15))

    def test_the_test_bit_is_cleared_when_ce_falls(self) -> None:
        # Arrange
        test = FACTS["controlRegisterF"]["bits"]["test"]["mask"]
        chip = a_clock([FROZEN])
        written(chip, epson.CF, epson.HOURS_24 | test)

        # Act
        chip.write(epson.ENABLE, 0x00)

        # Assert
        self.assertEqual(chip.store.read(epson.CF) & test, 0)

    def test_the_twenty_bit_cannot_be_written_in_twelve_hour_notation(self) -> None:
        # Arrange
        fact = FACTS["twelveHourNotation"]
        address, bit = named_bit(fact["bit"])
        chip = a_clock([FROZEN], control_f=0)
        written(chip, address, bit | 0x1)

        # Act
        answered = read_back(chip, address)

        # Assert
        self.assertEqual((int(bool(answered & bit)), answered & 0x1), (fact["reads"], 0x1))

    def test_and_the_clock_never_increments_it(self) -> None:
        # Arrange
        fact = FACTS["twelveHourNotation"]
        address, bit = named_bit(fact["bit"])
        hand = [FROZEN]
        chip = a_clock(hand, control_f=0)
        written(chip, epson.S1, *DIGITS)

        # Act
        seen = []
        for _ in range(24):
            hand[0] += HOUR
            chip.write(epson.ENABLE, 0x00)
            seen.append(int(bool(chip.store.read(address) & bit)))

        # Assert
        self.assertEqual(seen, [fact["reads"]] * 24)

    def test_a_write_to_the_afternoon_bit_is_disregarded_in_twenty_four_hour_notation(
        self,
    ) -> None:
        # Arrange
        fact = FACTS["twentyFourHourNotation"]
        address, bit = named_bit(fact["bit"])
        chip = a_clock([FROZEN])

        # Act
        written(chip, address, bit | 0x1)

        # Assert
        self.assertEqual(
            (int(bool(chip.store.read(address) & bit)), chip.digit(address)), (fact["reads"], 1)
        )

    def test_and_the_afternoon_bit_reads_zero_whatever_the_register_holds(self) -> None:
        # Arrange
        fact = FACTS["twentyFourHourNotation"]
        address, bit = named_bit(fact["bit"])
        chip = a_clock([FROZEN])
        chip.store.write(address, bit | 0x1)

        # Act
        answered = read_back(chip, address)

        # Assert
        self.assertEqual((int(bool(answered & bit)), answered & 0x1), (fact["reads"], 0x1))

    def test_with_the_calendar_off_the_read_flags_beside_the_date_keep_what_was_written(
        self,
    ) -> None:
        # Arrange
        dated = FACTS["controlRegisterD"]["bits"]["calHw"]["mask"]
        chip = a_clock([FROZEN], control_d=epson.CAL_HW & ~dated)
        written(chip, epson.D10, epson.READ_FLAG)
        written(chip, epson.MO10, epson.READ_FLAG)

        # Act
        chip.write(epson.ENABLE, 0x00)

        # Assert
        self.assertEqual(
            [chip.store.read(at) & epson.READ_FLAG for at in (epson.D10, epson.MO10)],
            [epson.READ_FLAG] * 2,
        )

    def test_and_a_tick_does_not_raise_them(self) -> None:
        # Arrange
        dated = FACTS["controlRegisterD"]["bits"]["calHw"]["mask"]
        hand = [FROZEN]
        chip = a_clock(hand, control_d=epson.CAL_HW & ~dated)
        written(chip, epson.S1, *DIGITS)
        chip.write(epson.ENABLE, 0x00)
        hand[0] += 5
        opened(chip, epson.WRITE_MODE, epson.CF)

        # Act
        chip.write(epson.DATA, epson.HOURS_24)

        # Assert
        self.assertEqual(
            [chip.store.read(at) & epson.READ_FLAG for at in (epson.MI10, epson.D10, epson.MO10)],
            [epson.READ_FLAG, 0, 0],
        )

    def test_a_write_to_the_interrupt_flag_is_not_executed(self) -> None:
        # Arrange
        fact = FACTS["controlRegisterD"]["bits"]["irqF"]
        chip = a_clock([FROZEN])
        written(chip, epson.CD, epson.CAL_HW | fact["mask"])

        # Act
        answered = read_back(chip, epson.CD)

        # Assert
        self.assertEqual(answered & fact["mask"], 0 if fact["readOnly"] else fact["mask"])

    def test_the_period_increment_raises_the_interrupt_flag_until_cd_is_read(self) -> None:
        # Arrange
        flag = FACTS["controlRegisterD"]["bits"]["irqF"]["mask"]
        hand = [FROZEN]
        chip = a_clock(hand)
        written(chip, epson.S1, *DIGITS)
        written(chip, epson.CE, EVERY_SECOND)
        chip.write(epson.ENABLE, 0x00)
        hand[0] += 1
        chip.write(epson.ENABLE, 0x00)

        # Act
        answered = (read_back(chip, epson.CD), read_back(chip, epson.CD))

        # Assert
        self.assertEqual((answered[0] & flag, answered[1] & flag), (flag, 0))

    def test_under_mask_the_period_increment_leaves_the_interrupt_flag_down(self) -> None:
        # Arrange
        mask = PERIOD_BITS["mask"]["mask"]

        # Act
        raised = (
            flag_after_a_second(EVERY_SECOND, DIGITS[:6]),
            flag_after_a_second(EVERY_SECOND | mask, DIGITS[:6]),
        )

        # Assert
        self.assertEqual(raised, (epson.IRQ_F, 0))

    def test_and_setting_mask_puts_down_a_flag_already_raised(self) -> None:
        # Arrange
        mask = PERIOD_BITS["mask"]["mask"]
        chip = a_clock([FROZEN], control_d=epson.CAL_HW | epson.IRQ_F)

        # Act
        written(chip, epson.CE, EVERY_SECOND | mask)

        # Assert
        self.assertEqual(chip.store.read(epson.CD) & epson.IRQ_F, 0)

    def test_interrupt_cycle_mode_holds_the_flag_and_fixed_period_mode_does_not(self) -> None:
        # Arrange
        interrupt_cycle = PERIOD_BITS["intStnd"]["mask"]
        every_second = PERIOD_BITS["t0"]["mask"]

        # Act
        raised = (
            flag_after_a_second(every_second | interrupt_cycle, DIGITS[:6]),
            flag_after_a_second(every_second, DIGITS[:6]),
        )

        # Assert
        self.assertEqual(raised, (epson.IRQ_F, 0))

    def test_each_printed_period_raises_the_flag_when_its_digit_increments(self) -> None:
        # Arrange
        rows = FACTS["controlRegisterE"]["periodTable"]["rows"]
        chosen = [
            epson.INT_STND
            | (PERIOD_BITS["t1"]["mask"] if row["t1"] else 0)
            | (PERIOD_BITS["t0"]["mask"] if row["t0"] else 0)
            for row in rows
        ]

        # Act
        raised = [
            tuple(
                bool(flag_after_a_second(control_e, start))
                for start in (A_SECOND_TURNING, A_MINUTE_TURNING, AN_HOUR_TURNING)
            )
            for control_e in chosen
        ]

        # Assert
        seconds = [period_in_seconds(row["period"]) for row in rows]
        self.assertEqual(raised, [(period <= 1, period <= 60, True) for period in seconds])


if __name__ == "__main__":
    unittest.main()
