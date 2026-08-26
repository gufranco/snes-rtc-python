"""Reading the clock routine out of the one cartridge that carries this part."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conformance import cartridge
from snesrtc import epson


def _writing(pairs: list[tuple[int, int]], where: int = 0x2D62) -> bytes:
    """A caller that loads an index and a value and calls the write routine."""
    body = bytearray()
    for index, value in pairs:
        body += bytes((0xA2, index, 0x00))
        body += bytes((0xA9, value))
        body += bytes((0x22, where & 0xFF, where >> 8, 0xC0))
    body += bytes((0x6B,))
    return bytes(body)


class PortTest(unittest.TestCase):
    def test_the_three_addresses_are_the_ones_the_package_answers_at(self) -> None:
        self.assertEqual(sorted(cartridge.PORTS), sorted((epson.ENABLE, epson.DATA, epson.STATUS)))

    def test_an_absolute_access_to_a_port_is_found(self) -> None:
        image = bytes((0x8D, 0x41, 0x48)) + b"\xea" * 64

        self.assertEqual(cartridge.touching(image), {(epson.DATA, "write"): 1})

    def test_a_read_is_told_apart_from_a_write(self) -> None:
        image = bytes((0xAD, 0x42, 0x48)) + b"\xea" * 64

        self.assertEqual(cartridge.touching(image), {(epson.STATUS, "read"): 1})

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


class RecordedTest(unittest.TestCase):
    def test_the_cartridge_writes_the_bit_the_record_asked_about(self) -> None:
        found = cartridge.recorded()

        self.assertIn("CAL_HW", [bit for one in found["controls"] for bit in one["bits"]])

    def test_it_also_holds_the_clock_while_it_loads_it(self) -> None:
        found = cartridge.recorded()

        self.assertIn("HOLD", [bit for one in found["controls"] for bit in one["bits"]])

    def test_it_writes_the_mode_nibbles_the_package_uses(self) -> None:
        found = cartridge.recorded()

        self.assertEqual(
            [found["modes"]["write"], found["modes"]["read"]],
            [f"{epson.WRITE_MODE:#04x}", f"{epson.READ_MODE:#04x}"],
        )

    def test_it_names_the_cartridge_with_four_digests(self) -> None:
        found = cartridge.recorded()

        self.assertEqual(
            [key for key in ("crc32", "md5", "sha1", "sha256") if key in found["readFrom"]],
            ["crc32", "md5", "sha1", "sha256"],
        )

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
