import unittest

from raw_sources.telemetria import TELEMETRIA_COLUMNS, build_raw_telemetria_rows
from synthetic_data.generator import GenerationConfig, generate_dataset


class RawTelemetriaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = build_raw_telemetria_rows(generate_dataset(GenerationConfig()), seed=20260816)

    def test_has_one_row_per_device_without_internal_ids(self):
        self.assertEqual(len(self.rows), 180)
        self.assertEqual(list(self.rows[0]), TELEMETRIA_COLUMNS)
        self.assertFalse(any(column == "id" or column.endswith("_id") for column in TELEMETRIA_COLUMNS))

    def test_contains_expected_source_quality_problems(self):
        imeis = [str(row["IMEI"]) for row in self.rows]
        self.assertEqual(len(imeis) - len(set(imeis)), 6)
        self.assertEqual(sum(row["Alias"] == "SIN ASIGNAR" and not row["Placa"] for row in self.rows), 15)
        self.assertTrue(any("MOTOR" in row["Alias"] for row in self.rows))
        self.assertTrue(any("/" in str(row["Hora de última transmisión"]) for row in self.rows))


if __name__ == "__main__":
    unittest.main()
