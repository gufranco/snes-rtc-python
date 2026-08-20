import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesrtc import doctor


class Complaint(Exception):
    pass


def a_finding(name="something", ok=True, detail="detail", advice=None):
    return doctor.Finding(name, ok, detail, advice)


def a_pin(name="snes9x", commit="2971061"):
    where = Path(tempfile.mkdtemp()) / "pinned.json"
    where.write_text(json.dumps({"reference": {"name": name, "commit": commit}}))
    return where


class FindingTest(unittest.TestCase):
    def test_a_finding_says_what_was_checked(self):
        self.assertEqual(a_finding(name="the clock").name, "the clock")

    def test_and_whether_it_was_well(self):
        self.assertTrue(a_finding(ok=True).ok)
        self.assertFalse(a_finding(ok=False).ok)

    def test_a_healthy_finding_prints_with_a_mark_that_says_so(self):
        self.assertIn("ok", a_finding(ok=True).line)

    def test_and_an_unhealthy_one_prints_differently(self):
        self.assertNotIn("ok", a_finding(ok=False).line)

    def test_every_finding_carries_what_it_actually_saw(self):
        self.assertIn("two addresses", a_finding(detail="two addresses").line)

    def test_an_unhealthy_finding_says_what_to_do_about_it(self):
        self.assertIn("go and look", a_finding(ok=False, advice="go and look").report)

    def test_a_healthy_one_carries_no_advice(self):
        self.assertEqual(a_finding(ok=True, advice="x").report, a_finding(ok=True).line)

    def test_a_finding_prints_as_itself(self):
        self.assertIn("something", repr(a_finding()))


class ExamineTest(unittest.TestCase):
    def test_the_examination_produces_findings(self):
        self.assertTrue(doctor.examine())

    def test_it_reports_the_python_it_is_running_on(self):
        self.assertIn("python", [one.name for one in doctor.examine()])

    def test_and_the_version_of_this_package(self):
        self.assertIn("snesrtc", [one.name for one in doctor.examine()])

    def test_and_one_finding_per_clock_it_covers(self):
        from snesrtc import models

        names = [one.name for one in doctor.examine()]

        for model in models.MODELS:
            self.assertIn(model, names, model)

    def test_every_finding_carries_a_detail(self):
        for one in doctor.examine():
            self.assertTrue(one.detail, one.name)

    def test_a_clock_that_will_not_build_is_reported_rather_than_hidden(self):
        def boom(_name):
            raise Complaint("the clock exploded")

        self.assertTrue(any(not one.ok for one in doctor.examine(build=boom)))

    def test_and_the_report_carries_what_it_said_and_what_kind(self):
        def boom(_name):
            raise Complaint("the clock exploded")

        text = "\n".join(one.report for one in doctor.examine(build=boom))

        self.assertIn("the clock exploded", text)
        self.assertIn("Complaint", text)

    def test_a_clock_is_reported_with_the_addresses_it_answers(self):
        for one in doctor.examine():
            if one.name == "s-rtc":
                self.assertIn("0x2800", one.detail)


class TimeSourceTest(unittest.TestCase):
    """That the clock is driven by a source somebody chose, not by this machine.

    A model that reads the host clock cannot be replayed, and every disagreement
    about it becomes an argument about when it was run. The source is injectable
    here, and the report says so along with what it currently reads.
    """

    def test_the_report_names_the_time_source(self):
        self.assertIn("time source", [one.name for one in doctor.examine()])

    def test_a_clock_told_a_moment_reads_that_moment_back(self):
        for one in doctor.examine():
            if one.name == "time source":
                self.assertTrue(one.ok)

    def test_a_clock_that_ignores_what_it_was_told_is_a_failure(self):
        class Deaf:
            @staticmethod
            def now():
                return 0

        found = doctor._time_source(lambda _name, **_options: Deaf())

        self.assertFalse(found.ok)

    def test_a_source_that_throws_is_reported_rather_than_swallowed(self):
        def boom(_name, **_options):
            raise Complaint("no clock at all")

        found = doctor._time_source(boom)

        self.assertFalse(found.ok)
        self.assertIn("no clock at all", found.detail)


class ForeignAddressTest(unittest.TestCase):
    def test_an_address_the_clock_does_not_own_reads_open_bus(self):
        for one in doctor.examine():
            if one.name == "foreign address":
                self.assertTrue(one.ok)

    def test_a_clock_that_answers_anything_there_is_a_failure(self):
        class TooKind:
            open_bus = 0x00

            @staticmethod
            def read(_address):
                return 0x42

        found = doctor._foreign(lambda _name, **_options: TooKind())

        self.assertFalse(found.ok)

    def test_a_read_that_throws_is_reported_rather_than_swallowed(self):
        def boom(_name, **_options):
            raise Complaint("no bus at all")

        found = doctor._foreign(boom)

        self.assertFalse(found.ok)
        self.assertIn("no bus at all", found.detail)


class PinTest(unittest.TestCase):
    def test_the_reference_it_is_held_to_is_named(self):
        found = doctor.examine(pin=a_pin(name="somebody else"))

        self.assertIn("somebody else", " ".join(one.detail for one in found))

    def test_and_the_commit_it_is_pinned_to(self):
        found = doctor.examine(pin=a_pin(commit="deadbeef"))

        self.assertIn("deadbeef", " ".join(one.detail for one in found))

    def test_and_the_digest_of_the_file_that_says_so(self):
        import hashlib

        where = a_pin()

        found = doctor.examine(pin=where)

        self.assertIn(
            hashlib.sha256(where.read_bytes()).hexdigest(), " ".join(one.detail for one in found)
        )

    def test_a_pin_that_is_not_here_is_a_failure(self):
        found = doctor.examine(pin=Path("/nowhere/at/all.json"))

        self.assertTrue(any(one.name == "reference" and not one.ok for one in found))

    def test_a_pin_that_is_here_and_damaged_says_so(self):
        where = Path(tempfile.mkdtemp()) / "pinned.json"
        where.write_text("{ not json at all")

        found = doctor.examine(pin=where)

        self.assertIn("not readable as JSON", " ".join(one.detail for one in found))

    def test_a_pin_that_names_nothing_is_a_failure(self):
        where = Path(tempfile.mkdtemp()) / "pinned.json"
        where.write_text(json.dumps({}))

        found = doctor.examine(pin=where)

        self.assertTrue(any(one.name == "reference" and not one.ok for one in found))

    def test_the_pin_it_reads_by_default_is_the_one_in_this_repository(self):
        self.assertTrue(doctor.PIN.exists())


class DriverTest(unittest.TestCase):
    def test_a_driver_that_is_built_is_reported_as_here(self):
        where = Path(tempfile.mkdtemp()) / "driver"
        where.write_bytes(b"not really a driver")

        self.assertIn(
            "built and here", " ".join(one.detail for one in doctor.examine(driver=where))
        )

    def test_one_that_is_not_built_says_what_will_skip(self):
        found = doctor.examine(driver=Path("/nowhere/at/all"))

        self.assertIn("skip", " ".join(one.detail for one in found))

    def test_and_that_is_not_treated_as_a_failure(self):
        for one in doctor.examine(driver=Path("/nowhere/at/all")):
            if one.name == "reference driver":
                self.assertTrue(one.ok)


class ReportTest(unittest.TestCase):
    def test_the_report_has_a_line_for_every_finding(self):
        found = doctor.examine()

        self.assertGreaterEqual(len(doctor.report(found)), len(found))

    def test_it_opens_with_something_that_says_what_it_is(self):
        self.assertIn("snesrtc", doctor.report(doctor.examine())[0])

    def test_an_unhealthy_run_says_how_many_did_not_pass(self):
        self.assertIn("1", " ".join(doctor.report([a_finding(ok=False)])))

    def test_a_healthy_run_says_there_is_nothing_to_report(self):
        self.assertIn("nothing to report", " ".join(doctor.report([a_finding(ok=True)])))


class EntryTest(unittest.TestCase):
    def test_a_healthy_run_reports_success(self):
        self.assertEqual(
            doctor.main([], examine=lambda **_: [a_finding(ok=True)], say=lambda _: None), 0
        )

    def test_an_unhealthy_one_reports_failure(self):
        self.assertEqual(
            doctor.main([], examine=lambda **_: [a_finding(ok=False)], say=lambda _: None), 1
        )

    def test_the_report_is_printed_rather_than_kept(self):
        said = []

        doctor.main([], examine=lambda **_: [a_finding(ok=True)], say=said.append)

        self.assertTrue(said)

    def test_a_real_run_says_something_about_this_machine(self):
        said = []

        doctor.main([], say=said.append)

        self.assertIn("snesrtc", " ".join(said))


if __name__ == "__main__":
    unittest.main()
