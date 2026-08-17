import unittest
from datetime import date

from raw_sources.consumo import (
    CONSUMO_EXTERNO_COLUMNS,
    CONSUMO_INTERNO_COLUMNS,
    build_raw_consumo,
)
from synthetic_data.generator import GenerationConfig, generate_dataset


class RawConsumoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = generate_dataset(GenerationConfig(seed=20260816))
        cls.result = build_raw_consumo(cls.tables, seed=20260816)

    def test_sources_have_independent_contracts_without_internal_ids(self):
        internal = self.result["interno"]
        external = self.result["externo"]
        self.assertEqual(list(internal[0]), CONSUMO_INTERNO_COLUMNS)
        self.assertEqual(list(external[0]), CONSUMO_EXTERNO_COLUMNS)
        self.assertFalse(any(c == "id" or c.lower().endswith("_id") for c in internal[0]))
        self.assertFalse(any(c == "id" or c.lower().endswith("_id") for c in external[0]))
        self.assertEqual(len(internal), 4760)
        self.assertEqual(len(external), 4760)

    def test_truth_preserves_shared_events_and_at_least_95_percent_vehicle_coverage(self):
        truth = self.result["truth"]
        self.assertEqual(len(truth), len(self.result["interno"]))
        self.assertEqual(len({row["evento_id"] for row in truth}), len(truth))
        self.assertEqual(len({row["vehiculo_id"] for row in truth}), 238)
        self.assertGreaterEqual(238 / len(self.tables["vehiculo"]), 0.95)

    def test_consumption_is_daily_and_within_telemetry_period(self):
        truth = self.result["truth"]
        days = {date.fromisoformat(row["fecha"]) for row in truth}
        self.assertEqual(min(days), date(2025, 1, 1))
        self.assertEqual(max(days), date(2025, 12, 31))
        self.assertEqual(len(days), 365)

    def test_liters_respect_related_vehicle_tank_capacity(self):
        capacities = {row["id"]: float(row["capacidad_tanque_l"]) for row in self.tables["vehiculo"]}
        for row in self.result["truth"]:
            self.assertGreater(row["litros"], 0)
            self.assertLessEqual(row["litros"], capacities[row["vehiculo_id"]])

    def test_generation_is_reproducible_and_keeps_raw_keys_recoverable(self):
        repeated = build_raw_consumo(self.tables, seed=20260816)
        self.assertEqual(self.result, repeated)
        for row in self.result["interno"]:
            self.assertTrue(str(row["DOMINIO"]).strip() or str(row["MATRICULA"]).strip())


if __name__ == "__main__":
    unittest.main()
