"""CLI y exportación atómica del dataset sintético."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import csv
import hashlib
import json
from pathlib import Path
import shutil

from .generator import GenerationConfig, generate_dataset


def export_dataset(tables: dict[str, list[dict]], config: GenerationConfig, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"El destino ya existe: {output_dir}")
    temp_dir = output_dir.with_name(f".{output_dir.name}.tmp")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)
    manifest = {"scenario": config.scenario, "seed": config.seed, "config": asdict(config), "tables": {}}
    try:
        for table_name, rows in tables.items():
            path = temp_dir / f"{table_name}.csv"
            if rows:
                with path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), extrasaction="raise")
                    writer.writeheader()
                    writer.writerows(rows)
            else:
                path.write_text("", encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest["tables"][table_name] = {"file": path.name, "rows": len(rows), "sha256": digest}
        (temp_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp_dir.replace(output_dir)
    except Exception:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        raise
    return output_dir


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Genera un dataset exclusivamente sintético.")
    parser.add_argument("--scenario", default="early_stage")
    parser.add_argument("--seed", type=int, default=20260816)
    parser.add_argument("--vehicles", type=int, default=250)
    parser.add_argument("--devices", type=int, default=180)
    parser.add_argument("--people", type=int, default=500)
    parser.add_argument("--telemetry-events", type=int, default=20_000)
    parser.add_argument("--fuel-transactions", type=int, default=5_000)
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--output", type=Path, default=Path("datasets/early_stage"))
    return parser


def main() -> None:
    args = _parser().parse_args()
    config = GenerationConfig(scenario=args.scenario, seed=args.seed, vehicles=args.vehicles, devices=args.devices, people=args.people, telemetry_events=args.telemetry_events, fuel_transactions=args.fuel_transactions, months=args.months)
    output = export_dataset(generate_dataset(config), config, args.output)
    print(f"Dataset sintético generado en {output}")


if __name__ == "__main__":
    main()
