import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, ClassVar

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import quotes, reading  # noqa: E402


class AttributionTest(unittest.TestCase):
    def a_record(self, cited: str, quote: str) -> tuple[str, object]:
        return (
            "held.json",
            {
                "documents": {
                    "right": {"file": "right.pdf"},
                    "wrong": {"file": "wrong.pdf"},
                },
                "facts": {"a": {"document": cited, "quote": quote}},
            },
        )

    BOOKS: ClassVar[dict[str, str]] = {
        "right.pdf": reading.flatten(
            "the quick brown fox jumps over the lazy dog and keeps running"
        ),
        "wrong.pdf": reading.flatten("nothing here resembles the sentence above in any way at all"),
    }

    def test_a_quote_in_the_document_it_names_is_accepted(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        found = quotes.misattributed(
            [self.a_record("right", "the quick brown fox jumps over the lazy dog")], self.BOOKS
        )

        # Assert
        self.assertEqual(found, expected)

    def test_a_quote_that_lives_in_another_document_is_reported(self) -> None:
        # Arrange
        expected = 1

        # Act
        found = quotes.misattributed(
            [self.a_record("wrong", "the quick brown fox jumps over the lazy dog")], self.BOOKS
        )

        # Assert
        self.assertEqual(len(found), expected)
        self.assertIn("right.pdf", found[0])

    def test_a_quote_in_no_document_at_all_is_left_to_the_other_check(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        found = quotes.misattributed(
            [self.a_record("right", "a sentence that appears in neither of them anywhere")],
            self.BOOKS,
        )

        # Assert
        self.assertEqual(found, expected)

    def test_a_document_with_no_file_on_this_machine_is_skipped(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        held = (
            "held.json",
            {
                "documents": {"right": {"file": "absent.pdf"}},
                "facts": {"a": {"document": "right", "quote": "the quick brown fox jumps"}},
            },
        )

        # Assert
        self.assertEqual(quotes.misattributed([held], self.BOOKS), expected)

    def test_a_record_declaring_no_files_is_left_alone(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        held = ("held.json", {"facts": {"a": {"document": "x", "quote": "the quick brown fox"}}})

        # Assert
        self.assertEqual(quotes.misattributed([held], self.BOOKS), expected)

    def test_an_entry_saying_nothing_has_no_quote_to_place(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        held = (
            "held.json",
            {
                "documents": {"right": {"file": "right.pdf"}},
                "facts": {
                    "a": {"document": "right", "quote": "nothing at all", "saysNothing": True}
                },
            },
        )

        # Assert
        self.assertEqual(quotes.misattributed([held], self.BOOKS), expected)

    def test_a_declared_document_naming_no_file_cannot_be_checked(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        held = (
            "held.json",
            {
                "documents": {"right": {"file": "right.pdf"}, "paperOnly": {"title": "no file"}},
                "facts": {"a": {"document": "paperOnly", "quote": "the quick brown fox jumps"}},
            },
        )

        # Assert
        self.assertEqual(quotes.misattributed([held], self.BOOKS), expected)

    def test_the_records_on_disk_are_all_where_they_say_they_are(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        found = quotes.misattributed()

        # Assert
        self.assertEqual(found, expected)


class PhantomTableTest(unittest.TestCase):
    TABLES: ClassVar[dict[str, set[str]]] = {
        "right.pdf": {"4-1", "7-1"},
        "other.pdf": {"6-5", "6-76"},
    }

    def a_record(self, document: str, section: str) -> tuple[str, dict[str, Any]]:
        return (
            "held.json",
            {
                "documents": {"right": {"file": "right.pdf"}, "other": {"file": "other.pdf"}},
                "facts": {"a": {"document": document, "section": section}},
            },
        )

    def test_a_table_the_named_document_has_is_accepted(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        found = quotes.phantom([self.a_record("right", "Table 4-1 Addressing Mode")], self.TABLES)

        # Assert
        self.assertEqual(found, expected)

    def test_a_table_only_another_document_has_is_reported(self) -> None:
        # Arrange
        expected = 1

        # Act
        found = quotes.phantom([self.a_record("right", "Table 6-5 note 6")], self.TABLES)

        # Assert
        self.assertEqual(len(found), expected)
        self.assertIn("other.pdf", found[0])

    def test_a_table_no_document_has_is_reported_without_a_destination(self) -> None:
        # Arrange
        expected = 1

        # Act
        found = quotes.phantom([self.a_record("right", "Table 9-9")], self.TABLES)

        # Assert
        self.assertEqual(len(found), expected)
        self.assertNotIn("and it is in", found[0])

    def test_a_section_naming_two_tables_is_checked_on_both(self) -> None:
        # Arrange
        expected = 1

        # Act
        found = quotes.phantom(
            [self.a_record("right", "Table 7-1, with Table 6-5 for the cycle counts")], self.TABLES
        )

        # Assert
        self.assertEqual(len(found), expected)
        self.assertIn("Table 6-5", found[0])

    def test_a_section_named_in_prose_is_left_alone(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        found = quotes.phantom([self.a_record("right", "3.13 Reset (RESB)")], self.TABLES)

        # Assert
        self.assertEqual(found, expected)

    def test_a_longer_table_number_does_not_pass_off_as_a_shorter_one(self) -> None:
        # Arrange
        expected = 1

        # Act
        found = quotes.phantom([self.a_record("other", "Table 6-7")], self.TABLES)

        # Assert
        self.assertEqual(len(found), expected)

    def test_a_bare_table_number_is_not_satisfied_by_a_subdivided_one(self) -> None:
        # Arrange
        expected = 1

        # Act
        found = quotes.phantom([self.a_record("other", "Table 6. ALU Field")], self.TABLES)

        # Assert
        self.assertEqual(len(found), expected)
        self.assertIn("Table 6,", found[0])

    def test_a_document_whose_reading_names_no_table_is_skipped(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        found = quotes.phantom(
            [self.a_record("right", "Table 6-5")], {"right.pdf": set(), "other.pdf": {"6-5"}}
        )

        # Assert
        self.assertEqual(found, expected)

    def test_a_document_with_no_file_on_this_machine_is_skipped(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        held = (
            "held.json",
            {
                "documents": {"gone": {"file": "absent.pdf"}},
                "facts": {"a": {"document": "gone", "section": "Table 6-5"}},
            },
        )

        # Assert
        self.assertEqual(quotes.phantom([held], self.TABLES), expected)

    def test_a_record_declaring_no_files_is_left_alone(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        held = ("held.json", {"facts": {"a": {"document": "right", "section": "Table 6-5"}}})

        # Assert
        self.assertEqual(quotes.phantom([held], self.TABLES), expected)

    def test_a_document_the_record_never_declared_is_skipped(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        found = quotes.phantom([self.a_record("unheard-of", "Table 6-5")], self.TABLES)

        # Assert
        self.assertEqual(found, expected)

    def test_the_walk_reaches_a_section_inside_a_list(self) -> None:
        # Arrange
        held = (
            "held.json",
            {
                "documents": {"right": {"file": "right.pdf"}},
                "facts": {"a": {"alsoSays": [{"document": "right", "section": "Table 6-5"}]}},
            },
        )

        # Act
        found = quotes.phantom([held], self.TABLES)

        # Assert
        self.assertEqual(len(found), 1)
        self.assertIn("alsoSays[0]", found[0])

    def test_the_records_on_disk_name_no_table_their_document_lacks(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        found = quotes.phantom()

        # Assert
        self.assertEqual(found, expected)


class TableCatalogueTest(unittest.TestCase):
    def answering(self, text: str) -> Any:
        def run(*_: Any, **__: Any) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess([], 0, stdout=text, stderr="")

        return run

    def refuse(self, *_: Any, **__: Any) -> subprocess.CompletedProcess[str]:
        raise OSError("no pdftotext here")

    def test_the_tables_a_document_names_are_collected(self) -> None:
        # Arrange
        expected = {"4-1", "7-1"}

        # Act
        found = quotes.labelled(ROOT / "one.pdf", self.answering("see Table 4-1 and Table 7-1"))

        # Assert
        self.assertEqual(found, expected)

    def test_a_machine_without_the_reader_reports_nothing_rather_than_raising(self) -> None:
        # Arrange
        given = ROOT / "one.pdf"

        # Act
        found = quotes.labelled(given, self.refuse)

        # Assert
        self.assertEqual(found, set())

    def test_a_second_reading_beside_the_document_is_pooled_in(self) -> None:
        # Arrange
        expected = {"4-1", "9-9"}

        # Act
        with tempfile.TemporaryDirectory() as where:
            folder = Path(where)
            (folder / "one.pdf").write_bytes(b"")
            (folder / "one.txt").write_text("and Table 9-9 from the scanned pages")
            found = quotes.labelled(folder / "one.pdf", self.answering("Table 4-1"))

        # Assert
        self.assertEqual(found, expected)

    def test_a_folder_that_is_not_there_yields_no_catalogue(self) -> None:
        # Arrange
        given = ROOT / "no such folder"

        # Act
        found = quotes.catalogue(given)

        # Assert
        self.assertEqual(found, {})

    def test_every_pinned_document_is_catalogued(self) -> None:
        # Arrange
        expected = {"one.pdf": {"1-1"}, "two.pdf": {"1-1"}}

        # Act
        with tempfile.TemporaryDirectory() as where:
            folder = Path(where)
            (folder / "one.pdf").write_bytes(b"")
            (folder / "two.pdf").write_bytes(b"")
            found = quotes.catalogue(folder, self.answering("Table 1-1"))

        # Assert
        self.assertEqual(found, expected)


class BorrowedTextTest(unittest.TestCase):
    LONG = "the quick brown fox jumps over the lazy dog and then turns around and runs home"
    BOOKS: ClassVar[dict[str, str]] = {"right.pdf": reading.flatten(LONG)}

    def a_record(self, key: str, text: str) -> tuple[str, dict[str, Any]]:
        return ("held.json", {"facts": {"a": {key: text}}})

    def test_a_passage_under_a_key_the_checker_reads_is_left_alone(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        found = quotes.borrowed([self.a_record("quote", self.LONG)], self.BOOKS)

        # Assert
        self.assertEqual(found, expected)

    def test_and_so_is_one_under_a_plural_key(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        held = ("held.json", {"facts": {"a": {"noteQuotes": {"1": self.LONG}}}})

        # Assert
        self.assertEqual(quotes.borrowed([held], self.BOOKS), expected)

    def test_a_passage_under_any_other_key_is_reported(self) -> None:
        # Arrange
        expected = 1

        # Act
        found = quotes.borrowed([self.a_record("footnote", self.LONG)], self.BOOKS)

        # Assert
        self.assertEqual(len(found), expected)
        self.assertIn("right.pdf", found[0])

    def test_a_short_string_is_left_alone_however_it_is_keyed(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        found = quotes.borrowed([self.a_record("title", "the quick brown fox")], self.BOOKS)

        # Assert
        self.assertEqual(found, expected)

    def test_a_long_string_no_document_carries_is_left_alone(self) -> None:
        # Arrange
        given = "note"

        # Act
        held = self.a_record(
            given, "this sentence was written here and appears in no document " * 2
        )

        # Assert
        self.assertEqual(quotes.borrowed([held], self.BOOKS), [])

    def test_the_walk_reaches_a_string_inside_a_list(self) -> None:
        # Arrange
        held = ("held.json", {"facts": {"a": {"about": ["x", self.LONG]}}})

        # Act
        found = quotes.borrowed([held], self.BOOKS)

        # Assert
        self.assertEqual(len(found), 1)
        self.assertIn("about[1]", found[0])

    def test_a_value_that_is_not_a_string_is_stepped_over(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        held = ("held.json", {"facts": {"a": {"cycles": [2, 3], "ok": True, "n": None}}})

        # Assert
        self.assertEqual(quotes.borrowed([held], self.BOOKS), expected)

    def test_the_records_on_disk_keep_no_document_text_out_of_reach(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        found = quotes.borrowed()

        # Assert
        self.assertEqual(found, expected)


if __name__ == "__main__":
    unittest.main()
