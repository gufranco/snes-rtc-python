import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snesrtc
from snesrtc import MODELS, Chip, Store, UnknownModelError

SHARP_DATA = 0x2800

EPSON_ENABLE = 0x4840


class CatalogueTest(unittest.TestCase):
    def test_the_catalogue_covers_the_sharp_part(self) -> None:
        # Arrange
        catalogue = MODELS

        # Act
        names = set(catalogue)

        # Assert
        self.assertIn("s-rtc", names)

    def test_and_the_epson_part_the_other_cartridges_carried(self) -> None:
        # Arrange
        catalogue = MODELS

        # Act
        names = set(catalogue)

        # Assert
        self.assertIn("rtc-4513", names)

    def test_every_model_says_what_it_is_and_where_it_answers(self) -> None:
        # Arrange
        models = MODELS.values()

        # Act
        bare = [model.name for model in models if not model.summary.strip() or not model.addresses]

        # Assert
        self.assertEqual(bare, [])

    def test_each_model_answers_at_the_addresses_the_readme_gives(self) -> None:
        # Arrange
        catalogue = MODELS

        # Act
        found = {name: model.addresses for name, model in catalogue.items()}

        # Assert
        self.assertEqual(found, {"s-rtc": (0x2800, 0x2801), "rtc-4513": (0x4840, 0x4841, 0x4842)})

    def test_a_model_prints_as_something_a_person_can_read(self) -> None:
        # Arrange
        model = MODELS["s-rtc"]

        # Act
        shown = repr(model)

        # Assert
        self.assertIn("s-rtc", shown)


class NameTest(unittest.TestCase):
    def test_a_model_is_found_by_its_own_name(self) -> None:
        # Arrange
        name = "s-rtc"

        # Act
        built = Chip(name)

        # Assert
        self.assertEqual(built.model, "s-rtc")

    def test_case_does_not_matter(self) -> None:
        # Arrange
        name = "S-RTC"

        # Act
        built = Chip(name)

        # Assert
        self.assertEqual(built.model, "s-rtc")

    def test_neither_do_the_separators_people_write(self) -> None:
        # Arrange
        name = "rtc4513"

        # Act
        built = Chip(name)

        # Assert
        self.assertEqual(built.model, "rtc-4513")

    def test_an_alias_reaches_the_part_it_names(self) -> None:
        # Arrange
        names = ("sharp", "spc7110")

        # Act
        built = [Chip(name).model for name in names]

        # Assert
        self.assertEqual(built, ["s-rtc", "rtc-4513"])

    def test_a_name_no_part_answers_to_is_refused(self) -> None:
        # Arrange
        name = "ds1307"

        # Act
        with self.assertRaises(UnknownModelError) as caught:
            Chip(name)

        # Assert
        self.assertIn("ds1307", str(caught.exception))

    def test_and_the_refusal_lists_what_there_is(self) -> None:
        # Arrange
        name = "nothing"

        # Act
        with self.assertRaises(UnknownModelError) as caught:
            Chip(name)

        # Assert
        self.assertIn("s-rtc", str(caught.exception))


class BuildTest(unittest.TestCase):
    def test_the_sharp_model_builds_the_sharp_protocol(self) -> None:
        # Arrange
        model = MODELS["s-rtc"]

        # Act
        built = model.build(Store(cleared=True), now=lambda: 0)

        # Assert
        self.assertEqual((built.read(SHARP_DATA), built.mode), (0x0F, "read"))

    def test_the_epson_model_builds_the_other_one(self) -> None:
        # Arrange
        model = MODELS["rtc-4513"]
        built: Any = model.build(Store(cleared=True), now=lambda: 0)

        # Act
        built.write(EPSON_ENABLE, 0x01)

        # Assert
        self.assertEqual((built.read(EPSON_ENABLE), built.state), (0x01, "mode"))

    def test_a_built_clock_gets_a_store_of_its_own_when_none_is_given(self) -> None:
        # Arrange
        model = MODELS["s-rtc"]

        # Act
        first, second = model.build(), model.build()

        # Assert
        self.assertIsInstance(first.store, Store)
        self.assertIsNot(first.store, second.store)

    def test_and_uses_the_one_it_is_given_when_there_is_one(self) -> None:
        # Arrange
        held = Store(cleared=True)

        # Act
        built = MODELS["s-rtc"].build(store=held)

        # Assert
        self.assertIs(built.store, held)

    def test_a_built_clock_can_be_handed_the_clock_it_reads(self) -> None:
        # Arrange
        model = MODELS["rtc-4513"]

        # Act
        built = model.build(now=lambda: 42)

        # Assert
        self.assertEqual(built.now(), 42)

    def test_a_built_clock_knows_which_model_it_is(self) -> None:
        # Arrange
        model = MODELS["s-rtc"]

        # Act
        built = model.build()

        # Assert
        self.assertEqual(built.model, "s-rtc")


class NamingNoneTest(unittest.TestCase):
    def test_building_without_naming_a_model_is_refused(self) -> None:
        # Arrange
        expected = UnknownModelError

        # Act
        with self.assertRaises(expected) as caught:
            Chip()

        # Assert
        self.assertIsInstance(caught.exception, UnknownModelError)

    def test_and_the_refusal_names_every_model_there_is(self) -> None:
        # Arrange
        names = list(MODELS)

        # Act
        with self.assertRaises(UnknownModelError) as caught:
            Chip()

        # Assert
        self.assertEqual([name for name in names if name not in str(caught.exception)], [])

    def test_nothing_named_describe_is_published(self) -> None:
        # Arrange
        package = snesrtc

        # Act
        found = hasattr(package, "describe")

        # Assert
        self.assertIs(found, False)

    def test_and_no_default_model_is_published_either(self) -> None:
        # Arrange
        package = snesrtc

        # Act
        found = hasattr(package, "DEFAULT_MODEL")

        # Assert
        self.assertIs(found, False)


if __name__ == "__main__":
    unittest.main()
