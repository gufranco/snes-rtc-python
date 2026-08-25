import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesrtc import epson, models, sharp, store
from snesrtc.errors import UnknownModelError


class CatalogueTest(unittest.TestCase):
    def test_the_catalogue_covers_the_sharp_part(self) -> None:
        self.assertIn("s-rtc", models.MODELS)

    def test_and_the_epson_part_the_other_cartridges_carried(self) -> None:
        self.assertIn("rtc-4513", models.MODELS)

    def test_every_model_says_what_it_is_and_where_it_answers(self) -> None:
        for model in models.MODELS.values():
            self.assertTrue(model.summary.strip())
            self.assertTrue(model.addresses)

    def test_a_model_prints_as_something_a_person_can_read(self) -> None:
        self.assertIn("s-rtc", repr(models.describe("s-rtc")))


class NameTest(unittest.TestCase):
    def test_a_model_is_found_by_its_own_name(self) -> None:
        self.assertEqual(models.describe("s-rtc").name, "s-rtc")

    def test_case_does_not_matter(self) -> None:
        self.assertEqual(models.describe("S-RTC").name, "s-rtc")

    def test_neither_do_the_separators_people_write(self) -> None:
        self.assertEqual(models.describe("rtc4513").name, "rtc-4513")

    def test_an_alias_reaches_the_part_it_names(self) -> None:
        self.assertEqual(models.describe("sharp").name, "s-rtc")
        self.assertEqual(models.describe("spc7110").name, "rtc-4513")

    def test_a_name_no_part_answers_to_is_refused(self) -> None:
        with self.assertRaises(UnknownModelError):
            models.describe("ds1307")

    def test_and_the_refusal_lists_what_there_is(self) -> None:
        with self.assertRaises(UnknownModelError) as caught:
            models.describe("nothing")

        self.assertIn("s-rtc", str(caught.exception))


class BuildTest(unittest.TestCase):
    def test_the_sharp_model_builds_the_sharp_protocol(self) -> None:
        built = models.describe("s-rtc").build()

        self.assertIsInstance(built, sharp.Chip)

    def test_the_epson_model_builds_the_other_one(self) -> None:
        built = models.describe("rtc-4513").build()

        self.assertIsInstance(built, epson.Chip)

    def test_a_built_clock_gets_a_store_of_its_own_when_none_is_given(self) -> None:
        built = models.describe("s-rtc").build()

        self.assertIsInstance(built.store, store.Store)

    def test_and_uses_the_one_it_is_given_when_there_is_one(self) -> None:
        held = store.Store(cleared=True)

        built = models.describe("s-rtc").build(store=held)

        self.assertIs(built.store, held)

    def test_a_built_clock_can_be_handed_the_clock_it_reads(self) -> None:
        built = models.describe("rtc-4513").build(now=lambda: 42)

        self.assertEqual(built.now(), 42)

    def test_a_built_clock_knows_which_model_it_is(self) -> None:
        self.assertEqual(models.describe("s-rtc").build().model, "s-rtc")


if __name__ == "__main__":
    unittest.main()
