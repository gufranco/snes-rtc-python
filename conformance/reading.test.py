import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import reading  # noqa: E402

QUOTE = "Set the timing of the interrupt cycle mode or fixed-period waveform mode."


class FlattenTest(unittest.TestCase):
    def test_punctuation_and_spacing_stop_mattering(self) -> None:
        # Arrange
        text = "A, b.  C!"

        # Act
        flat = reading.flatten(text)

        # Assert
        self.assertEqual(flat, "abc")

    def test_a_typographic_dash_reads_as_a_plain_one(self) -> None:
        # Arrange
        text = f"a{chr(0x2014)}b"

        # Act
        flat = reading.flatten(text)

        # Assert
        self.assertEqual(flat, "ab")

    def test_a_curly_quote_reads_as_a_straight_one(self) -> None:
        # Arrange
        text = f"it{chr(0x2019)}s"

        # Act
        flat = reading.flatten(text)

        # Assert
        self.assertEqual(flat, "its")

    def test_and_a_typographic_double_quote_does_too(self) -> None:
        # Arrange
        text = f"{chr(0x201C)}x{chr(0x201D)}"

        # Act
        flat = reading.flatten(text)

        # Assert
        self.assertEqual(flat, "x")


class CloseReadingTest(unittest.TestCase):
    def test_a_reading_one_letter_off_split_over_two_lines_is_a_close_one(self) -> None:
        # Arrange
        read = ["Set the timing of the interrupt cycle made", "or fixed-period waveform mode."]

        # Act
        close = reading.close_reading(QUOTE, read)

        # Assert
        self.assertTrue(close)

    def test_a_reading_more_letters_off_than_a_recogniser_slips_is_not(self) -> None:
        # Arrange
        read = ["Set the tuning of the interrupt cycle made or fixed-period waveform mode."]

        # Act
        close = reading.close_reading(QUOTE, read)

        # Assert
        self.assertFalse(close)

    def test_a_reading_of_another_length_is_not_a_close_one(self) -> None:
        # Arrange
        read = ["Set the timing of the interrupt cycle mode."]

        # Act
        close = reading.close_reading(QUOTE, read)

        # Assert
        self.assertFalse(close)

    def test_a_reading_that_is_not_a_list_of_sentences_is_not_one(self) -> None:
        # Arrange
        read = [QUOTE, 2]

        # Act
        close = reading.close_reading(QUOTE, read)

        # Assert
        self.assertFalse(close)

    def test_an_empty_reading_of_an_empty_quote_is_not_one(self) -> None:
        # Arrange
        read: list[str] = []

        # Act
        close = reading.close_reading("", read)

        # Assert
        self.assertFalse(close)


if __name__ == "__main__":
    unittest.main()
