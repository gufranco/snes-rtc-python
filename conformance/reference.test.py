import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import reference

from snesrtc import epson, store

BUILT = Path(reference.DEFAULT_DRIVER)

HAS_DRIVER = BUILT.exists()

HAS_COMPILER = shutil.which("g++") is not None


class ScriptTest(unittest.TestCase):
    def test_a_script_is_as_long_as_it_was_asked_to_be(self) -> None:
        self.assertEqual(len(reference.generate(seed=1, length=40)), 40)

    def test_the_same_seed_produces_the_same_script(self) -> None:
        self.assertEqual(
            reference.generate(seed=1, length=40), reference.generate(seed=1, length=40)
        )

    def test_a_different_seed_produces_a_different_one(self) -> None:
        self.assertNotEqual(
            reference.generate(seed=1, length=40), reference.generate(seed=2, length=40)
        )

    def test_a_script_for_one_part_stays_off_the_other_part_addresses(self) -> None:
        script = reference.generate(seed=1, length=400, part="sharp")

        touched = {first for verb, first, _ in script if verb in ("r", "w")}

        self.assertEqual(touched & set(reference.EPSON_ADDRESSES), set())

    def test_and_the_other_way_round(self) -> None:
        script = reference.generate(seed=1, length=400, part="epson")

        touched = {first for verb, first, _ in script if verb in ("r", "w")}

        self.assertEqual(touched & set(reference.SHARP_ADDRESSES), set())

    def test_an_unnamed_part_reaches_both_chips(self) -> None:
        rendered = reference.render(reference.generate(seed=1, length=400))

        self.assertIn("10240", rendered)
        self.assertIn("18496", rendered)

    def test_a_script_starts_by_setting_the_clock_it_will_be_read_against(self) -> None:
        self.assertTrue(reference.render(reference.generate(seed=1, length=10)).startswith("time "))

    def test_and_then_configures_the_chip_the_way_the_manual_does(self) -> None:
        script = reference.generate(seed=1, length=10)

        self.assertEqual(tuple(script[1:3]), reference.CONFIGURE)

    def test_a_script_ends_by_asking_for_the_stored_bytes(self) -> None:
        self.assertTrue(reference.render(reference.generate(seed=1, length=10)).endswith("dump\n"))

    def test_every_power_is_followed_by_the_same_configuration(self) -> None:
        script = reference.generate(seed=5, length=4000)

        after = [tuple(script[at + 1 : at + 3]) for at, op in enumerate(script) if op[0] == "power"]

        self.assertTrue(all(step == reference.CONFIGURE for step in after))


class PartTest(unittest.TestCase):
    def test_a_part_with_no_cap_takes_the_length_it_is_asked_for(self) -> None:
        self.assertEqual(reference.PARTS["sharp"].length(4000), 4000)

    def test_a_capped_part_takes_the_cap_instead(self) -> None:
        self.assertEqual(reference.PARTS["epson"].length(4000), 200)

    def test_and_a_shorter_request_still_wins(self) -> None:
        self.assertEqual(reference.PARTS["epson"].length(50), 50)

    def test_the_epson_cap_is_well_clear_of_the_prefix_it_has_to_hold(self) -> None:
        settled = [
            reference.observe(reference.generate(seed, 200, "epson")).settled for seed in range(30)
        ]

        self.assertLess(max(settled), reference.PARTS["epson"].length(200))


class ReplayTest(unittest.TestCase):
    def test_replaying_a_script_answers_one_line_per_read(self) -> None:
        script = [("r", 0x2800, 0), ("r", 0x2800, 0)]

        answered = reference.replay(script)

        self.assertEqual(len(answered), 2)

    def test_a_write_produces_no_line_of_its_own(self) -> None:
        self.assertEqual(reference.replay([("w", 0x2801, 0x0D)]), [])

    def test_the_last_line_is_the_stored_bytes(self) -> None:
        answered = reference.replay([("dump", 0, 0)])

        self.assertEqual(len(answered[-1]), 40)

    def test_setting_the_clock_moves_what_the_model_reads(self) -> None:
        script = [("time", 2_000_000_000, 0), ("r", 0x2800, 0), ("dump", 0, 0)]

        answered = reference.replay(script)

        self.assertNotEqual(answered[-1][32:], "00000000")

    def test_storing_a_byte_puts_it_where_it_was_asked(self) -> None:
        answered = reference.replay([("store", 3, 0x09), ("dump", 0, 0)])

        self.assertEqual(answered[-1][6:8], "09")

    def test_powering_the_chips_discards_what_they_held(self) -> None:
        script = [("store", 3, 0x09), ("power", 0, 0), ("dump", 0, 0)]

        answered = reference.replay(script)

        self.assertNotEqual(answered[-1][6:8], "09")

    def test_an_address_neither_chip_answers_produces_a_line_anyway(self) -> None:
        self.assertEqual(len(reference.replay([("r", 0x1234, 0)])), 1)


class WitnessTest(unittest.TestCase):
    """What the runner refuses to compare, and why it refuses each one.

    Every id these produce has to appear in divergences.json, which the runner
    checks on every script rather than trusting.
    """

    def settled(self, script: list[reference.Operation]) -> reference.Replay:
        return reference.observe([("time", reference.START, 0), *reference.CONFIGURE, *script])

    def test_a_configured_script_that_touches_nothing_declared_is_compared_whole(self) -> None:
        replayed = self.settled([("r", epson.DATA, 0), ("dump", 0, 0)])

        self.assertEqual(replayed.reached, set())

    def test_and_is_compared_to_its_end(self) -> None:
        replayed = self.settled([("r", epson.DATA, 0), ("dump", 0, 0)])

        self.assertIsNone(replayed.limit)

    def test_a_flag_bit_in_a_narrow_register_stops_the_comparison_at_the_catch_up(
        self,
    ) -> None:
        replayed = self.settled(
            [
                ("store", epson.MO10, 0x8),
                ("dump", 0, 0),
                ("w", epson.ENABLE, 0x00),
                ("dump", 0, 0),
            ]
        )

        self.assertEqual(replayed.settled, 1)

    def test_but_not_before_it(self) -> None:
        replayed = self.settled([("store", epson.MO10, 0x8), ("dump", 0, 0)])

        self.assertEqual(replayed.reached, set())

    def test_writing_the_interrupt_flag_is_refused(self) -> None:
        replayed = self.settled(
            [
                ("w", epson.ENABLE, 0x01),
                ("w", epson.DATA, epson.WRITE_MODE),
                ("w", epson.DATA, epson.CD),
                ("w", epson.DATA, epson.IRQ_F),
            ]
        )

        self.assertIn("epson-irqf-not-writable", replayed.reached)

    def test_so_is_the_range_bit(self) -> None:
        replayed = self.settled(
            [
                ("w", epson.ENABLE, 0x01),
                ("w", epson.DATA, epson.WRITE_MODE),
                ("w", epson.DATA, epson.CD),
                ("w", epson.DATA, epson.CAL_HW),
            ]
        )

        self.assertIn("epson-cd-bit1-add-second", replayed.reached)

    def test_and_a_write_while_the_chip_is_in_read_mode(self) -> None:
        replayed = self.settled(
            [
                ("w", epson.ENABLE, 0x01),
                ("w", epson.DATA, epson.READ_MODE),
                ("w", epson.DATA, 0x00),
                ("w", epson.DATA, 0x00),
            ]
        )

        self.assertIn("epson-writes-during-read-mode", replayed.reached)

    def test_closing_a_chip_that_holds_the_test_bit_is_refused(self) -> None:
        replayed = self.settled(
            [("store", epson.CF, reference.CONFIGURED_CF | epson.TEST), ("w", epson.ENABLE, 0x00)]
        )

        self.assertIn("epson-test-bit-not-cleared", replayed.reached)

    def test_every_id_the_runner_can_witness_is_written_down(self) -> None:
        known = reference.declared()

        reached = set()
        for seed in range(12):
            reached |= reference.observe(reference.generate(seed, 400, "epson")).reached

        self.assertEqual(reached - known, set())

    def test_the_sharp_part_has_nothing_the_manufacturer_settles_differently(self) -> None:
        reached = set()
        for seed in range(12):
            reached |= reference.observe(reference.generate(seed, 400, "sharp")).reached

        self.assertEqual(reached, set())


class StampWidthTest(unittest.TestCase):
    """The one exclusion that is about the recorder rather than about a part.

    The recording builds its stamp from the four bytes the cartridge holds and
    then tests for underflow against the maximum of the host's time_t, so a
    64-bit build and a 32-bit build of it disagree about every interval past half
    the stamp's range. An answer that turns on the width of a type is a property
    of the build machine, and is excluded rather than allowed to decide.
    """

    def test_a_moment_past_half_the_stamp_range_is_refused(self) -> None:
        cartridge = reference.Cartridge()

        found = reference.witness(cartridge, ("time", reference.STAMP_AMBIGUOUS, 0))

        self.assertIn("stamp-width-platform-dependent", found)

    def test_and_so_is_every_operation_after_it(self) -> None:
        cartridge = reference.Cartridge()
        cartridge.at = reference.STAMP_AMBIGUOUS

        found = reference.witness(cartridge, ("r", 0x2800, 0))

        self.assertIn("stamp-width-platform-dependent", found)

    def test_a_moment_below_it_is_compared_as_usual(self) -> None:
        cartridge = reference.Cartridge()

        found = reference.witness(cartridge, ("time", reference.STAMP_AMBIGUOUS - 1, 0))

        self.assertEqual(found, set())

    def test_the_threshold_is_half_the_range_four_bytes_hold(self) -> None:
        self.assertEqual(reference.STAMP_AMBIGUOUS * 2, 0x1_0000_0000)


class CatchUpTest(unittest.TestCase):
    """Which operations make the model write the time back, judged from outside it."""

    def opened(self, index: int, mode: int = epson.WRITE_MODE) -> reference.Cartridge:
        cartridge = reference.Cartridge()
        cartridge.store.write(epson.CF, reference.CONFIGURED_CF)
        cartridge.store.write(epson.CD, reference.CONFIGURED_CD)
        cartridge.write(epson.ENABLE, 0x01)
        cartridge.write(epson.DATA, mode)
        cartridge.write(epson.DATA, index)
        return cartridge

    def test_closing_the_chip_writes_the_time_back(self) -> None:
        cartridge = reference.Cartridge()

        self.assertTrue(reference._catches_up(cartridge, ("w", epson.ENABLE, 0x00)))

    def test_a_write_to_control_register_f_writes_it_back(self) -> None:
        cartridge = self.opened(epson.CF)

        self.assertTrue(reference._catches_up(cartridge, ("w", epson.DATA, 0x00)))

    def test_a_write_to_a_clock_register_does_not(self) -> None:
        cartridge = self.opened(epson.S1)

        self.assertFalse(reference._catches_up(cartridge, ("w", epson.DATA, 0x01)))

    def test_an_adjustment_does(self) -> None:
        cartridge = self.opened(epson.CD)

        self.assertTrue(reference._catches_up(cartridge, ("w", epson.DATA, epson.ADJUST)))

    def test_a_control_register_d_write_that_changes_nothing_does_not(self) -> None:
        cartridge = self.opened(epson.CD)

        self.assertFalse(
            reference._catches_up(cartridge, ("w", epson.DATA, reference.CONFIGURED_CD))
        )

    def test_a_read_never_does(self) -> None:
        cartridge = self.opened(epson.CF)

        self.assertFalse(reference._catches_up(cartridge, ("r", epson.DATA, 0)))


class AdvanceTest(unittest.TestCase):
    def test_a_running_clock_with_time_behind_it_advances(self) -> None:
        cartridge = reference.Cartridge()
        cartridge.store.write(epson.CF, reference.CONFIGURED_CF)
        cartridge.at = reference.START + 5

        self.assertTrue(reference._would_advance(cartridge))

    def test_a_stopped_one_does_not(self) -> None:
        cartridge = reference.Cartridge()
        cartridge.store.write(epson.CF, reference.CONFIGURED_CF | epson.STOP)
        cartridge.at = reference.START + 5

        self.assertFalse(reference._would_advance(cartridge))

    def test_nor_does_a_held_one(self) -> None:
        cartridge = reference.Cartridge()
        cartridge.store.write(epson.CF, reference.CONFIGURED_CF)
        cartridge.store.write(epson.CD, reference.CONFIGURED_CD | epson.HOLD)
        cartridge.at = reference.START + 5

        self.assertFalse(reference._would_advance(cartridge))


class RegisterWitnessTest(unittest.TestCase):
    def held(self) -> store.Store:
        held = store.Store(cleared=True)
        held.write(epson.CD, reference.CONFIGURED_CD)
        return held

    def test_a_clock_register_write_reaches_nothing_on_its_own(self) -> None:
        self.assertEqual(reference._witness_register(self.held(), epson.MO10, 0xF), set())

    def test_the_interrupt_flag_is_named(self) -> None:
        found = reference._witness_register(self.held(), epson.CD, epson.IRQ_F)

        self.assertEqual(found, {"epson-irqf-not-writable"})

    def test_the_adjustment_bit_is_named(self) -> None:
        found = reference._witness_register(self.held(), epson.CD, epson.ADJUST)

        self.assertIn("epson-thirty-second-adjust-lockout-unmodelled", found)

    def test_the_range_bit_is_named(self) -> None:
        found = reference._witness_register(self.held(), epson.CD, epson.CAL_HW)

        self.assertIn("epson-cd-bit1-add-second", found)

    def test_a_change_to_the_hold_bit_is_named(self) -> None:
        found = reference._witness_register(self.held(), epson.CD, epson.HOLD)

        self.assertIn("epson-hold-discards-elapsed-time", found)


class ReadWitnessTest(unittest.TestCase):
    def test_reading_control_register_d_with_the_interrupt_flag_set_is_refused(self) -> None:
        cartridge = reference.Cartridge()
        cartridge.store.write(epson.CD, reference.CONFIGURED_CD | epson.IRQ_F)
        cartridge.write(epson.ENABLE, 0x01)
        cartridge.write(epson.DATA, epson.READ_MODE)
        cartridge.write(epson.DATA, epson.CD)

        found = reference.witness(cartridge, ("r", epson.DATA, 0))

        self.assertIn("epson-irqf-not-writable", found)

    def test_a_catch_up_inside_an_open_session_raises_the_read_flag(self) -> None:
        cartridge = reference.Cartridge()
        cartridge.store.write(epson.CF, reference.CONFIGURED_CF)
        cartridge.store.write(epson.CD, reference.CONFIGURED_CD)
        cartridge.write(epson.ENABLE, 0x01)
        cartridge.write(epson.DATA, epson.WRITE_MODE)
        cartridge.write(epson.DATA, epson.CF)
        cartridge.at = reference.START + 5

        found = reference.witness(cartridge, ("w", epson.DATA, reference.CONFIGURED_CF))

        self.assertIn("epson-read-and-write-flags-unmodelled", found)


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


class GeneratorEdgeTest(unittest.TestCase):
    def test_a_power_is_left_out_when_its_configuration_would_not_fit(self) -> None:
        lengths = [
            length
            for length in range(6, 200)
            if not any(op[0] == "power" for op in reference.generate(3, length))
        ]

        self.assertNotEqual(lengths, [])


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
