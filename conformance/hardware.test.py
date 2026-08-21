"""Hold the model's own constants to what the manufacturer printed.

A datasheet figure quoted in a docstring rots and cannot fail. This file is what
turns hardware.json from a record of a reading into a gate: every constant the
Epson manual settles is checked against the entry that carries its quote, so a
constant edited without the document is a failing test rather than a silent
change of claim.

The Sharp part has no manufacturer document. Its block is checked for saying so,
and for still saying so, because the failure this guards against is somebody
later filling it in from an emulator and leaving it looking documented.
"""

import json
import sys
import unittest
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


class DocumentTest(unittest.TestCase):
    def test_the_epson_part_is_backed_by_a_named_document(self) -> None:
        self.assertEqual(EPSON["document"]["publisher"], "Seiko Epson Corporation")

    def test_the_document_carries_a_digest_so_the_reading_can_be_repeated(self) -> None:
        self.assertRegex(EPSON["document"]["sha256"], r"^[0-9a-f]{64}$")

    def test_and_a_second_document_that_corroborates_the_register_table(self) -> None:
        self.assertRegex(EPSON["document"]["corroboration"]["sha256"], r"^[0-9a-f]{64}$")

    def test_the_two_documents_are_not_the_same_file(self) -> None:
        self.assertNotEqual(
            EPSON["document"]["sha256"], EPSON["document"]["corroboration"]["sha256"]
        )

    def test_every_fact_carries_the_sentence_it_came_from(self) -> None:
        unquoted = [
            name for name, fact in FACTS.items() if isinstance(fact, dict) and not _quoted(fact)
        ]

        self.assertEqual(unquoted, [])


def _quoted(fact: object) -> bool:
    """Whether a fact, or anything nested inside it, carries a verbatim quote."""
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

        self.assertFalse(epson.Clock(held).stopped())

    def test_the_stopping_bits_are_named_in_control_register_f_and_not_in_d(self) -> None:
        stopping = {"reset", "stop"}

        self.assertEqual(stopping & set(FACTS["controlRegisterD"]["bits"]), set())

    def test_control_register_d_has_no_bit_that_adds_a_second(self) -> None:
        named = set(FACTS["controlRegisterD"]["bits"])

        self.assertEqual(named, {"hold", "calHw", "irqF", "thirtySecondAdjust"})


class ContradictionTest(unittest.TestCase):
    """The half of the register table that is easy to get wrong and never fails loudly."""

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
    """Every declared divergence has to be answerable, not merely written down."""

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


if __name__ == "__main__":
    unittest.main()
