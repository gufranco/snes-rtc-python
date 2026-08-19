import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import reference

BUILT = Path(reference.DEFAULT_DRIVER)

HAS_DRIVER = BUILT.exists()

HAS_COMPILER = shutil.which("g++") is not None


class ScriptTest(unittest.TestCase):
    def test_a_script_is_as_long_as_it_was_asked_to_be(self):
        self.assertEqual(len(reference.generate(seed=1, length=40)), 40)

    def test_the_same_seed_produces_the_same_script(self):
        self.assertEqual(
            reference.generate(seed=1, length=40), reference.generate(seed=1, length=40)
        )

    def test_a_different_seed_produces_a_different_one(self):
        self.assertNotEqual(
            reference.generate(seed=1, length=40), reference.generate(seed=2, length=40)
        )

    def test_a_script_reaches_both_chips(self):
        rendered = reference.render(reference.generate(seed=1, length=400))

        self.assertIn("10240", rendered)
        self.assertIn("18496", rendered)

    def test_a_script_starts_by_setting_the_clock_it_will_be_read_against(self):
        self.assertTrue(reference.render(reference.generate(seed=1, length=10)).startswith("time "))

    def test_a_script_ends_by_asking_for_the_stored_bytes(self):
        self.assertTrue(reference.render(reference.generate(seed=1, length=10)).endswith("dump\n"))


class ReplayTest(unittest.TestCase):
    def test_replaying_a_script_answers_one_line_per_read(self):
        script = [("r", 0x2800, 0), ("r", 0x2800, 0)]

        answered = reference.replay(script)

        self.assertEqual(len(answered), 2)

    def test_a_write_produces_no_line_of_its_own(self):
        self.assertEqual(reference.replay([("w", 0x2801, 0x0D)]), [])

    def test_the_last_line_is_the_stored_bytes(self):
        answered = reference.replay([("dump", 0, 0)])

        self.assertEqual(len(answered[-1]), 40)

    def test_setting_the_clock_moves_what_the_model_reads(self):
        script = [("time", 2_000_000_000, 0), ("r", 0x2800, 0), ("dump", 0, 0)]

        answered = reference.replay(script)

        self.assertNotEqual(answered[-1][32:], "00000000")

    def test_storing_a_byte_puts_it_where_it_was_asked(self):
        answered = reference.replay([("store", 3, 0x09), ("dump", 0, 0)])

        self.assertEqual(answered[-1][6:8], "09")

    def test_powering_the_chips_discards_what_they_held(self):
        script = [("store", 3, 0x09), ("power", 0, 0), ("dump", 0, 0)]

        answered = reference.replay(script)

        self.assertNotEqual(answered[-1][6:8], "09")

    def test_an_address_neither_chip_answers_produces_a_line_anyway(self):
        self.assertEqual(len(reference.replay([("r", 0x1234, 0)])), 1)


class OptionTest(unittest.TestCase):
    def test_the_defaults_are_enough(self):
        chosen = reference.options([])

        self.assertEqual(chosen.runs, reference.RUNS)

    def test_the_number_of_runs_can_be_set(self):
        self.assertEqual(reference.options(["--runs", "3"]).runs, 3)

    def test_so_can_the_length_of_each(self):
        self.assertEqual(reference.options(["--length", "50"]).length, 50)

    def test_and_the_driver_to_compare_against(self):
        self.assertEqual(reference.options(["--driver", "somewhere"]).driver, "somewhere")

    def test_an_option_with_no_value_is_refused(self):
        with self.assertRaises(reference.Usage):
            reference.options(["--runs"])

    def test_an_option_the_runner_does_not_know_is_refused(self):
        with self.assertRaises(reference.Usage):
            reference.options(["--nonsense"])


class ComparisonTest(unittest.TestCase):
    def test_two_identical_transcripts_report_nothing(self):
        self.assertEqual(reference.differences(["0F", "00"], ["0F", "00"]), [])

    def test_a_line_that_differs_is_named_with_its_number(self):
        found = reference.differences(["0F", "00"], ["0F", "01"])

        self.assertEqual(found, [(1, "00", "01")])

    def test_a_transcript_that_stops_early_is_reported_rather_than_ignored(self):
        found = reference.differences(["0F", "00"], ["0F"])

        self.assertEqual(found[0][0], 1)


@unittest.skipUnless(HAS_DRIVER and HAS_COMPILER, "the reference driver is not built")
class AgainstReferenceTest(unittest.TestCase):
    def test_the_model_agrees_with_the_reference_over_a_long_script(self):
        script = reference.generate(seed=7, length=4000)

        found = reference.differences(reference.ask(script, str(BUILT)), reference.replay(script))

        self.assertEqual(found, [])


class DriverFailureTest(unittest.TestCase):
    def test_a_driver_that_fails_is_reported_rather_than_read_as_agreement(self):
        with self.assertRaises(reference.Usage):
            reference.ask([("dump", 0, 0)], "/usr/bin/false")


@unittest.skipUnless(HAS_DRIVER, "the reference driver is not built")
class WholeRunTest(unittest.TestCase):
    def test_a_short_run_against_the_reference_agrees_and_says_so(self):
        self.assertEqual(reference.run(["--runs", "2", "--length", "200"]), 0)


class DisagreementTest(unittest.TestCase):
    def wrong_driver(self):
        where = Path(tempfile.mkdtemp()) / "wrong"
        where.write_text(
            "#!/bin/sh\nwhile read -r line; do\n  case $line in\n  r*|dump*) echo ZZ ;;\n  esac\ndone\n"
        )
        where.chmod(where.stat().st_mode | stat.S_IXUSR)
        return where

    def test_a_driver_that_answers_differently_makes_the_run_fail(self):
        self.assertEqual(
            reference.run(["--runs", "1", "--length", "60", "--driver", str(self.wrong_driver())]),
            1,
        )

    def test_and_a_run_of_them_stops_reporting_after_the_first_handful(self):
        self.assertEqual(
            reference.run(["--runs", "40", "--length", "60", "--driver", str(self.wrong_driver())]),
            1,
        )


class EntryTest(unittest.TestCase):
    def test_a_run_with_no_driver_present_says_so_rather_than_passing(self):
        self.assertEqual(reference.main(["--driver", "/nowhere/at/all"]), 2)

    def test_an_option_it_does_not_know_is_reported(self):
        self.assertEqual(reference.main(["--nonsense"]), 2)


if __name__ == "__main__":
    unittest.main()
