import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance import reference
from snesrtc import epson, store


class WitnessTest(unittest.TestCase):
    def settled(self, script: list[reference.Operation]) -> reference.Replay:
        return reference.observe([("time", reference.START, 0), *reference.CONFIGURE, *script])

    def test_a_configured_script_that_touches_nothing_declared_is_compared_whole(self) -> None:
        # Arrange
        given = [("r", epson.DATA, 0), ("dump", 0, 0)]

        # Act
        replayed = self.settled(given)

        # Assert
        self.assertEqual(replayed.reached, set())

    def test_and_is_compared_to_its_end(self) -> None:
        # Arrange
        given = [("r", epson.DATA, 0), ("dump", 0, 0)]

        # Act
        replayed = self.settled(given)

        # Assert
        self.assertIsNone(replayed.limit)

    def test_a_flag_bit_in_a_narrow_register_stops_the_comparison_at_the_catch_up(
        self,
    ) -> None:
        # Arrange
        expected = 1

        # Act
        replayed = self.settled(
            [("store", epson.MO10, 8), ("dump", 0, 0), ("w", epson.ENABLE, 0), ("dump", 0, 0)]
        )

        # Assert
        self.assertEqual(replayed.settled, expected)

    def test_but_not_before_it(self) -> None:
        # Arrange
        given = [("store", epson.MO10, 8), ("dump", 0, 0)]

        # Act
        replayed = self.settled(given)

        # Assert
        self.assertEqual(replayed.reached, set())

    def test_writing_the_interrupt_flag_stops_nothing(self) -> None:
        # Arrange
        script = [
            ("w", epson.ENABLE, 0x01),
            ("w", epson.DATA, epson.WRITE_MODE),
            ("w", epson.DATA, epson.CD),
            ("w", epson.DATA, epson.IRQ_F),
        ]

        # Act
        replayed = self.settled(script)

        # Assert
        self.assertEqual(replayed.reached, set())

    def test_writing_the_range_bit_is_refused(self) -> None:
        # Arrange
        given = [
            ("w", epson.ENABLE, 1),
            ("w", epson.DATA, epson.WRITE_MODE),
            ("w", epson.DATA, epson.CD),
            ("w", epson.DATA, epson.CAL_HW),
        ]

        # Act
        replayed = self.settled(given)

        # Assert
        self.assertIn("epson-cd-bit1-add-second", replayed.reached)

    def test_and_a_write_while_the_chip_is_in_read_mode(self) -> None:
        # Arrange
        given = [
            ("w", epson.ENABLE, 1),
            ("w", epson.DATA, epson.READ_MODE),
            ("w", epson.DATA, 0),
            ("w", epson.DATA, 0),
        ]

        # Act
        replayed = self.settled(given)

        # Assert
        self.assertIn("epson-writes-during-read-mode", replayed.reached)

    def test_closing_a_chip_that_holds_the_test_bit_is_refused(self) -> None:
        # Arrange
        given = [("store", epson.CF, reference.CONFIGURED_CF | epson.TEST), ("w", epson.ENABLE, 0)]

        # Act
        replayed = self.settled(given)

        # Assert
        self.assertIn("epson-test-bit-not-cleared", replayed.reached)

    def test_every_id_the_runner_can_witness_is_written_down(self) -> None:
        # Arrange
        known = reference.declared()
        reached = set()

        # Act
        for seed in range(12):
            reached |= reference.observe(reference.generate(seed, 400, "epson")).reached

        # Assert
        self.assertEqual(reached - known, set())

    def test_the_sharp_part_has_nothing_the_manufacturer_settles_differently(self) -> None:
        # Arrange
        reached = set()

        # Act
        for seed in range(12):
            reached |= reference.observe(reference.generate(seed, 400, "sharp")).reached

        # Assert
        self.assertEqual(reached, set())


class StampWidthTest(unittest.TestCase):
    def test_a_moment_past_half_the_stamp_range_is_refused(self) -> None:
        # Arrange
        cartridge = reference.Cartridge()

        # Act
        found = reference.witness(cartridge, ("time", reference.STAMP_AMBIGUOUS, 0))

        # Assert
        self.assertIn("stamp-width-platform-dependent", found)

    def test_and_so_is_every_operation_after_it(self) -> None:
        # Arrange
        cartridge = reference.Cartridge()
        cartridge.at = reference.STAMP_AMBIGUOUS

        # Act
        found = reference.witness(cartridge, ("r", 10240, 0))

        # Assert
        self.assertIn("stamp-width-platform-dependent", found)

    def test_a_moment_below_it_is_compared_as_usual(self) -> None:
        # Arrange
        cartridge = reference.Cartridge()

        # Act
        found = reference.witness(cartridge, ("time", reference.STAMP_AMBIGUOUS - 1, 0))

        # Assert
        self.assertEqual(found, set())

    def test_the_threshold_is_half_the_range_four_bytes_hold(self) -> None:
        # Arrange
        expected = 4294967296

        # Act
        found = reference.STAMP_AMBIGUOUS * 2

        # Assert
        self.assertEqual(found, expected)


class CatchUpTest(unittest.TestCase):
    def opened(self, index: int, mode: int = epson.WRITE_MODE) -> reference.Cartridge:
        cartridge = reference.Cartridge()
        cartridge.store.write(epson.CF, reference.CONFIGURED_CF)
        cartridge.store.write(epson.CD, reference.CONFIGURED_CD)
        cartridge.write(epson.ENABLE, 0x01)
        cartridge.write(epson.DATA, mode)
        cartridge.write(epson.DATA, index)
        return cartridge

    def test_closing_the_chip_writes_the_time_back(self) -> None:
        # Arrange
        cartridge = reference.Cartridge()

        # Act
        caught_up = reference._catches_up(cartridge, ("w", epson.ENABLE, 0x00))

        # Assert
        self.assertTrue(caught_up)

    def test_a_write_to_control_register_f_writes_it_back(self) -> None:
        # Arrange
        given = epson.CF

        # Act
        cartridge = self.opened(given)

        # Assert
        self.assertTrue(reference._catches_up(cartridge, ("w", epson.DATA, 0)))

    def test_a_write_to_a_clock_register_does_not(self) -> None:
        # Arrange
        given = epson.S1

        # Act
        cartridge = self.opened(given)

        # Assert
        self.assertFalse(reference._catches_up(cartridge, ("w", epson.DATA, 1)))

    def test_an_adjustment_does(self) -> None:
        # Arrange
        given = epson.CD

        # Act
        cartridge = self.opened(given)

        # Assert
        self.assertTrue(reference._catches_up(cartridge, ("w", epson.DATA, epson.ADJUST)))

    def test_a_control_register_d_write_that_changes_nothing_does_not(self) -> None:
        # Arrange
        given = epson.CD

        # Act
        cartridge = self.opened(given)

        # Assert
        self.assertFalse(
            reference._catches_up(cartridge, ("w", epson.DATA, reference.CONFIGURED_CD))
        )

    def test_a_read_never_does(self) -> None:
        # Arrange
        given = epson.CF

        # Act
        cartridge = self.opened(given)

        # Assert
        self.assertFalse(reference._catches_up(cartridge, ("r", epson.DATA, 0)))


class AdvanceTest(unittest.TestCase):
    def test_a_running_clock_with_time_behind_it_advances(self) -> None:
        # Arrange
        cartridge = reference.Cartridge()
        cartridge.store.write(epson.CF, reference.CONFIGURED_CF)

        # Act
        cartridge.at = reference.START + 5

        # Assert
        self.assertTrue(reference._would_advance(cartridge))

    def test_a_stopped_one_does_not(self) -> None:
        # Arrange
        cartridge = reference.Cartridge()
        cartridge.store.write(epson.CF, reference.CONFIGURED_CF | epson.STOP)

        # Act
        cartridge.at = reference.START + 5

        # Assert
        self.assertFalse(reference._would_advance(cartridge))

    def test_nor_does_a_held_one(self) -> None:
        # Arrange
        cartridge = reference.Cartridge()
        cartridge.store.write(epson.CF, reference.CONFIGURED_CF)
        cartridge.store.write(epson.CD, reference.CONFIGURED_CD | epson.HOLD)

        # Act
        cartridge.at = reference.START + 5

        # Assert
        self.assertFalse(reference._would_advance(cartridge))


class RegisterWitnessTest(unittest.TestCase):
    def held(self) -> store.Store:
        held = store.Store(cleared=True)
        held.write(epson.CD, reference.CONFIGURED_CD)
        return held

    def test_a_clock_register_write_reaches_nothing_on_its_own(self) -> None:
        # Arrange
        expected: set[str] = set()

        # Act
        found = reference._witness_register(self.held(), epson.MO10, 15)

        # Assert
        self.assertEqual(found, expected)

    def test_writing_the_interrupt_flag_is_left_to_the_excusal(self) -> None:
        # Arrange
        held = self.held()

        # Act
        found = reference._witness_register(held, epson.CD, epson.IRQ_F)

        # Assert
        self.assertEqual(found, set())

    def test_and_so_is_a_tens_of_hours_write_carrying_a_fixed_bit(self) -> None:
        # Arrange
        held = self.held()

        # Act
        found = reference._witness_register(held, epson.H10, epson.H20 | epson.PM | 1)

        # Assert
        self.assertEqual(found, set())

    def test_the_adjustment_bit_is_named(self) -> None:
        # Arrange
        held = self.held()

        # Act
        found = reference._witness_register(held, epson.CD, epson.ADJUST)

        # Assert
        self.assertIn("epson-thirty-second-adjust-lockout", found)

    def test_the_range_bit_is_named(self) -> None:
        # Arrange
        held = self.held()

        # Act
        found = reference._witness_register(held, epson.CD, epson.CAL_HW)

        # Assert
        self.assertIn("epson-cd-bit1-add-second", found)

    def test_a_change_to_the_hold_bit_is_named(self) -> None:
        # Arrange
        held = self.held()

        # Act
        found = reference._witness_register(held, epson.CD, epson.HOLD)

        # Assert
        self.assertIn("epson-hold-discards-elapsed-time", found)


class ReadWitnessTest(unittest.TestCase):
    def test_a_catch_up_inside_an_open_session_raises_the_read_flag(self) -> None:
        # Arrange
        cartridge = reference.Cartridge()
        cartridge.store.write(epson.CF, reference.CONFIGURED_CF)
        cartridge.store.write(epson.CD, reference.CONFIGURED_CD)
        cartridge.write(epson.ENABLE, 0x01)
        cartridge.write(epson.DATA, epson.WRITE_MODE)
        cartridge.write(epson.DATA, epson.CF)
        cartridge.at = reference.START + 5

        # Act
        found = reference.witness(cartridge, ("w", epson.DATA, reference.CONFIGURED_CF))

        # Assert
        self.assertIn("epson-oscillation-flag-cannot-be-originated", found)


class ExcusalTest(unittest.TestCase):
    def raised(self) -> reference.Replay:
        return reference.observe(
            [
                ("time", reference.START, 0),
                *reference.CONFIGURE,
                ("store", epson.CE, epson.INT_STND | 0x4),
                ("time", reference.START + 1, 0),
                ("w", epson.ENABLE, 0x00),
                ("w", epson.ENABLE, 0x01),
                ("w", epson.DATA, epson.READ_MODE),
                ("w", epson.DATA, epson.CD),
                ("r", epson.DATA, 0),
                ("dump", 0, 0),
            ]
        )

    def test_a_raised_interrupt_flag_stops_nothing(self) -> None:
        # Arrange
        script = self.raised

        # Act
        replayed = script()

        # Assert
        self.assertEqual((replayed.reached, replayed.limit), (set(), None))

    def test_the_read_of_cd_is_compared_except_for_that_flag(self) -> None:
        # Arrange
        replayed = self.raised()
        theirs = [f"{int(replayed.transcript[0], 16) & ~epson.IRQ_F:02X}", replayed.transcript[1]]

        # Act
        found, partly = reference.explain(theirs, replayed.transcript, None, replayed.excused)

        # Assert
        self.assertEqual((found, partly), ([], {0: {"epson-irqf-not-writable"}}))

    def test_and_any_other_bit_of_it_still_has_to_agree(self) -> None:
        # Arrange
        replayed = self.raised()
        theirs = [f"{int(replayed.transcript[0], 16) ^ epson.CAL_HW:02X}", replayed.transcript[1]]

        # Act
        found, _ = reference.explain(theirs, replayed.transcript, None, replayed.excused)

        # Assert
        self.assertEqual([index for index, _, _ in found], [0])

    def test_a_held_back_afternoon_bit_stops_the_comparison_at_the_next_catch_up(self) -> None:
        # Arrange
        script = [
            ("time", reference.START, 0),
            *reference.CONFIGURE,
            ("w", epson.ENABLE, 0x01),
            ("w", epson.DATA, epson.WRITE_MODE),
            ("w", epson.DATA, epson.H10),
            ("w", epson.DATA, epson.PM | 0x1),
            ("dump", 0, 0),
            ("w", epson.ENABLE, 0x00),
            ("dump", 0, 0),
        ]

        # Act
        replayed = reference.observe(script)

        # Assert
        self.assertEqual(
            (replayed.reached, replayed.settled),
            ({"epson-digit-fields-narrower-than-registers"}, 1),
        )


if __name__ == "__main__":
    unittest.main()
