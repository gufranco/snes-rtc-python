import json
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.driving import (
    CF,
    EPSON,
    FACTS,
    FROZEN,
    H10,
    HOURS_24,
    NIBBLE,
    PARTS,
    SHARP,
    SHARP_CONTROL,
    SHARP_DATA,
)
from snesrtc import Chip, Store

DIVERGENCES = Path(__file__).resolve().parent / "divergences.json"

SEQUENCE_LIMIT = 64


def quoted(fact: object) -> bool:
    if isinstance(fact, dict):
        if "quote" in fact:
            return True
        return any(quoted(value) for value in fact.values())
    if isinstance(fact, list):
        return any(quoted(value) for value in fact)
    return False


def source(key: str) -> dict[str, object]:
    held: dict[str, object] = EPSON["documents"][key]
    return held


def divergences() -> list[dict[str, Any]]:
    held: list[dict[str, Any]] = json.loads(DIVERGENCES.read_text())["divergences"]
    return held


def a_sharp_clock() -> Any:
    held = Store(cleared=True)
    held.stamp = FROZEN
    return Chip("s-rtc", held, now=lambda: FROZEN)


def in_twelve_hour_notation() -> Any:
    chip = Chip("rtc-4513", Store())
    chip.store.write(CF, chip.store.read(CF) & ~HOURS_24 & NIBBLE)
    return chip


class DocumentTest(unittest.TestCase):
    def test_the_epson_part_is_backed_by_a_named_document(self) -> None:
        # Arrange
        manual = source("applicationManual")

        # Act
        publisher = manual["publisher"]

        # Assert
        self.assertEqual(publisher, "Seiko Epson Corporation")

    def test_the_document_carries_a_digest_so_the_reading_can_be_repeated(self) -> None:
        # Arrange
        manual = source("applicationManual")

        # Act
        digest = str(manual["sha256"])

        # Assert
        self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_and_a_second_document_that_corroborates_the_register_table(self) -> None:
        # Arrange
        extract = source("catalogueExtract")

        # Act
        digest = str(extract["sha256"])

        # Assert
        self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_the_second_one_says_which_one_it_corroborates(self) -> None:
        # Arrange
        extract = source("catalogueExtract")

        # Act
        corroborated = extract["corroborates"]

        # Assert
        self.assertEqual(corroborated, "applicationManual")

    def test_the_two_documents_are_not_the_same_file(self) -> None:
        # Arrange
        manual, extract = source("applicationManual"), source("catalogueExtract")

        # Act
        digests = {manual["sha256"], extract["sha256"]}

        # Assert
        self.assertEqual(len(digests), 2)

    def test_the_sharp_part_declares_an_empty_block_rather_than_none(self) -> None:
        # Arrange
        part = SHARP

        # Act
        documents = part["documents"]

        # Assert
        self.assertEqual(documents, {})

    def test_every_fact_carries_the_sentence_it_came_from(self) -> None:
        # Arrange
        facts = FACTS.items()

        # Act
        unquoted = [name for name, fact in facts if isinstance(fact, dict) and not quoted(fact)]

        # Assert
        self.assertEqual(unquoted, [])


class QuoteSearchTest(unittest.TestCase):
    def test_a_fact_with_its_own_quote_is_quoted(self) -> None:
        # Arrange
        fact = {"value": 1, "quote": "printed here"}

        # Act
        found = quoted(fact)

        # Assert
        self.assertIs(found, True)

    def test_a_fact_whose_quote_is_nested_deeper_is_quoted_too(self) -> None:
        # Arrange
        fact = {"bits": {"hold": {"quote": "printed here"}}}

        # Act
        found = quoted(fact)

        # Assert
        self.assertIs(found, True)

    def test_and_one_hidden_in_a_list(self) -> None:
        # Arrange
        fact = {"rows": [{"quote": "printed here"}]}

        # Act
        found = quoted(fact)

        # Assert
        self.assertIs(found, True)

    def test_a_bare_value_is_not_a_quote(self) -> None:
        # Arrange
        fact = 16

        # Act
        found = quoted(fact)

        # Assert
        self.assertIs(found, False)

    def test_and_neither_is_a_fact_that_only_asserts(self) -> None:
        # Arrange
        fact = {"value": 16, "why": "because"}

        # Act
        found = quoted(fact)

        # Assert
        self.assertIs(found, False)


class UnverifiedTest(unittest.TestCase):
    def test_the_sharp_part_is_marked_unverified_rather_than_left_looking_documented(
        self,
    ) -> None:
        # Arrange
        part = SHARP

        # Act
        verified = part["verified"]

        # Assert
        self.assertIs(verified, False)

    def test_it_carries_no_document_block(self) -> None:
        # Arrange
        part = SHARP

        # Act
        keys = set(part)

        # Assert
        self.assertNotIn("document", keys)

    def test_it_names_who_asserts_what_it_holds(self) -> None:
        # Arrange
        part = SHARP

        # Act
        unverified = part["unverified"]

        # Assert
        self.assertIn("assertedBy", unverified)

    def test_and_what_would_settle_it(self) -> None:
        # Arrange
        part = SHARP

        # Act
        settling = part["unverified"]["wouldSettleIt"]

        # Assert
        self.assertNotEqual(settling, [])

    def test_its_recorded_facts_are_labelled_as_recorded_rather_than_as_facts(self) -> None:
        # Arrange
        part = SHARP

        # Act
        keys = set(part)

        # Assert
        self.assertNotIn("facts", keys)

    def test_the_model_answers_where_the_recorded_block_says_it_does(self) -> None:
        # Arrange
        recorded = SHARP["recordedFacts"]
        chip = a_sharp_clock()
        chip.write(recorded["controlAddress"], 0x0E)
        idle = chip.read(recorded["dataAddress"])
        chip.write(recorded["controlAddress"], 0x0D)

        # Act
        answered = chip.read(recorded["dataAddress"])

        # Assert
        self.assertEqual((idle, answered), (0x00, recorded["marker"]))

    def test_the_model_carries_the_sequence_length_the_recorded_block_gives(self) -> None:
        # Arrange
        chip = a_sharp_clock()

        # Act
        answered = [chip.read(SHARP_DATA) for _ in range(SEQUENCE_LIMIT)]

        # Assert
        self.assertEqual(answered.index(0x0F, 1) - 1, SHARP["recordedFacts"]["sequenceLength"])

    def test_and_the_marker(self) -> None:
        # Arrange
        chip = a_sharp_clock()

        # Act
        answered = chip.read(SHARP_DATA)

        # Assert
        self.assertEqual(answered, SHARP["recordedFacts"]["marker"])

    def test_and_the_year_base(self) -> None:
        # Arrange
        chip = a_sharp_clock()

        # Act
        moment = chip.read_moment()

        # Assert
        self.assertEqual(moment.year, SHARP["recordedFacts"]["yearBase"])

    def test_and_the_weekday_epoch(self) -> None:
        # Arrange
        chip = a_sharp_clock()
        chip.write(SHARP_CONTROL, 0x0E)
        chip.write(SHARP_CONTROL, 0x00)

        # Act
        for digit in (0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 9):
            chip.write(SHARP_CONTROL, digit)

        # Assert
        self.assertEqual(chip.store.read(12), SHARP["recordedFacts"]["weekdayEpoch"]["value"])


class NotStatedTest(unittest.TestCase):
    def test_the_century_window_is_recorded_as_a_convention_rather_than_a_fact(self) -> None:
        # Arrange
        part = EPSON

        # Act
        unstated = part["notStated"]

        # Assert
        self.assertIn("centuryWindow", unstated)

    def test_the_wrapper_is_recorded_as_undocumented(self) -> None:
        # Arrange
        part = EPSON

        # Act
        unstated = part["notStated"]

        # Assert
        self.assertIn("spc7110Mapping", unstated)

    def test_the_year_pivot_the_model_uses_appears_in_no_fact_block(self) -> None:
        # Arrange
        facts = FACTS

        # Act
        keys = set(facts)

        # Assert
        self.assertNotIn("yearPivot", keys)


class DivergenceTest(unittest.TestCase):
    def test_no_two_entries_share_an_id(self) -> None:
        # Arrange
        entries = divergences()

        # Act
        names = [entry["id"] for entry in entries]

        # Assert
        self.assertEqual(len(names), len(set(names)))

    def test_every_entry_names_the_parts_it_is_about(self) -> None:
        # Arrange
        entries = divergences()

        # Act
        missing = [entry["id"] for entry in entries if not entry.get("parts")]

        # Assert
        self.assertEqual(missing, [])

    def test_every_entry_says_which_side_the_package_follows(self) -> None:
        # Arrange
        entries = divergences()

        # Act
        missing = [entry["id"] for entry in entries if not entry.get("packageFollows")]

        # Assert
        self.assertEqual(missing, [])

    def test_every_open_entry_says_what_would_settle_it(self) -> None:
        # Arrange
        entries = [entry for entry in divergences() if entry["status"] == "open"]

        # Act
        missing = [entry["id"] for entry in entries if not entry.get("wouldSettleIt")]

        # Assert
        self.assertEqual(missing, [])

    def test_every_closed_entry_says_what_would_reopen_it(self) -> None:
        # Arrange
        entries = [entry for entry in divergences() if entry["status"] == "closed"]

        # Act
        missing = [entry["id"] for entry in entries if not entry.get("wouldReopenIt")]

        # Assert
        self.assertEqual(missing, [])

    def test_every_contradiction_quotes_the_document_it_contradicts(self) -> None:
        # Arrange
        entries = [entry for entry in divergences() if entry["severity"] == "contradiction"]

        # Act
        unquoted = [entry["id"] for entry in entries if "quote" not in entry["documentSays"]]

        # Assert
        self.assertEqual(unquoted, [])

    def test_every_entry_that_follows_the_document_is_about_a_documented_part(self) -> None:
        # Arrange
        entries = [
            entry for entry in divergences() if entry["packageFollows"].startswith("document")
        ]

        # Act
        wrong = [
            entry["id"]
            for entry in entries
            if not all(PARTS[name]["verified"] for name in entry["parts"])
        ]

        # Assert
        self.assertEqual(wrong, [])

    def test_the_parts_named_are_parts_the_hardware_file_knows(self) -> None:
        # Arrange
        entries = divergences()

        # Act
        unknown = [
            entry["id"] for entry in entries if any(name not in PARTS for name in entry["parts"])
        ]

        # Assert
        self.assertEqual(unknown, [])


class RecordSaysWhatTheModelDoesTest(unittest.TestCase):
    def test_every_hour_of_the_day_survives_twelve_hour_notation(self) -> None:
        # Arrange
        chip = in_twelve_hour_notation()

        # Act
        read_back = []
        for hour in range(24):
            chip.store_hour(hour)
            read_back.append(chip.hour())

        # Assert
        self.assertEqual(read_back, list(range(24)))

    def test_and_the_tens_of_hours_bit_stays_down_throughout(self) -> None:
        # Arrange
        chip = in_twelve_hour_notation()

        # Act
        tens = []
        for hour in range(24):
            chip.store_hour(hour)
            tens.append(chip.digit(H10) & 0x2)

        # Assert
        self.assertEqual(tens, [0] * 24)

    def test_so_no_entry_calls_that_notation_unmodelled(self) -> None:
        # Arrange
        entries = divergences()

        # Act
        named = [
            one["id"]
            for one in entries
            if "twelve" in str(one["id"]) and "unmodelled" in str(one["id"])
        ]

        # Assert
        self.assertEqual(named, [])

    def test_no_entry_at_all_calls_something_unmodelled_in_its_name(self) -> None:
        # Arrange
        entries = divergences()

        # Act
        named = [one["id"] for one in entries if "unmodelled" in str(one["id"])]

        # Assert
        self.assertEqual(named, [])

    def test_every_entry_carries_a_status_the_family_recognises(self) -> None:
        # Arrange
        allowed = {"open", "closed", "narrowed", "notModelled", "notADisagreement", "acknowledged"}

        # Act
        stray = [one["id"] for one in divergences() if one.get("status") not in allowed]

        # Assert
        self.assertEqual(stray, [])


if __name__ == "__main__":
    unittest.main()
