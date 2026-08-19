import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesrtc import store


class ShapeTest(unittest.TestCase):
    def test_the_store_is_the_twenty_bytes_the_cartridge_keeps(self):
        self.assertEqual(len(store.Store(seed=1).bytes), store.SIZE)

    def test_every_byte_read_back_is_a_byte(self):
        held = store.Store(seed=1)

        for at in range(store.SIZE):
            self.assertLessEqual(held.read(at), 0xFF)

    def test_a_value_wider_than_a_byte_is_narrowed_on_the_way_in(self):
        held = store.Store(seed=1)

        held.write(0, 0x1FF)

        self.assertEqual(held.read(0), 0xFF)

    def test_an_index_past_the_end_wraps_rather_than_failing(self):
        held = store.Store(seed=1)

        held.write(store.SIZE, 0x07)

        self.assertEqual(held.read(0), 0x07)


class UnclearedTest(unittest.TestCase):
    def test_a_fresh_store_is_not_simply_zero_everywhere(self):
        self.assertTrue(any(store.Store(seed=1).bytes))

    def test_two_stores_seeded_differently_hold_different_rubbish(self):
        self.assertNotEqual(store.Store(seed=1).bytes, store.Store(seed=2).bytes)

    def test_the_same_seed_holds_the_same_rubbish_twice(self):
        self.assertEqual(store.Store(seed=1).bytes, store.Store(seed=1).bytes)

    def test_a_store_can_be_asked_to_start_cleared_when_a_caller_means_it(self):
        self.assertEqual(store.Store(cleared=True).bytes, [0] * store.SIZE)

    def test_a_store_can_be_handed_the_bytes_a_saved_cartridge_held(self):
        held = store.Store(held=[0x01] * store.SIZE)

        self.assertEqual(held.read(5), 0x01)

    def test_bytes_short_of_the_full_store_are_taken_as_far_as_they_go(self):
        held = store.Store(held=[0x09, 0x08], cleared=True)

        self.assertEqual((held.read(0), held.read(1), held.read(2)), (0x09, 0x08, 0x00))


class StampTest(unittest.TestCase):
    def test_the_timestamp_is_kept_in_the_last_four_bytes_low_first(self):
        held = store.Store(cleared=True)

        held.stamp = 0x12345678

        self.assertEqual([held.read(at) for at in range(16, 20)], [0x78, 0x56, 0x34, 0x12])

    def test_and_reads_back_as_the_number_it_was(self):
        held = store.Store(cleared=True)

        held.stamp = 0x12345678

        self.assertEqual(held.stamp, 0x12345678)

    def test_a_stamp_wider_than_four_bytes_keeps_only_what_fits(self):
        held = store.Store(cleared=True)

        held.stamp = 0x1FFFFFFFF

        self.assertEqual(held.stamp, 0xFFFFFFFF)


class ReadingTest(unittest.TestCase):
    def test_a_store_prints_as_the_bytes_a_person_would_want_to_see(self):
        held = store.Store(cleared=True)

        self.assertIn("00", repr(held))


if __name__ == "__main__":
    unittest.main()
