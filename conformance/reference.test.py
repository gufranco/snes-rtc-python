import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance import reference

BUILT = Path(reference.DEFAULT_DRIVER)

HAS_DRIVER = BUILT.exists()

HAS_COMPILER = shutil.which("g++") is not None


class UndeclaredTest(unittest.TestCase):
    def test_a_divergence_nobody_wrote_down_fails_the_run_rather_than_being_excused(
        self,
    ) -> None:
        chosen = reference.Options(length=200, driver="/nowhere", seed=1)

        tally = reference.sweep("epson", chosen, set())

        self.assertEqual(tally.failed, 1)

    def test_and_the_operations_after_it_are_still_counted_apart(self) -> None:
        chosen = reference.Options(length=200, driver="/nowhere", seed=1)

        tally = reference.sweep("epson", chosen, set())

        self.assertGreater(tally.excluded, 0)


class DeclarationTest(unittest.TestCase):
    def test_the_divergence_file_names_every_entry(self) -> None:
        self.assertIn("epson-hold-discards-elapsed-time", reference.declared())

    def test_and_the_sharp_part_is_declared_undocumented(self) -> None:
        self.assertIn("sharp-part-undocumented", reference.declared())


class OptionTest(unittest.TestCase):
    def test_the_defaults_are_enough(self) -> None:
        chosen = reference.options([])

        self.assertEqual(chosen.runs, reference.RUNS)

    def test_the_number_of_runs_can_be_set(self) -> None:
        self.assertEqual(reference.options(["--runs", "3"]).runs, 3)

    def test_so_can_the_length_of_each(self) -> None:
        self.assertEqual(reference.options(["--length", "50"]).length, 50)

    def test_and_the_driver_to_compare_against(self) -> None:
        self.assertEqual(reference.options(["--driver", "somewhere"]).driver, "somewhere")

    def test_and_one_seed_on_its_own_for_reproducing_a_failure(self) -> None:
        self.assertEqual(list(reference.options(["--seed", "22"]).seeds()), [22])

    def test_without_one_every_seed_up_to_the_count_runs(self) -> None:
        self.assertEqual(list(reference.options(["--runs", "3"]).seeds()), [0, 1, 2])

    def test_and_the_run_can_start_somewhere_other_than_zero(self) -> None:
        chosen = reference.options(["--runs", "3", "--from", "500"])

        self.assertEqual(list(chosen.seeds()), [500, 501, 502])

    def test_a_named_seed_still_wins_over_a_start(self) -> None:
        chosen = reference.options(["--from", "500", "--seed", "7"])

        self.assertEqual(list(chosen.seeds()), [7])

    def test_an_option_with_no_value_is_refused(self) -> None:
        with self.assertRaises(reference.Usage):
            reference.options(["--runs"])

    def test_an_option_the_runner_does_not_know_is_refused(self) -> None:
        with self.assertRaises(reference.Usage):
            reference.options(["--nonsense"])


class ComparisonTest(unittest.TestCase):
    def test_two_identical_transcripts_report_nothing(self) -> None:
        self.assertEqual(reference.differences(["0F", "00"], ["0F", "00"]), [])

    def test_a_line_that_differs_is_named_with_its_number(self) -> None:
        found = reference.differences(["0F", "00"], ["0F", "01"])

        self.assertEqual(found, [(1, "00", "01")])

    def test_a_transcript_that_stops_early_is_reported_rather_than_ignored(self) -> None:
        found = reference.differences(["0F", "00"], ["0F"])

        self.assertEqual(found[0][0], 1)

    def test_a_limit_stops_the_comparison_where_it_stops_being_settled(self) -> None:
        self.assertEqual(reference.differences(["0F", "00"], ["0F", "01"], 1), [])

    def test_a_line_missing_from_the_reference_is_reported(self) -> None:
        # Arrange
        expected = ["0F"]

        # Act
        found, _ = reference.explain(expected, ["0F", "00"])

        # Assert
        self.assertEqual(found, [(1, None, "00")])


class TallyTest(unittest.TestCase):
    def test_a_tally_with_nothing_refused_says_only_what_it_compared(self) -> None:
        tally = reference.Tally("epson")
        tally.add(reference.Replay(["00"], 1, set()), 1)

        self.assertEqual(len(list(tally.report())), 1)

    def test_and_one_with_something_refused_names_it(self) -> None:
        tally = reference.Tally("epson")
        tally.add(reference.Replay(["00", "01"], 1, {"epson-irqf-not-writable"}), 2)

        self.assertIn("epson-irqf-not-writable", list(tally.report())[1])

    def test_the_operations_not_compared_are_counted_rather_than_dropped(self) -> None:
        tally = reference.Tally("epson")
        tally.add(reference.Replay(["00", "01", "02"], 1, {"epson-irqf-not-writable"}), 3)

        self.assertEqual((tally.compared, tally.excluded), (1, 2))

    def test_an_operation_compared_except_excused_fields_is_counted_apart(self) -> None:
        # Arrange
        tally = reference.Tally("epson")

        # Act
        tally.add(reference.Replay(["00", "04"], 2, set()), 2, {1: {"epson-irqf-not-writable"}})

        # Assert
        self.assertEqual((tally.compared, tally.partly, tally.excluded), (1, 1, 0))

    def test_and_the_report_names_what_was_excused(self) -> None:
        # Arrange
        tally = reference.Tally("epson")
        tally.add(reference.Replay(["00", "04"], 2, set()), 2, {1: {"epson-irqf-not-writable"}})

        # Act
        said = list(tally.report())

        # Assert
        self.assertEqual(said[1], "  fields excused under epson-irqf-not-writable on 1 operations")


@unittest.skipUnless(HAS_DRIVER and HAS_COMPILER, "the reference driver is not built")
class AgainstReferenceTest(unittest.TestCase):
    def test_the_sharp_model_agrees_with_the_recording_over_a_long_script(self) -> None:
        script = reference.generate(seed=7, length=4000, part="sharp")

        found = reference.differences(reference.ask(script, str(BUILT)), reference.replay(script))

        self.assertEqual(found, [])

    def test_the_epson_model_agrees_over_the_ground_the_recording_can_settle(self) -> None:
        script = reference.generate(seed=7, length=4000, part="epson")
        replayed = reference.observe(script)

        found = reference.differences(
            reference.ask(script, str(BUILT)), replayed.transcript, replayed.limit
        )

        self.assertEqual(found, [])


class DriverFailureTest(unittest.TestCase):
    def test_a_driver_that_fails_is_reported_rather_than_read_as_agreement(self) -> None:
        with self.assertRaises(reference.Usage):
            reference.ask([("dump", 0, 0)], "/usr/bin/false")


@unittest.skipUnless(HAS_DRIVER, "the reference driver is not built")
class WholeRunTest(unittest.TestCase):
    def test_a_short_run_against_the_reference_agrees_and_says_so(self) -> None:
        self.assertEqual(reference.run(["--runs", "2", "--length", "200"]), 0)


class DisagreementTest(unittest.TestCase):
    def wrong_driver(self) -> Path:
        where = Path(tempfile.mkdtemp()) / "wrong"
        where.write_text(
            "#!/bin/sh\nwhile read -r line; do\n  case $line in\n  r*|dump*) echo ZZ ;;\n  esac\ndone\n"
        )
        where.chmod(where.stat().st_mode | stat.S_IXUSR)
        return where

    def test_a_driver_that_answers_differently_makes_the_run_fail(self) -> None:
        self.assertEqual(
            reference.run(["--runs", "1", "--length", "60", "--driver", str(self.wrong_driver())]),
            1,
        )

    def test_and_a_run_of_them_stops_reporting_after_the_first_handful(self) -> None:
        self.assertEqual(
            reference.run(["--runs", "40", "--length", "60", "--driver", str(self.wrong_driver())]),
            1,
        )


class EntryTest(unittest.TestCase):
    def test_a_run_with_no_driver_present_says_so_rather_than_passing(self) -> None:
        self.assertEqual(reference.main(["--driver", "/nowhere/at/all"]), 2)

    def test_an_option_it_does_not_know_is_reported(self) -> None:
        self.assertEqual(reference.main(["--nonsense"]), 2)


if __name__ == "__main__":
    unittest.main()
