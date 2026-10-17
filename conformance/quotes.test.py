import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, override

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import quotes, reading  # noqa: E402

PRINTED = "the quick brown fox jumps over the lazy dog and then keeps running for a while"


class WindowTest(unittest.TestCase):
    def test_a_quote_shorter_than_the_window_is_one_window(self) -> None:
        # Arrange
        quote = "a b c"

        # Act
        found = quotes.windows(quote)

        # Assert
        self.assertEqual(found, [reading.flatten(quote)])

    def test_a_longer_one_is_scored_on_overlapping_runs(self) -> None:
        found = quotes.windows(PRINTED)

        self.assertEqual(len(found), len(PRINTED.split()) - quotes.WINDOW + 1)


class ReadingTest(unittest.TestCase):
    def test_a_quote_is_found_where_it_sits(self) -> None:
        found = quotes.said({"quote": "hello"}, "here")

        self.assertEqual(found, [("here.quote", "hello")])

    def test_a_key_that_merely_ends_in_quote_is_read_too(self) -> None:
        found = quotes.said({"unusedBitsQuote": "hello"})

        self.assertEqual(found, [("unusedBitsQuote", "hello")])

    def test_a_list_of_quotes_is_read_item_by_item(self) -> None:
        found = quotes.said({"quotes": ["one", "two"]})

        self.assertEqual([where for where, _ in found], ["quotes[0]", "quotes[1]"])

    def test_a_list_entry_that_is_not_a_sentence_is_left_alone(self) -> None:
        found = quotes.said({"quotes": ["one", 2]})

        self.assertEqual(len(found), 1)

    def test_a_plural_key_of_its_own_name_holds_several(self) -> None:
        found = quotes.said({"aboutQuotes": ["one", "two"]})

        self.assertEqual(found, [("aboutQuotes[0]", "one"), ("aboutQuotes[1]", "two")])

    def test_and_a_numbered_map_of_them_keeps_the_number_printed_beside_each(self) -> None:
        found = quotes.said({"noteQuotes": {"1": "first", "14": "fourteenth"}})

        self.assertEqual(found, [("noteQuotes.1", "first"), ("noteQuotes.14", "fourteenth")])

    def test_a_numbered_map_carrying_something_that_is_not_a_passage_skips_it(self) -> None:
        found = quotes.said({"noteQuotes": {"1": "first", "2": 2}})

        self.assertEqual(found, [("noteQuotes.1", "first")])

    def test_a_quote_inside_a_list_of_objects_is_reached(self) -> None:
        found = quotes.said([{"quote": "hello"}])

        self.assertEqual(found, [("[0].quote", "hello")])

    def test_a_table_flattened_into_prose_is_left_out(self) -> None:
        found = quotes.said({"quote": "Table 21", "assembled": True})

        self.assertEqual(found, [])

    def test_the_records_hold_quotes_to_look_for(self) -> None:
        self.assertGreater(len(quotes.quoted()), 0)

    def test_a_quote_the_recording_made_is_not_one_to_look_for(self) -> None:
        found = quotes.quoted([("made-up.json", {"referenceDoes": {"quote": "hello"}})])

        self.assertEqual(found, [])

    def test_but_one_the_manufacturer_made_is(self) -> None:
        found = quotes.quoted([("made-up.json", {"documentSays": {"quote": "hello"}})])

        self.assertEqual(found, [("made-up.json.documentSays.quote", "hello")])

    def test_and_none_of_them_comes_from_the_recording(self) -> None:
        stray = [where for where, _ in quotes.quoted() if "referenceDoes" in where]

        self.assertEqual(stray, [])


class RecognisedReadingTest(unittest.TestCase):
    QUOTE = "Set the timing of the interrupt cycle mode or fixed-period waveform mode."

    def test_a_reading_one_letter_off_is_searched_for_instead_of_the_quote(self) -> None:
        # Arrange
        read = ["Set the timing of the interrupt cycle made", "or fixed-period waveform mode."]

        # Act
        found = quotes.said({"quote": self.QUOTE, reading.RECOGNISED: read})

        # Assert
        self.assertEqual(
            found,
            [("quote.recognisedAs[0]", read[0]), ("quote.recognisedAs[1]", read[1])],
        )

    def test_a_reading_that_drifts_further_leaves_the_quote_to_be_searched(self) -> None:
        # Arrange
        read = ["Set the tuning of the interrupt cycle made or fixed-period waveform mode."]

        # Act
        found = quotes.said({"quote": self.QUOTE, reading.RECOGNISED: read})

        # Assert
        self.assertEqual(found, [("quote", self.QUOTE)])

    def test_a_reading_beside_a_supporting_quote_is_not_applied_to_it(self) -> None:
        # Arrange
        read = ["Set the timing of the interrupt cycle made or fixed-period waveform mode."]

        # Act
        found = quotes.said({"maskQuote": self.QUOTE, reading.RECOGNISED: read})

        # Assert
        self.assertEqual(found, [("maskQuote", self.QUOTE)])

    def test_the_reading_is_not_reported_as_words_borrowed_under_a_key_nobody_checks(
        self,
    ) -> None:
        # Arrange
        read = ["Set the timing of the interrupt cycle made or fixed-period waveform mode."]
        held = ("held.json", {"facts": {"a": {reading.RECOGNISED: read}}})

        # Act
        found = quotes.borrowed([held], {"fax.pdf": reading.flatten(read[0])})

        # Assert
        self.assertEqual(found, [])


class LibraryTest(unittest.TestCase):
    def test_a_machine_with_no_documents_has_an_empty_library(self) -> None:
        self.assertEqual(quotes.library(ROOT / "no such folder"), {})

    def test_a_folder_of_documents_is_read_once_each(self) -> None:
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (folder / "one.pdf").write_bytes(b"not really a pdf")

        self.assertEqual(list(quotes.library(folder)), ["one.pdf"])

    def test_something_that_cannot_be_read_yields_no_text(self) -> None:
        self.assertEqual(quotes.readable(ROOT / "no such file.pdf"), "")

    def test_and_a_machine_with_no_reader_installed_checks_nothing(self) -> None:
        found = quotes.readable(ROOT / "anything.pdf", self.refuse)

        self.assertEqual(found, "")

    def test_a_reader_that_answers_gives_back_what_it_read(self) -> None:
        found = quotes.readable(ROOT / "anything.pdf", self.answering("Hello, World."))

        self.assertEqual(found, "helloworld")

    def test_a_reading_left_beside_the_document_is_pooled_with_it(self) -> None:
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (folder / "one.pdf").write_bytes(b"")
        (folder / "one.txt").write_text("from the pages")

        found = quotes.readable(folder / "one.pdf", self.answering("from the layer"))

        self.assertEqual(found, "fromthelayerfromthepages")

    def test_and_nothing_is_pooled_when_nobody_has_read_the_pages(self) -> None:
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (folder / "one.pdf").write_bytes(b"")

        found = quotes.readable(folder / "one.pdf", self.answering("only the layer"))

        self.assertEqual(found, "onlythelayer")

    @staticmethod
    def answering(text: str) -> Any:
        class Answered:
            stdout = text

        def reader(*rest: object, **named: object) -> Answered:
            return Answered()

        return reader

    @staticmethod
    def refuse(*rest: object, **named: object) -> None:
        raise FileNotFoundError("pdftotext")


class VerdictTest(unittest.TestCase):
    def test_a_quote_that_places_enough_windows_is_found(self) -> None:
        self.assertTrue(quotes.Verdict("a", "b", "doc", 5, 10).found)

    def test_one_that_places_too_few_is_not(self) -> None:
        self.assertFalse(quotes.Verdict("a", "b", "doc", 1, 10).found)

    def test_and_a_quote_with_no_windows_at_all_is_not(self) -> None:
        self.assertFalse(quotes.Verdict("a", "b", None, 0, 0).found)


class VerifyTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.books = {"real.pdf": reading.flatten(PRINTED)}

    def test_a_sentence_the_document_carries_is_located(self) -> None:
        found = quotes.verify([("here", PRINTED)], self.books)

        self.assertEqual((found[0].found, found[0].document), (True, "real.pdf"))

    def test_a_sentence_it_does_not_is_reported(self) -> None:
        found = quotes.verify([("here", "nothing at all like the printed page here")], self.books)

        self.assertEqual((found[0].found, found[0].document), (False, None))

    def test_the_best_of_several_documents_is_the_one_named(self) -> None:
        # Arrange
        books = {"poor.pdf": reading.flatten("the quick brown"), **self.books}

        # Act
        found = quotes.verify([("here", PRINTED)], books)

        # Assert
        self.assertEqual(found[0].document, "real.pdf")


class ReportTest(unittest.TestCase):
    def test_a_run_with_no_documents_says_it_checked_nothing(self) -> None:
        said = quotes.report([quotes.Verdict("a", "b", None, 0, 3)], 0)

        self.assertIn("none was checked", said)

    def test_a_clean_run_still_says_how_much_it_checked(self) -> None:
        said = quotes.report([quotes.Verdict("a", "b", "doc", 3, 3)], 1)

        self.assertIn("1 quotes against 1 documents, 1 located, 0 not", said)

    def test_a_missing_quote_is_named_with_its_score(self) -> None:
        said = quotes.report([quotes.Verdict("here", "text", "doc", 1, 9)], 1)

        self.assertIn("placed 1 of 9 windows (best in doc)", said)

    def test_and_one_no_document_could_place_names_none(self) -> None:
        said = quotes.report([quotes.Verdict("here", "text", None, 0, 9)], 1)

        self.assertIn("placed 0 of 9 windows", said)


class EntryPointTest(unittest.TestCase):
    def run_with(self, books: dict[str, str], held: list[tuple[str, str]]) -> tuple[int, str]:
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            status = quotes.main(books, held)
        return status, printed.getvalue()

    def test_with_no_documents_it_asks_for_nothing(self) -> None:
        status, said = self.run_with({}, [("here", PRINTED)])

        self.assertEqual((status, "none was checked" in said), (0, True))

    def test_with_documents_and_every_quote_placed_it_passes(self) -> None:
        # Arrange
        books = {"real.pdf": reading.flatten(PRINTED)}

        # Act
        status, said = self.run_with(books, [("here", PRINTED)])

        # Assert
        self.assertEqual((status, "0 not" in said), (0, True))

    def test_a_sentence_no_document_carries_asks_for_a_person(self) -> None:
        # Arrange
        books = {"real.pdf": reading.flatten(PRINTED)}

        # Act
        status, said = self.run_with(books, [("here", "absent")])

        # Assert
        self.assertEqual((status, "1 not" in said), (1, True))


if __name__ == "__main__":
    unittest.main()
