import re
import unittest

from raw_sources.flota import FLOTA_COLUMNS, build_raw_flota_rows
from synthetic_data.generator import GenerationConfig, generate_dataset


def normalize(value):
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


class RawFlotaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = generate_dataset(GenerationConfig())
        cls.rows = build_raw_flota_rows(cls.tables, seed=20260816)

    def test_raw_flota_has_expected_columns_and_no_internal_ids(self):
        self.assertEqual(len(self.rows), 250)
        self.assertEqual(list(self.rows[0]), FLOTA_COLUMNS)
        self.assertFalse(any(column == "id" or column.endswith("_id") for column in FLOTA_COLUMNS))

    def test_raw_flota_preserves_duplicate_problems_after_normalization(self):
        matriculas = [normalize(row["MATRICULA"]) for row in self.rows]
        dominios = [normalize(row["DOMINIO"]) for row in self.rows]
        self.assertEqual(len(matriculas) - len(set(matriculas)), 32)
        self.assertEqual(len(dominios) - len(set(dominios)), 32)

    def test_raw_flota_contains_source_specific_representation_variants(self):
        self.assertTrue(any(isinstance(row["MATRICULA"], int) for row in self.rows))
        self.assertTrue(any(" " in str(row["DOMINIO"]) for row in self.rows))
        self.assertGreater(len({str(row["IDENTIFICABLE"]) for row in self.rows}), 2)
        self.assertTrue(any(row["CAPACIDAD TANQUE"] in (None, "") for row in self.rows))


if __name__ == "__main__":
    unittest.main()
