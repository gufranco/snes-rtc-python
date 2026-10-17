import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def load_module(name: str, where: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, where)
    assert spec is not None and spec.loader is not None, "no loader for that path"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


environment = load_module("environment", Path(__file__).resolve().parent / "environment.py")


def nested(where: Path, top: str, leaf: str) -> None:
    deep = where.joinpath(*filter(None, (top, "a" * 120, "b" * 120)))
    deep.mkdir(parents=True)
    (deep / leaf).write_bytes(b"")


class PathBudgetTest(unittest.TestCase):
    def test_a_short_path_on_windows_is_fine(self) -> None:
        # Arrange
        root = Path("C:/a")

        # Act
        found = environment.path_budget(root, windows=True, longest=80)

        # Assert
        self.assertTrue(found.ok)

    def test_a_path_past_the_windows_limit_is_not(self) -> None:
        # Arrange
        root = Path("C:/a")

        # Act
        found = environment.path_budget(root, windows=True, longest=300)

        # Assert
        self.assertFalse(found.ok)

    def test_and_the_advice_names_the_setting_that_lifts_it(self) -> None:
        # Arrange
        root = Path("C:/a")

        # Act
        found = environment.path_budget(root, windows=True, longest=300)

        # Assert
        self.assertIn("LongPathsEnabled", found.advice)

    def test_the_same_length_elsewhere_is_still_reported(self) -> None:
        # Arrange
        root = Path("/a")

        # Act
        found = environment.path_budget(root, windows=False, longest=300)

        # Assert
        self.assertFalse(found.ok)

    def test_because_the_tree_is_shared_rather_than_local_to_one_machine(self) -> None:
        # Arrange
        roots = ((Path("/a"), False), (Path("C:/a"), True))

        # Act
        found = [environment.path_budget(root, windows=on, longest=300).ok for root, on in roots]

        # Assert
        self.assertEqual(found, [False, False])

    def test_the_headroom_a_windows_checkout_would_have_is_reported(self) -> None:
        # Arrange
        root = Path("/a")

        # Act
        found = environment.path_budget(root, windows=False, longest=100)

        # Assert
        self.assertIn("160", found.detail)

    def test_a_tree_that_leaves_no_room_for_a_checkout_path_is_flagged_anywhere(self) -> None:
        # Arrange
        root = Path("/a")

        # Act
        found = environment.path_budget(root, windows=False, longest=250)

        # Assert
        self.assertFalse(found.ok)

    def test_and_the_advice_says_it_is_about_windows_rather_than_here(self) -> None:
        # Arrange
        root = Path("/a")

        # Act
        found = environment.path_budget(root, windows=False, longest=250)

        # Assert
        self.assertIn("Windows", found.advice)

    def test_a_tree_with_room_to_spare_passes_on_every_system(self) -> None:
        # Arrange
        systems = (True, False)

        # Act
        found = [environment.path_budget(Path("/a"), windows=on, longest=100).ok for on in systems]

        # Assert
        self.assertEqual(found, [True, True])

    def test_a_generated_directory_is_reported_without_failing_the_check(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        nested(where, "node_modules", "c.js")

        # Act
        found = environment.path_budget(where)

        # Assert
        self.assertTrue(found.ok)

    def test_but_the_same_depth_in_tracked_content_does_fail_it(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        nested(where, "", "c.py")

        # Act
        found = environment.path_budget(where)

        # Assert
        self.assertFalse(found.ok)

    def test_and_a_generated_one_is_still_named_so_it_is_not_a_surprise(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        nested(where, "node_modules", "c.js")

        # Act
        found = environment.path_budget(where)

        # Assert
        self.assertIn("node_modules", found.detail)


class ToolTest(unittest.TestCase):
    def test_a_tool_that_is_present_is_reported_with_where(self) -> None:
        # Arrange
        def look(_name: str) -> str | None:
            return "/usr/bin/git"

        # Act
        found = environment.tool("git", look=look)

        # Assert
        self.assertTrue(found.ok)

    def test_one_that_is_absent_is_not_ok(self) -> None:
        # Arrange
        def look(_name: str) -> str | None:
            return None

        # Act
        found = environment.tool("git", look=look)

        # Assert
        self.assertFalse(found.ok)

    def test_an_optional_tool_that_is_absent_is_still_ok(self) -> None:
        # Arrange
        def look(_name: str) -> str | None:
            return None

        # Act
        found = environment.tool("docker", look=look, required=False)

        # Assert
        self.assertTrue(found.ok)

    def test_but_says_it_was_not_found(self) -> None:
        # Arrange
        def look(_name: str) -> str | None:
            return None

        # Act
        found = environment.tool("docker", look=look, required=False)

        # Assert
        self.assertIn("not found", found.detail)


class SpaceTest(unittest.TestCase):
    def test_plenty_of_room_is_fine(self) -> None:
        # Arrange
        def measure(_path: Path) -> int:
            return 40 * 1024**3

        # Act
        found = environment.free_space(ROOT, measure=measure)

        # Assert
        self.assertTrue(found.ok)

    def test_a_nearly_full_disk_is_not(self) -> None:
        # Arrange
        def measure(_path: Path) -> int:
            return 100 * 1024**2

        # Act
        found = environment.free_space(ROOT, measure=measure)

        # Assert
        self.assertFalse(found.ok)

    def test_a_disk_it_cannot_measure_is_reported_rather_than_assumed(self) -> None:
        # Arrange
        def refuse(_path: Path) -> int:
            raise OSError("no")

        # Act
        found = environment.free_space(ROOT, measure=refuse)

        # Assert
        self.assertFalse(found.ok)

    def test_a_case_insensitive_answer_is_reported_and_is_not_a_fault(self) -> None:
        # Arrange
        insensitive = True

        # Act
        found = environment.filesystem_case(ROOT, insensitive=insensitive)

        # Assert
        self.assertEqual((found.ok, "insensitive" in found.detail), (True, True))

    def test_a_case_sensitive_answer_is_reported_the_same_way(self) -> None:
        # Arrange
        insensitive = False

        # Act
        found = environment.filesystem_case(ROOT, insensitive=insensitive)

        # Assert
        self.assertEqual((found.ok, found.detail), (True, "case sensitive"))

    def test_a_root_it_cannot_write_to_is_reported_rather_than_raised(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        where.chmod(0o500)
        self.addCleanup(where.chmod, 0o700)

        # Act
        found = environment.filesystem_case(where)

        # Assert
        self.assertEqual((found.ok, "could not probe" in found.detail), (True, True))


class LocaleTest(unittest.TestCase):
    def test_utf8_mode_on_is_fine_whatever_the_locale_says(self) -> None:
        # Arrange
        preferred = "cp1252"

        # Act
        found = environment.locale_setting(preferred=preferred, utf8=1)

        # Assert
        self.assertTrue(found.ok)

    def test_a_utf8_locale_is_fine_with_the_mode_off(self) -> None:
        # Arrange
        preferred = "UTF-8"

        # Act
        found = environment.locale_setting(preferred=preferred, utf8=0)

        # Assert
        self.assertTrue(found.ok)

    def test_a_legacy_locale_with_the_mode_off_is_not(self) -> None:
        # Arrange
        preferred = "cp1252"

        # Act
        found = environment.locale_setting(preferred=preferred, utf8=0)

        # Assert
        self.assertFalse(found.ok)

    def test_and_the_advice_names_the_switch(self) -> None:
        # Arrange
        preferred = "cp1252"

        # Act
        found = environment.locale_setting(preferred=preferred, utf8=0)

        # Assert
        self.assertIn("PYTHONUTF8", found.advice)


if __name__ == "__main__":
    unittest.main()
