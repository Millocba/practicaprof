"""Prepara el intercambio JSON sin IDs para construir el Excel crudo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from raw_sources.flota import FLOTA_COLUMNS, build_raw_flota_rows
from synthetic_data.generator import GenerationConfig, generate_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260816)
    args = parser.parse_args()
    tables = generate_dataset(GenerationConfig(seed=args.seed))
    payload = {"seed": args.seed, "columns": FLOTA_COLUMNS, "rows": build_raw_flota_rows(tables, args.seed)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
