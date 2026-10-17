import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesrtc import Store

SIZE = 20


class ShapeTest(unittest.TestCase):
    def test_the_store_is_the_twenty_bytes_the_cartridge_keeps(self) -> None:
        # Arrange
        held = Store(seed=1)

        # Act
        size = len(held.bytes)

        # Assert
        self.assertEqual(size, SIZE)

    def test_every_byte_read_back_is_a_byte(self) -> None:
        # Arrange
        held = Store(seed=1)

        # Act
        widest = max(held.read(at) for at in range(SIZE))

        # Assert
        self.assertLessEqual(widest, 0xFF)

    def test_a_value_wider_than_a_byte_is_narrowed_on_the_way_in(self) -> None:
        # Arrange
        held = Store(seed=1)

        # Act
        held.write(0, 0x1FF)

        # Assert
        self.assertEqual(held.read(0), 0xFF)

    def test_an_index_past_the_end_wraps_rather_than_failing(self) -> None:
        # Arrange
        held = Store(seed=1)

        # Act
        held.write(SIZE, 0x07)

        # Assert
        self.assertEqual((held.read(0), held.read(SIZE)), (0x07, 0x07))


class UnclearedTest(unittest.TestCase):
    def test_a_fresh_store_is_not_simply_zero_everywhere(self) -> None:
        # Arrange
        seed = 1

        # Act
        held = Store(seed=seed)

        # Assert
        self.assertNotEqual(held.bytes, [0] * SIZE)

    def test_two_stores_seeded_differently_hold_different_rubbish(self) -> None:
        # Arrange
        first = Store(seed=1)

        # Act
        second = Store(seed=2)

        # Assert
        self.assertNotEqual(first.bytes, second.bytes)

    def test_the_same_seed_holds_the_same_rubbish_twice(self) -> None:
        # Arrange
        first = Store(seed=1)

        # Act
        second = Store(seed=1)

        # Assert
        self.assertEqual(first.bytes, second.bytes)

    def test_a_store_can_be_asked_to_start_cleared_when_a_caller_means_it(self) -> None:
        # Arrange
        cleared = True

        # Act
        held = Store(cleared=cleared)

        # Assert
        self.assertEqual(held.bytes, [0] * SIZE)

    def test_a_store_can_be_handed_the_bytes_a_saved_cartridge_held(self) -> None:
        # Arrange
        saved = [0x01] * SIZE

        # Act
        held = Store(held=saved)

        # Assert
        self.assertEqual(held.read(5), 0x01)

    def test_bytes_short_of_the_full_store_are_taken_as_far_as_they_go(self) -> None:
        # Arrange
        saved = [0x09, 0x08]

        # Act
        held = Store(held=saved, cleared=True)

        # Assert
        self.assertEqual((held.read(0), held.read(1), held.read(2)), (0x09, 0x08, 0x00))


class StampTest(unittest.TestCase):
    def test_the_timestamp_is_kept_in_the_last_four_bytes_low_first(self) -> None:
        # Arrange
        held = Store(cleared=True)

        # Act
        held.stamp = 0x12345678

        # Assert
        self.assertEqual([held.read(at) for at in range(16, 20)], [0x78, 0x56, 0x34, 0x12])

    def test_and_reads_back_as_the_number_it_was(self) -> None:
        # Arrange
        held = Store(cleared=True)

        # Act
        held.stamp = 0x12345678

        # Assert
        self.assertEqual(held.stamp, 0x12345678)

    def test_a_stamp_wider_than_four_bytes_keeps_only_what_fits(self) -> None:
        # Arrange
        held = Store(cleared=True)

        # Act
        held.stamp = 0x1FFFFFFFF

        # Assert
        self.assertEqual(held.stamp, 0xFFFFFFFF)


class ReadingTest(unittest.TestCase):
    def test_a_store_prints_as_the_bytes_a_person_would_want_to_see(self) -> None:
        # Arrange
        held = Store(cleared=True, held=[0xAB])

        # Act
        shown = repr(held)

        # Assert
        self.assertIn("AB 00", shown)


if __name__ == "__main__":
    unittest.main()
