"""Prepara el intercambio JSON para los Excel crudos de consumo."""

import argparse
import json
from pathlib import Path

from raw_sources.consumo import (
    CONSUMO_EXTERNO_COLUMNS,
    CONSUMO_INTERNO_COLUMNS,
    build_raw_consumo,
)
from synthetic_data.generator import GenerationConfig, generate_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260816)
    args = parser.parse_args()
    result = build_raw_consumo(generate_dataset(GenerationConfig(seed=args.seed)), args.seed)
    payload = {
        "seed": args.seed,
        "period": {"from": "2025-01-01", "to": "2025-12-31"},
        "coverage": {"vehicles": 238, "fleet": 250, "ratio": 0.952},
        "interno": {"columns": CONSUMO_INTERNO_COLUMNS, "rows": result["interno"]},
        "externo": {"columns": CONSUMO_EXTERNO_COLUMNS, "rows": result["externo"]},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
