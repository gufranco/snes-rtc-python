import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conformance import cartridge
from conformance.driving import DATA, ENABLE, READ_MODE, STATUS, WRITE_MODE


def _writing(pairs: list[tuple[int, int]], where: int = 0x2D62) -> bytes:
    body = bytearray()
    for index, value in pairs:
        body += bytes((0xA2, index, 0x00))
        body += bytes((0xA9, value))
        body += bytes((0x22, where & 0xFF, where >> 8, 0xC0))
    body += bytes((0x6B,))
    return bytes(body)


def _fold(pivot: int = 95, carry: int = 5, base: int = 1900) -> bytes:
    held = bytes((0x85, 0x00, 0x38, 0xE9, pivot, 0xB0, 0x05, 0xA5, 0x00, 0x18, 0x69, carry))
    held += bytes((0x18, 0x69, pivot, 0x60))
    return held + bytes((0xC2, 0x20, 0x29, 0xFF, 0x00, 0x18, 0x69)) + base.to_bytes(2, "little")


def _session(mode: int, body: bytes, closed: bool = True) -> bytes:
    return cartridge.opening(mode) + body + (cartridge.CLOSING if closed else b"")


def _loading(table: int, digits: list[int]) -> bytes:
    held = bytearray(b"\xea" * 0x8000)
    held[table : table + len(digits)] = bytes(digits)
    call = bytes((0xBF, table & 0xFF, table >> 8, 0xC0, 0xDA, 0x22, 0x62, 0x2D, 0xC0))
    held[0x100 : 0x100 + len(call)] = call
    return bytes(held)


INDEX_THEN_READ = bytes((0x8E, 0x41, 0x48, 0xAD, 0x41, 0x48))

FIRST_DAY = [0, 0, 0, 0, 2, 1, 2, 2, 2, 1, 5, 9, 5]


class PortTest(unittest.TestCase):
    def test_the_three_addresses_are_the_ones_the_package_answers_at(self) -> None:
        # Arrange
        expected = sorted((ENABLE, DATA, STATUS))

        # Act
        found = sorted(cartridge.PORTS)

        # Assert
        self.assertEqual(found, expected)

    def test_an_absolute_access_to_a_port_is_found(self) -> None:
        # Arrange
        image = bytes((0x8D, 0x41, 0x48)) + b"\xea" * 64

        # Act
        found = cartridge.touching(image)

        # Assert
        self.assertEqual(found, {(DATA, "write"): 1})

    def test_a_read_is_told_apart_from_a_write(self) -> None:
        # Arrange
        image = bytes((0xAD, 0x42, 0x48)) + b"\xea" * 64

        # Act
        found = cartridge.touching(image)

        # Assert
        self.assertEqual(found, {(STATUS, "read"): 1})

    def test_an_access_to_anything_else_is_not(self) -> None:
        image = bytes((0x8D, 0x00, 0x21)) + b"\xea" * 64

        self.assertEqual(cartridge.touching(image), {})


class RoutineTest(unittest.TestCase):
    def test_the_write_routine_is_found_by_the_shape_of_its_opening(self) -> None:
        image = b"\xea" * 0x2D62 + cartridge.OPENING + b"\xea" * 64

        self.assertEqual(cartridge.write_routine(image), 0x2D62)

    def test_an_image_without_it_yields_nothing(self) -> None:
        self.assertIsNone(cartridge.write_routine(b"\xea" * 0x8000))


class CallerTest(unittest.TestCase):
    def test_a_caller_that_sets_an_index_and_a_value_is_read(self) -> None:
        image = bytearray(b"\xea" * 0x8000)
        body = _writing([(0x0D, 0x06)])
        image[0x100 : 0x100 + len(body)] = body

        self.assertEqual(cartridge.written(bytes(image), 0x2D62), [(0x0D, 0x06)])

    def test_a_caller_whose_index_register_is_narrow_is_read_too(self) -> None:
        image = bytearray(b"\xea" * 0x8000)
        image[0x100:0x107] = bytes((0xA2, 0x0D, 0xA9, 0x06, 0x22, 0x62, 0x2D))
        image[0x107] = 0xC0

        self.assertEqual(cartridge.written(bytes(image), 0x2D62), [(0x0D, 0x06)])

    def test_two_callers_come_back_in_the_order_they_sit(self) -> None:
        image = bytearray(b"\xea" * 0x8000)
        body = _writing([(0x0D, 0x01), (0x0F, 0x07)])
        image[0x100 : 0x100 + len(body)] = body

        self.assertEqual(cartridge.written(bytes(image), 0x2D62), [(0x0D, 0x01), (0x0F, 0x07)])

    def test_a_call_whose_index_and_value_are_not_constants_is_passed_over(self) -> None:
        image = bytearray(b"\xea" * 0x8000)
        image[0x100:0x104] = bytes((0x22, 0x62, 0x2D, 0xC0))

        self.assertEqual(cartridge.written(bytes(image), 0x2D62), [])

    def test_a_call_that_loads_a_value_but_not_an_index_is_passed_over(self) -> None:
        image = bytearray(b"\xea" * 0x8000)
        image[0x100:0x106] = bytes((0xEA, 0xA9, 0x06, 0x22, 0x62, 0x2D))
        image[0x106] = 0xC0

        self.assertEqual(cartridge.written(bytes(image), 0x2D62), [])

    def test_an_image_with_no_caller_yields_nothing(self) -> None:
        self.assertEqual(cartridge.written(b"\xea" * 0x8000, 0x2D62), [])


class ControlTest(unittest.TestCase):
    def test_a_write_to_the_first_control_register_is_named(self) -> None:
        found = cartridge.controls([(0x0D, 0x06)])

        self.assertEqual(found, [{"register": "CD", "value": "0x06", "bits": ["CAL_HW", "IRQ_F"]}])

    def test_a_write_to_a_clock_register_is_not_a_control_write(self) -> None:
        self.assertEqual(cartridge.controls([(0x00, 0x06)]), [])

    def test_the_bits_of_the_last_control_register_are_named_as_its_own(self) -> None:
        found = cartridge.controls([(0x0F, 0x07)])

        self.assertEqual(found[0]["bits"], ["RESET", "STOP", "HOURS_24"])

    def test_a_value_with_no_bits_set_names_none(self) -> None:
        found = cartridge.controls([(0x0D, 0x00)])

        self.assertEqual(found[0]["bits"], [])


class SessionTest(unittest.TestCase):
    def test_a_read_session_that_only_selects_an_index_writes_the_data_port_once(self) -> None:
        # Arrange
        image = b"\xea" * 16 + _session(READ_MODE, INDEX_THEN_READ) + b"\xea" * 16

        # Act
        found = cartridge.sessions(image, READ_MODE)

        # Assert
        self.assertEqual(found, [{"at": 16, "dataWrites": 1}])

    def test_a_write_to_the_data_port_after_the_index_is_counted(self) -> None:
        # Arrange
        body = INDEX_THEN_READ + bytes((0x8D, 0x41, 0x48))
        image = _session(READ_MODE, body) + b"\xea" * 16

        # Act
        found = cartridge.sessions(image, READ_MODE)

        # Assert
        self.assertEqual(found[0]["dataWrites"], 2)

    def test_an_opening_with_no_close_in_reach_is_counted_apart(self) -> None:
        # Arrange
        image = _session(READ_MODE, INDEX_THEN_READ, closed=False) + b"\xea" * 0x100

        # Act
        found = (cartridge.sessions(image, READ_MODE), cartridge.unclosed(image, READ_MODE))

        # Assert
        self.assertEqual(found, ([], 1))


class CenturyTest(unittest.TestCase):
    def test_the_fold_names_the_window_the_program_reads_years_in(self) -> None:
        # Arrange
        image = b"\xea" * 32 + _fold() + b"\xea" * 32

        # Act
        found = cartridge.century(image)

        # Assert
        self.assertEqual(
            found, {"foldAt": 32, "pivot": 95, "base": 1900, "first": 1995, "last": 2094}
        )

    def test_a_fold_whose_two_halves_do_not_make_a_century_is_passed_over(self) -> None:
        # Arrange
        image = _fold(carry=6) + b"\xea" * 32

        # Act
        found = cartridge.century(image)

        # Assert
        self.assertIsNone(found)

    def test_a_fold_without_the_base_beside_it_is_passed_over(self) -> None:
        # Arrange
        image = _fold()[:16] + b"\xea" * 32

        # Act
        found = cartridge.century(image)

        # Assert
        self.assertIsNone(found)

    def test_an_image_with_no_fold_yields_nothing(self) -> None:
        # Arrange
        image = b"\xea" * 0x100

        # Act
        found = cartridge.century(image)

        # Assert
        self.assertIsNone(found)


class LoadedTest(unittest.TestCase):
    def test_the_table_the_initialisation_loads_is_read(self) -> None:
        # Arrange
        image = _loading(0x2EA2, FIRST_DAY)

        # Act
        found = cartridge.loaded(image, 0x2D62)

        # Assert
        self.assertEqual(found, FIRST_DAY)

    def test_a_call_not_fed_from_a_table_yields_nothing(self) -> None:
        # Arrange
        image = bytes(4) + bytes((0xDA, 0x22, 0x62, 0x2D, 0xC0)) + b"\xea" * 16

        # Act
        found = cartridge.loaded(image, 0x2D62)

        # Assert
        self.assertIsNone(found)

    def test_the_digits_read_in_the_window_as_a_date(self) -> None:
        # Arrange
        window = {"pivot": 95, "base": 1900}

        # Act
        found = (cartridge.reading(FIRST_DAY, window), cartridge.reading([0] * 13, window))

        # Assert
        self.assertEqual(found, ("1995-12-22 12:00:00", "2000-00-00 00:00:00"))


class FindingsTest(unittest.TestCase):
    def test_an_image_with_no_fold_records_no_window_and_no_loaded_date(self) -> None:
        # Arrange
        image = _loading(0x2EA2, FIRST_DAY)

        # Act
        found = cartridge.findings(image, 0x2D62)

        # Assert
        self.assertEqual((found["century"], "loadedOnInitialisation" in found), (None, False))

    def test_an_image_with_a_fold_and_a_loaded_table_records_the_date_it_loads(self) -> None:
        # Arrange
        held = bytearray(_loading(0x2EA2, FIRST_DAY))
        held[0x4000 : 0x4000 + len(_fold())] = _fold()

        # Act
        found = cartridge.findings(bytes(held), 0x2D62)

        # Assert
        self.assertEqual(found["loadedOnInitialisation"]["reads"], "1995-12-22 12:00:00")

    def test_a_summary_with_a_fold_names_the_window(self) -> None:
        # Arrange
        said: list[str] = []
        window = {"first": 1995, "last": 2094}

        # Act
        cartridge.summarise({"readSessions": [], "century": window}, said.append)

        # Assert
        self.assertEqual(said[-1], "  years read as 1995 to 2094")

    def test_a_summary_without_a_fold_says_so(self) -> None:
        # Arrange
        said: list[str] = []

        # Act
        cartridge.summarise({"readSessions": [], "century": None}, said.append)

        # Assert
        self.assertEqual(said[-1], "  no year fold was found")


class RecordedTest(unittest.TestCase):
    def test_the_cartridge_writes_the_bit_the_record_asked_about(self) -> None:
        found = cartridge.recorded()

        self.assertIn("CAL_HW", [bit for one in found["controls"] for bit in one["bits"]])

    def test_it_also_holds_the_clock_while_it_loads_it(self) -> None:
        found = cartridge.recorded()

        self.assertIn("HOLD", [bit for one in found["controls"] for bit in one["bits"]])

    def test_it_writes_the_mode_nibbles_the_package_uses(self) -> None:
        # Arrange
        expected = [f"{WRITE_MODE:#04x}", f"{READ_MODE:#04x}"]

        # Act
        found = cartridge.recorded()

        # Assert
        self.assertEqual(
            [found["modes"]["write"], found["modes"]["read"]],
            expected,
        )

    def test_it_names_the_cartridge_with_four_digests(self) -> None:
        found = cartridge.recorded()

        self.assertEqual(
            [key for key in ("crc32", "md5", "sha1", "sha256") if key in found["readFrom"]],
            ["crc32", "md5", "sha1", "sha256"],
        )

    def test_every_read_session_writes_the_data_port_only_to_choose_the_index(self) -> None:
        # Arrange
        found = cartridge.recorded()

        # Act
        writes = {one["dataWrites"] for one in found["readSessions"]}

        # Assert
        self.assertEqual((writes, len(found["readSessions"])), ({1}, 5))

    def test_it_reads_two_digit_years_as_1995_to_2094(self) -> None:
        # Arrange
        found = cartridge.recorded()

        # Act
        window = (found["century"]["first"], found["century"]["last"])

        # Assert
        self.assertEqual(window, (1995, 2094))

    def test_it_loads_a_date_in_1995_when_it_sets_the_clock(self) -> None:
        # Arrange
        found = cartridge.recorded()

        # Act
        loaded = found["loadedOnInitialisation"]["reads"]

        # Assert
        self.assertEqual(loaded, "1995-12-22 12:00:00")

    def test_a_reading_that_is_not_there_reads_as_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            self.assertEqual(cartridge.recorded(Path(where) / "absent.json"), {})


class MainTest(unittest.TestCase):
    def test_with_no_arguments_it_says_how_to_use_it(self) -> None:
        said: list[str] = []

        code = cartridge.main([], say=said.append)

        self.assertEqual((code, "usage" in said[0]), (2, True))

    def test_a_file_that_is_not_there_is_refused(self) -> None:
        said: list[str] = []

        code = cartridge.main(["/nowhere", "/tmp/out.json"], say=said.append)

        self.assertEqual((code, any("no such file" in one for one in said)), (2, True))

    def test_an_image_with_no_clock_routine_reports_that(self) -> None:
        said: list[str] = []
        with tempfile.TemporaryDirectory() as where:
            image = Path(where) / "one.sfc"
            image.write_bytes(b"\xea" * 0x8000)

            code = cartridge.main([str(image), str(Path(where) / "out.json")], say=said.append)

        self.assertEqual((code, any("no clock routine" in one for one in said)), (1, True))

    def test_an_image_carrying_one_is_read_and_recorded(self) -> None:
        said: list[str] = []
        with tempfile.TemporaryDirectory() as where:
            held = bytearray(b"\xea" * 0x8000)
            held[0x2D62 : 0x2D62 + len(cartridge.OPENING)] = cartridge.OPENING
            body = _writing([(0x0D, 0x06)])
            held[0x100 : 0x100 + len(body)] = body
            image = Path(where) / "one.sfc"
            image.write_bytes(bytes(held))
            out = Path(where) / "out.json"

            code = cartridge.main([str(image), str(out)], say=said.append)

            self.assertEqual(
                (code, json.loads(out.read_text())["controls"][0]["register"]), (0, "CD")
            )


if __name__ == "__main__":
    unittest.main()
