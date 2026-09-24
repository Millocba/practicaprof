"""Prepara el intercambio JSON para el Excel crudo de telemetría."""

import argparse
import json
from pathlib import Path

from raw_sources.telemetria import TELEMETRIA_COLUMNS, build_raw_telemetria_rows
from synthetic_data.generator import GenerationConfig, generate_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260816)
    args = parser.parse_args()
    rows = build_raw_telemetria_rows(generate_dataset(GenerationConfig(seed=args.seed)), args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"seed": args.seed, "columns": TELEMETRIA_COLUMNS, "rows": rows}, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
