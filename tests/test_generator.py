import json
from pathlib import Path
import re
import tempfile
import unittest

from synthetic_data.generator import GenerationConfig, generate_dataset
from synthetic_data.cli import export_dataset


class GeneratorContractTests(unittest.TestCase):
    def test_generates_reproducible_related_tables(self):
        config = GenerationConfig(
            scenario="clean",
            seed=123,
            vehicles=20,
            devices=12,
            people=30,
            telemetry_events=100,
            fuel_transactions=50,
            months=2,
        )

        first = generate_dataset(config)
        second = generate_dataset(config)

        self.assertEqual(first, second)
        self.assertEqual(len(first["vehiculo"]), 20)
        self.assertEqual(len(first["dispositivo"]), 12)
        self.assertEqual(len(first["persona"]), 30)
        self.assertEqual(len(first["evento_telemetria"]), 100)
        self.assertEqual(len(first["transaccion_combustible"]), 50)
        self.assertTrue(all(row["matricula_sintetica"].startswith("VEH-SYN-") for row in first["vehiculo"]))

        vehicle_ids = {row["id"] for row in first["vehiculo"]}
        device_ids = {row["id"] for row in first["dispositivo"]}
        self.assertTrue(all(row["vehiculo_id"] in vehicle_ids for row in first["dispositivo"]))
        self.assertTrue(all(row["dispositivo_id"] in device_ids for row in first["evento_telemetria"]))

    def test_early_stage_injects_and_records_expected_duplicates(self):
        config = GenerationConfig(
            scenario="early_stage",
            seed=123,
            vehicles=100,
            devices=60,
            people=100,
            telemetry_events=200,
            fuel_transactions=100,
            months=2,
        )

        tables = generate_dataset(config)
        truth_types = [row["tipo"] for row in tables["ground_truth"]]

        self.assertEqual(truth_types.count("DQ_DUP_VEH_ID"), 32)
        self.assertEqual(truth_types.count("DQ_DUP_DOMAIN"), 32)
        matriculas = [row["matricula_sintetica"] for row in tables["vehiculo"]]
        dominios = [row["dominio_sintetico"] for row in tables["vehiculo"]]
        self.assertEqual(len(matriculas) - len(set(matriculas)), 32)
        self.assertEqual(len(dominios) - len(set(dominios)), 32)

    def test_export_writes_csv_manifest_and_refuses_overwrite(self):
        config = GenerationConfig(scenario="clean", seed=7, vehicles=10, devices=5, people=12, telemetry_events=20, fuel_transactions=15, months=1)
        tables = generate_dataset(config)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dataset"
            export_dataset(tables, config, output)

            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["scenario"], "clean")
            self.assertEqual(manifest["tables"]["vehiculo"]["rows"], 10)
            self.assertEqual(len(manifest["tables"]["vehiculo"]["sha256"]), 64)
            self.assertTrue((output / "vehiculo.csv").exists())
            with self.assertRaises(FileExistsError):
                export_dataset(tables, config, output)

    def test_vehicle_catalogs_and_argentine_domain_formats_are_plausible(self):
        config = GenerationConfig(scenario="clean", seed=9, vehicles=40, devices=20, people=40, telemetry_events=80, fuel_transactions=40, months=1)
        vehicles = generate_dataset(config)["vehiculo"]
        accepted = re.compile(r"^(?:[A-Z]{3}\d{3}|[A-Z]{2}\d{3}[A-Z]{2})$")
        public_brands = {"Toyota", "Ford", "Renault", "Fiat", "Volkswagen", "Chevrolet", "Iveco"}

        self.assertTrue(all(accepted.fullmatch(row["dominio_sintetico"]) for row in vehicles))
        self.assertTrue(all(row["marca_sintetica"] in public_brands for row in vehicles))
        self.assertTrue(all(not row["modelo_sintetico"].startswith("Modelo Sintético") for row in vehicles))

    def test_reducing_volume_preserves_existing_entity_ids(self):
        common = dict(scenario="clean", seed=11, devices=10, people=20, telemetry_events=30, fuel_transactions=20, months=1)
        small = generate_dataset(GenerationConfig(vehicles=20, **common))
        large = generate_dataset(GenerationConfig(vehicles=30, **common))

        self.assertEqual([row["id"] for row in small["vehiculo"]], [row["id"] for row in large["vehiculo"][:20]])
        self.assertEqual([row["vehiculo_id"] for row in small["dispositivo"]], [row["vehiculo_id"] for row in large["dispositivo"]])


if __name__ == "__main__":
    unittest.main()
