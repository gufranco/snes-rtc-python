import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conformance import sharp_cartridge as reader

TAIL = bytes((0xC2, 0x20, 0xEE, 0x04, 0xE2, 0x60))

BUFFER = 0xE220

TO_PORT = bytes((0x29, 0x0F, 0x8F, 0x01, 0x28, 0x00))

MARKER = bytes((0xE2, 0x20, 0xAF, 0x00, 0x28, 0x00, 0xC2, 0x20, 0x29, 0x0F, 0x00, 0xC9, 0x0F, 0x00))

FINISH = bytes((0xC2, 0x20, 0x9C, 0x04, 0xE2, 0x60))


def _command(value: int) -> bytes:
    return bytes((0xE2, 0x20, 0xA9, value)) + TO_PORT + TAIL


def _send(buffer: int) -> bytes:
    return bytes((0xE2, 0x20, 0xAD)) + buffer.to_bytes(2, "little") + TO_PORT + TAIL


def _take(buffer: int) -> bytes:
    held = bytes((0xE2, 0x20, 0xAF, 0x00, 0x28, 0x00, 0x29, 0x0F, 0x8D))
    return held + buffer.to_bytes(2, "little") + TAIL


class _Bank:
    def __init__(self) -> None:
        self.image = bytearray(b"\xea" * 0x20000)
        self.at = 0x10100
        self.words: list[int] = []

    def step(self, body: bytes) -> "_Bank":
        self.image[self.at : self.at + len(body)] = body
        self.words.append(self.at & 0xFFFF)
        self.at += len(body) + 1
        return self

    def again(self, which: int) -> "_Bank":
        self.words.append(self.words[which])
        return self

    def built(self, table: int = 0x18000) -> bytes:
        for offset, word in enumerate(self.words):
            self.image[table + offset * 2 : table + offset * 2 + 2] = word.to_bytes(2, "little")
        return bytes(self.image)


def _a_program() -> bytes:
    bank = _Bank()
    bank.step(_command(0x0E)).step(TAIL).step(_command(0x00))
    for offset in range(3):
        bank.step(_send(BUFFER + offset))
    bank.step(_command(0x0D)).step(FINISH).step(MARKER)
    for offset in range(3):
        bank.step(_take(BUFFER + offset))
    return bank.again(8).again(7).built()


def _a_folder(case: unittest.TestCase) -> Path:
    where = Path(tempfile.mkdtemp())
    case.addCleanup(shutil.rmtree, where)
    return where


class StepTest(unittest.TestCase):
    def test_a_constant_written_to_the_command_port_is_a_command(self) -> None:
        # Arrange
        image = b"\xea" * 8 + _command(0x0E)

        # Act
        found = reader.steps(image)

        # Assert
        self.assertEqual(found[8], ("command", 0x0E))

    def test_a_buffered_digit_written_to_it_is_a_send_from_that_buffer(self) -> None:
        # Arrange
        image = _send(BUFFER + 4)

        # Act
        found = reader.steps(image)

        # Assert
        self.assertEqual(found[0], ("send", BUFFER + 4))

    def test_a_digit_read_into_a_buffer_is_a_take(self) -> None:
        # Arrange
        image = _take(BUFFER + 2)

        # Act
        found = reader.steps(image)

        # Assert
        self.assertEqual(found[0], ("take", BUFFER + 2))


class TableTest(unittest.TestCase):
    def test_the_longest_run_of_step_addresses_is_the_table(self) -> None:
        # Arrange
        image = _a_program()

        # Act
        at, run = reader.table(image, reader.steps(image))

        # Assert
        self.assertEqual((at, len(run)), (0x18000, 14))

    def test_a_run_that_reaches_the_end_of_the_image_stops_there(self) -> None:
        # Arrange
        image = bytes(6)

        # Act
        found = reader.run_at(image, 0, {0: ("wait", 0)})

        # Assert
        self.assertEqual(found, [("wait", 0)] * 3)

    def test_an_image_with_no_run_long_enough_has_no_table(self) -> None:
        # Arrange
        image = _command(0x0E) + b"\xea" * 64

        # Act
        found = reader.table(image, reader.steps(image))

        # Assert
        self.assertEqual(found, (-1, []))


class ScriptTest(unittest.TestCase):
    def test_a_table_splits_into_scripts_at_each_finish(self) -> None:
        # Arrange
        image = _a_program()
        _, run = reader.table(image, reader.steps(image))

        # Act
        found = reader.scripts(run)

        # Assert
        self.assertEqual(
            found,
            [
                ["0x0e", "0x00", "send 0", "send 1", "send 2", "0x0d"],
                ["marker", "take 0", "take 1", "take 2", "marker"],
            ],
        )

    def test_a_run_of_consecutive_digits_folds_into_a_range(self) -> None:
        # Arrange
        script = ["0x0e", "send 4", "send 5", "send 6", "take 9", "marker"]

        # Act
        found = reader.folded(script)

        # Assert
        self.assertEqual(found, ["0x0e", "send 4 to 6", "take 9 to 9", "marker"])


class ReadingTest(unittest.TestCase):
    def test_a_program_with_a_table_is_read_into_scripts_and_commands(self) -> None:
        # Arrange
        image = _a_program()

        # Act
        found = reader.reading(image, "one.sfc")

        # Assert
        assert found is not None
        self.assertEqual(
            (found["tableAt"], found["commands"], found["scripts"][0]),
            ("0x018000", ["0x00"], ["0x0e", "0x00", "send 0 to 2", "0x0d"]),
        )

    def test_a_program_without_one_is_not(self) -> None:
        # Arrange
        image = b"\xea" * 0x100

        # Act
        found = reader.reading(image, "one.sfc")

        # Assert
        self.assertIsNone(found)


class RecordedTest(unittest.TestCase):
    def test_the_program_sends_eight_commands_after_the_command_code(self) -> None:
        # Arrange
        found = reader.recorded()

        # Act
        commands = found["commands"]

        # Assert
        self.assertEqual(commands, [f"{value:#04x}" for value in range(8)])

    def test_it_reads_a_marker_thirteen_digits_and_a_marker(self) -> None:
        # Arrange
        found = reader.recorded()

        # Act
        reads = [one for one in found["scripts"] if one[0] == "marker"]

        # Assert
        self.assertEqual(reads, [["marker", "take 0 to 12", "marker"]])

    def test_it_writes_twelve_digits_after_command_zero_and_no_weekday(self) -> None:
        # Arrange
        found = reader.recorded()

        # Act
        written = [one for one in found["scripts"] if one[:2] == ["0x0e", "0x00"]]

        # Assert
        self.assertEqual(written, [["0x0e", "0x00", "send 0 to 11", "0x0d"]])

    def test_it_names_the_cartridge_with_four_digests(self) -> None:
        # Arrange
        found = reader.recorded()

        # Act
        held = [key for key in ("crc32", "md5", "sha1", "sha256") if key in found["readFrom"]]

        # Assert
        self.assertEqual(held, ["crc32", "md5", "sha1", "sha256"])

    def test_a_reading_that_is_not_there_reads_as_nothing(self) -> None:
        # Arrange
        where = _a_folder(self) / "absent.json"

        # Act
        found = reader.recorded(where)

        # Assert
        self.assertEqual(found, {})


class MainTest(unittest.TestCase):
    def test_with_no_arguments_it_says_how_to_use_it(self) -> None:
        # Arrange
        said: list[str] = []

        # Act
        code = reader.main([], say=said.append)

        # Assert
        self.assertEqual((code, "usage" in said[0]), (2, True))

    def test_a_file_that_is_not_there_is_refused(self) -> None:
        # Arrange
        said: list[str] = []

        # Act
        code = reader.main(["/nowhere", "/tmp/out.json"], say=said.append)

        # Assert
        self.assertEqual((code, any("no such file" in one for one in said)), (2, True))

    def test_an_image_with_no_table_reports_that(self) -> None:
        # Arrange
        said: list[str] = []
        image = _a_folder(self) / "one.sfc"
        image.write_bytes(b"\xea" * 0x100)

        # Act
        code = reader.main([str(image), str(image.with_suffix(".json"))], say=said.append)

        # Assert
        self.assertEqual((code, any("no clock script table" in one for one in said)), (1, True))

    def test_an_image_carrying_one_is_read_and_recorded(self) -> None:
        # Arrange
        said: list[str] = []
        image = _a_folder(self) / "one.sfc"
        image.write_bytes(_a_program())
        out = image.with_suffix(".json")

        # Act
        code = reader.main([str(image), str(out)], say=said.append)

        # Assert
        self.assertEqual((code, json.loads(out.read_text())["commands"]), (0, ["0x00"]))


if __name__ == "__main__":
    unittest.main()
