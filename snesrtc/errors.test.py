from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from snesrtc import errors  # noqa: E402


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


class OneHomeTest(unittest.TestCase):
    def named(self) -> list[str]:
        return [
            name
            for name, held in vars(errors).items()
            if isinstance(held, type) and issubclass(held, Exception)
        ]

    def test_the_module_defines_the_refusal_this_package_makes(self) -> None:
        self.assertEqual(sorted(self.named()), ["UnknownModelError"])

    def test_it_derives_from_exception(self) -> None:
        stray = [name for name in self.named() if not issubclass(getattr(errors, name), Exception)]

        self.assertEqual(stray, [])

    def test_naming_a_clock_this_package_does_not_cover_raises_the_one_defined_here(
        self,
    ) -> None:
        from snesrtc import models

        with self.assertRaises(errors.UnknownModelError):
            models.lookup("rtc-62421")

    def test_and_the_refusal_names_the_clocks_it_does_cover(self) -> None:
        from snesrtc import models

        with self.assertRaises(errors.UnknownModelError) as caught:
            models.lookup("rtc-62421")

        self.assertIn("s-rtc", str(caught.exception))


class NoCycleTest(unittest.TestCase):
    def test_it_imports_nothing_from_this_package(self) -> None:
        held = (ROOT / "snesrtc" / "errors.py").read_text()

        self.assertEqual(reaching_back(held), [])

    def test_the_reader_of_that_names_an_absolute_import_back(self) -> None:
        found = reaching_back("import snesrtc.models\n")

        self.assertEqual(found, ["snesrtc.models"])

    def test_and_a_relative_one(self) -> None:
        found = reaching_back("from . import models\n")

        self.assertEqual(found, ["."])

    def test_and_steps_over_one_from_outside(self) -> None:
        found = reaching_back("from __future__ import annotations\nimport snesrtctools\n")

        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
