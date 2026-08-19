import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build

HAS_COMPILER = shutil.which(build.COMPILER) is not None


class DefinitionTest(unittest.TestCase):
    def test_the_reference_is_pinned_to_a_commit(self):
        self.assertEqual(len(build.reference()["commit"]), 40)

    def test_it_names_where_the_sources_come_from(self):
        self.assertTrue(build.reference()["repository"].startswith("https://"))

    def test_it_names_every_file_the_driver_includes(self):
        named = build.reference()["files"]

        self.assertIn("srtcemu.cpp", named)
        self.assertIn("spc7110emu.cpp", named)

    def test_a_definition_can_be_read_from_somewhere_else(self):
        elsewhere = Path(tempfile.mkdtemp()) / "pinned.json"
        elsewhere.write_text('{"reference": {"commit": "abc", "repository": "x", "files": []}}')

        self.assertEqual(build.reference(elsewhere)["commit"], "abc")


class CheckoutTest(unittest.TestCase):
    def test_the_checkout_takes_only_the_directory_the_sources_are_in(self):
        steps = build.checkout_command(build.reference(), Path("/somewhere"))

        self.assertTrue(any("sparse-checkout" in " ".join(step) for step in steps))

    def test_it_fetches_the_pinned_commit_rather_than_whatever_is_current(self):
        steps = build.checkout_command(build.reference(), Path("/somewhere"))

        self.assertTrue(any(build.reference()["commit"] in step for step in steps))

    def test_it_asks_for_no_history_it_does_not_need(self):
        steps = build.checkout_command(build.reference(), Path("/somewhere"))

        self.assertTrue(any("--depth=1" in step for step in steps))


class CompileTest(unittest.TestCase):
    def test_the_compile_names_the_driver_this_repository_owns(self):
        command = build.compile_command(Path("/sources"), Path("/out/driver"))

        self.assertIn("driver.cpp", " ".join(command))

    def test_and_points_the_compiler_at_the_fetched_sources(self):
        command = build.compile_command(Path("/sources"), Path("/out/driver"))

        self.assertIn("-I/sources", command)

    def test_the_output_goes_where_it_was_asked(self):
        command = build.compile_command(Path("/sources"), Path("/out/driver"))

        self.assertIn("/out/driver", command)


class OptionTest(unittest.TestCase):
    def test_the_defaults_are_enough(self):
        self.assertEqual(build.options([]).output, build.DEFAULT_OUTPUT)

    def test_the_output_can_be_set(self):
        self.assertEqual(build.options(["--output", "somewhere"]).output, "somewhere")

    def test_so_can_where_the_sources_are_kept(self):
        self.assertEqual(build.options(["--sources", "here"]).sources, "here")

    def test_an_option_with_no_value_is_refused(self):
        with self.assertRaises(build.Usage):
            build.options(["--output"])

    def test_an_option_it_does_not_know_is_refused(self):
        with self.assertRaises(build.Usage):
            build.options(["--nonsense"])

    def test_the_pinned_definition_can_be_pointed_elsewhere(self):
        self.assertEqual(build.options(["--pinned", "somewhere"]).pinned, "somewhere")

    def test_and_so_can_the_driver_being_built(self):
        self.assertEqual(build.options(["--driver-source", "other.cpp"]).driver, "other.cpp")


class LocalUpstream:
    """A git repository on disk, so the fetch path can be exercised offline."""

    def __init__(self):
        self.where = Path(tempfile.mkdtemp()) / "upstream"
        self.where.mkdir(parents=True)
        (self.where / "hello.cpp").write_text("int main(void) { return 0; }\n")
        for step in (
            ["git", "init", "-q", "-b", "main", str(self.where)],
            ["git", "-C", str(self.where), "add", "-A"],
            [
                "git",
                "-C",
                str(self.where),
                "-c",
                "user.name=t",
                "-c",
                "user.email=t@t",
                "commit",
                "-q",
                "-m",
                "seed",
            ],
        ):
            subprocess.run(step, check=True, capture_output=True)
        self.commit = subprocess.run(
            ["git", "-C", str(self.where), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def pinned(self):
        return {
            "name": "local",
            "repository": str(self.where),
            "commit": self.commit,
            "sparse": ["."],
            "path": ".",
            "files": ["hello.cpp"],
        }

    def definition(self):
        where = Path(tempfile.mkdtemp()) / "pinned.json"
        where.write_text(json.dumps({"reference": self.pinned()}))
        return where


class FetchTest(unittest.TestCase):
    def test_fetching_brings_the_pinned_commit_down(self):
        upstream = LocalUpstream()
        into = Path(tempfile.mkdtemp()) / "sources"

        where = build.fetch(upstream.pinned(), into)

        self.assertTrue((where / "hello.cpp").exists())

    def test_a_fetch_that_cannot_be_done_is_reported_rather_than_ignored(self):
        broken = {
            "repository": "/nowhere/at/all",
            "commit": "0" * 40,
            "sparse": ["."],
            "path": ".",
        }

        with self.assertRaises(build.Usage):
            build.fetch(broken, Path(tempfile.mkdtemp()) / "sources")


@unittest.skipUnless(HAS_COMPILER, "no compiler available")
class WholeBuildTest(unittest.TestCase):
    def test_a_build_fetches_what_it_needs_and_reports_what_it_built(self):
        upstream = LocalUpstream()
        working = Path(tempfile.mkdtemp())

        answered = build.main(
            [
                "--pinned",
                str(upstream.definition()),
                "--sources",
                str(working / "sources"),
                "--output",
                str(working / "built"),
                "--driver-source",
                str(upstream.where / "hello.cpp"),
            ]
        )

        self.assertEqual(answered, 0)
        self.assertTrue((working / "built").exists())


class EntryTest(unittest.TestCase):
    def test_an_option_it_does_not_know_is_reported(self):
        self.assertEqual(build.main(["--nonsense"]), 2)

    @unittest.skipUnless(HAS_COMPILER, "no compiler available")
    def test_building_against_a_directory_holding_no_sources_fails_rather_than_passing(self):
        where = Path(tempfile.mkdtemp())

        self.assertEqual(
            build.main(["--sources", str(where), "--output", str(where / "driver")]), 1
        )


if __name__ == "__main__":
    unittest.main()
