from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from snesrtc import Chip, UnknownModelError  # noqa: E402

ERRORS = ROOT / "snesrtc" / "errors.py"


def reaching_back(source: str) -> list[str]:

    def inside(name: str) -> bool:
        return name.startswith(".") or name == "snesrtc" or name.startswith("snesrtc.")

    borrowed = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            borrowed += [alias.name for alias in node.names if inside(alias.name)]
        elif isinstance(node, ast.ImportFrom):
            name = "." * node.level + (node.module or "")
            if inside(name):
                borrowed.append(name)
    return borrowed


def defined_classes(source: str) -> list[str]:
    return [node.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ClassDef)]


class OneHomeTest(unittest.TestCase):
    def test_the_module_defines_the_refusal_this_package_makes(self) -> None:
        # Arrange
        held = ERRORS.read_text()

        # Act
        named = defined_classes(held)

        # Assert
        self.assertEqual(named, ["UnknownModelError"])

    def test_it_derives_from_exception(self) -> None:
        # Arrange
        refusal = UnknownModelError

        # Act
        derived = issubclass(refusal, Exception)

        # Assert
        self.assertIs(derived, True)

    def test_and_the_exported_name_is_the_one_defined_there(self) -> None:
        # Arrange
        refusal = UnknownModelError

        # Act
        home = refusal.__module__

        # Assert
        self.assertEqual(home, "snesrtc.errors")

    def test_naming_a_clock_this_package_does_not_cover_raises_the_one_defined_here(
        self,
    ) -> None:
        # Arrange
        name = "rtc-62421"

        # Act
        with self.assertRaises(UnknownModelError) as caught:
            Chip(name)

        # Assert
        self.assertIsInstance(caught.exception, UnknownModelError)

    def test_and_the_refusal_names_the_clocks_it_does_cover(self) -> None:
        # Arrange
        name = "rtc-62421"

        # Act
        with self.assertRaises(UnknownModelError) as caught:
            Chip(name)

        # Assert
        self.assertEqual(
            str(caught.exception),
            "rtc-62421 is not a clock this package covers; it has rtc-4513, s-rtc",
        )


class NoCycleTest(unittest.TestCase):
    def test_it_imports_nothing_from_this_package(self) -> None:
        # Arrange
        held = ERRORS.read_text()

        # Act
        found = reaching_back(held)

        # Assert
        self.assertEqual(found, [])

    def test_the_reader_of_that_names_an_absolute_import_back(self) -> None:
        # Arrange
        source = "import snesrtc.models\n"

        # Act
        found = reaching_back(source)

        # Assert
        self.assertEqual(found, ["snesrtc.models"])

    def test_and_a_relative_one(self) -> None:
        # Arrange
        source = "from . import models\n"

        # Act
        found = reaching_back(source)

        # Assert
        self.assertEqual(found, ["."])

    def test_and_steps_over_one_from_outside(self) -> None:
        # Arrange
        source = "from __future__ import annotations\nimport snesrtctools\n"

        # Act
        found = reaching_back(source)

        # Assert
        self.assertEqual(found, [])

    def test_the_reader_of_classes_names_each_one_defined(self) -> None:
        # Arrange
        source = "class One(Exception): ...\n\n\nclass Two(One): ...\n"

        # Act
        found = defined_classes(source)

        # Assert
        self.assertEqual(found, ["One", "Two"])


if __name__ == "__main__":
    unittest.main()
