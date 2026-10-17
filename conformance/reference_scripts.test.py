import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance import reference


class ScriptTest(unittest.TestCase):
    def test_a_script_is_as_long_as_it_was_asked_to_be(self) -> None:
        # Arrange
        expected = 40

        # Act
        found = len(reference.generate(seed=1, length=40))

        # Assert
        self.assertEqual(found, expected)

    def test_the_same_seed_produces_the_same_script(self) -> None:
        # Arrange
        first = reference.generate(seed=1, length=40)

        # Act
        second = reference.generate(seed=1, length=40)

        # Assert
        self.assertEqual(first, second)

    def test_a_different_seed_produces_a_different_one(self) -> None:
        # Arrange
        first = reference.generate(seed=1, length=40)

        # Act
        second = reference.generate(seed=2, length=40)

        # Assert
        self.assertNotEqual(first, second)

    def test_a_script_for_one_part_stays_off_the_other_part_addresses(self) -> None:
        # Arrange
        script = reference.generate(seed=1, length=400, part="sharp")

        # Act
        touched = {first for verb, first, _ in script if verb in ("r", "w")}

        # Assert
        self.assertEqual(touched & set(reference.EPSON_ADDRESSES), set())

    def test_and_the_other_way_round(self) -> None:
        # Arrange
        script = reference.generate(seed=1, length=400, part="epson")

        # Act
        touched = {first for verb, first, _ in script if verb in ("r", "w")}

        # Assert
        self.assertEqual(touched & set(reference.SHARP_ADDRESSES), set())

    def test_an_unnamed_part_reaches_both_chips(self) -> None:
        # Arrange
        script = reference.generate(seed=1, length=400)

        # Act
        rendered = reference.render(script)

        # Assert
        self.assertIn("10240", rendered)
        self.assertIn("18496", rendered)

    def test_a_script_starts_by_setting_the_clock_it_will_be_read_against(self) -> None:
        # Arrange
        given = "time "

        # Act
        found = reference.render(reference.generate(seed=1, length=10)).startswith(given)

        # Assert
        self.assertTrue(found)

    def test_and_then_configures_the_chip_the_way_the_manual_does(self) -> None:
        # Arrange
        expected = reference.CONFIGURE

        # Act
        script = reference.generate(seed=1, length=10)

        # Assert
        self.assertEqual(tuple(script[1:3]), expected)

    def test_a_script_ends_by_asking_for_the_stored_bytes(self) -> None:
        # Arrange
        given = "dump\n"

        # Act
        found = reference.render(reference.generate(seed=1, length=10)).endswith(given)

        # Assert
        self.assertTrue(found)

    def test_every_power_is_followed_by_the_same_configuration(self) -> None:
        # Arrange
        script = reference.generate(seed=5, length=4000)

        # Act
        after = [tuple(script[at + 1 : at + 3]) for at, op in enumerate(script) if op[0] == "power"]

        # Assert
        self.assertTrue(all(step == reference.CONFIGURE for step in after))


class PartTest(unittest.TestCase):
    def test_a_part_with_no_cap_takes_the_length_it_is_asked_for(self) -> None:
        # Arrange
        expected = 4000

        # Act
        found = reference.PARTS["sharp"].length(4000)

        # Assert
        self.assertEqual(found, expected)

    def test_a_capped_part_takes_the_cap_instead(self) -> None:
        # Arrange
        expected = 200

        # Act
        found = reference.PARTS["epson"].length(4000)

        # Assert
        self.assertEqual(found, expected)

    def test_and_a_shorter_request_still_wins(self) -> None:
        # Arrange
        expected = 50

        # Act
        found = reference.PARTS["epson"].length(50)

        # Assert
        self.assertEqual(found, expected)

    def test_the_epson_cap_is_well_clear_of_the_prefix_it_has_to_hold(self) -> None:
        # Arrange
        scripts = [reference.generate(seed, 200, "epson") for seed in range(30)]

        # Act
        settled = [reference.observe(script).settled for script in scripts]

        # Assert
        self.assertLess(max(settled), reference.PARTS["epson"].length(200))


class ReplayTest(unittest.TestCase):
    def test_replaying_a_script_answers_one_line_per_read(self) -> None:
        # Arrange
        script = [("r", 0x2800, 0), ("r", 0x2800, 0)]

        # Act
        answered = reference.replay(script)

        # Assert
        self.assertEqual(len(answered), 2)

    def test_a_write_produces_no_line_of_its_own(self) -> None:
        # Arrange
        given = [("w", 10241, 13)]

        # Act
        found = reference.replay(given)

        # Assert
        self.assertEqual(found, [])

    def test_the_last_line_is_the_stored_bytes(self) -> None:
        # Arrange
        expected = 40

        # Act
        answered = reference.replay([("dump", 0, 0)])

        # Assert
        self.assertEqual(len(answered[-1]), expected)

    def test_setting_the_clock_moves_what_the_model_reads(self) -> None:
        # Arrange
        script = [("time", 2_000_000_000, 0), ("r", 0x2800, 0), ("dump", 0, 0)]

        # Act
        answered = reference.replay(script)

        # Assert
        self.assertNotEqual(answered[-1][32:], "00000000")

    def test_storing_a_byte_puts_it_where_it_was_asked(self) -> None:
        # Arrange
        expected = "09"

        # Act
        answered = reference.replay([("store", 3, 9), ("dump", 0, 0)])

        # Assert
        self.assertEqual(answered[-1][6:8], expected)

    def test_powering_the_chips_discards_what_they_held(self) -> None:
        # Arrange
        script = [("store", 3, 0x09), ("power", 0, 0), ("dump", 0, 0)]

        # Act
        answered = reference.replay(script)

        # Assert
        self.assertNotEqual(answered[-1][6:8], "09")

    def test_an_address_neither_chip_answers_produces_a_line_anyway(self) -> None:
        # Arrange
        expected = 1

        # Act
        found = len(reference.replay([("r", 4660, 0)]))

        # Assert
        self.assertEqual(found, expected)


class GeneratorEdgeTest(unittest.TestCase):
    def test_a_power_is_left_out_when_its_configuration_would_not_fit(self) -> None:
        # Arrange
        expected: list[str] = []

        # Act
        lengths = [
            length
            for length in range(6, 200)
            if not any(op[0] == "power" for op in reference.generate(3, length))
        ]

        # Assert
        self.assertNotEqual(lengths, expected)


if __name__ == "__main__":
    unittest.main()
