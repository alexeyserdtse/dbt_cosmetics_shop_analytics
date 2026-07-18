"""Convert raw CSV datasets to Parquet with one shared, inferred schema.

The schema is inferred by DuckDB across ALL files of a dataset (not per
file), so every Parquet file lands with identical column types even when
a single month would sniff differently. The inferred schema is also
written next to the Parquet files as <dataset>.schema.json — a derivable
artifact that stays with the data (gitignored); the committed contract
lives in models/raw/_raw__sources.yml.

Usage: python scripts/csv_to_parquet.py [--overwrite]
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Dataset:
    """A group of CSV files sharing one schema, converted side by side."""

    name: str
    directory: Path
    pattern: str = "*.csv"

    def csv_files(self) -> list[Path]:
        return sorted(self.directory.glob(self.pattern))

    @property
    def glob_expression(self) -> str:
        return str(self.directory / self.pattern)

    @property
    def schema_path(self) -> Path:
        return self.directory / f"{self.name}.schema.json"


class CsvToParquetConverter:
    """Converts every CSV of a dataset to Parquet using one shared schema."""

    def __init__(self, dataset: Dataset, overwrite: bool = False) -> None:
        self.dataset = dataset
        self.overwrite = overwrite
        self.con = duckdb.connect()  # in-memory; files are read/written in place

    def run(self) -> None:
        csv_files = self.dataset.csv_files()
        if not csv_files:
            raise SystemExit(
                f"No files matching {self.dataset.glob_expression} — "
                "download the dataset first (see README)."
            )
        schema = self.infer_schema()
        self.write_schema_file(schema)
        for csv_path in csv_files:
            self.convert_file(csv_path, schema)

    def infer_schema(self) -> dict[str, str]:
        """Infer one schema across all files of the dataset."""
        rows = self.con.execute(
            "describe select * from read_csv_auto(?)", [self.dataset.glob_expression]
        ).fetchall()
        return {name: column_type for name, column_type, *_ in rows}

    def write_schema_file(self, schema: dict[str, str]) -> None:
        self.dataset.schema_path.write_text(json.dumps(schema, indent=2) + "\n")
        logger.info("schema %s", self.dataset.schema_path.relative_to(PROJECT_ROOT))

    def convert_file(self, csv_path: Path, schema: dict[str, str]) -> None:
        parquet_path = csv_path.with_suffix(".parquet")
        if parquet_path.exists() and not self.overwrite:
            logger.info("skip   %s (already exists)", parquet_path.name)
            return
        columns = ", ".join(f"'{name}': '{ctype}'" for name, ctype in schema.items())
        self.con.execute(
            f"""
            copy (
                select * from read_csv('{csv_path}', header = true, columns = {{{columns}}})
            ) to '{parquet_path}' (format parquet)
            """
        )
        logger.info("wrote  %s", parquet_path.name)


DATASETS = [
    Dataset(name="events", directory=PROJECT_ROOT / "data" / "raw"),
]


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="re-convert files that already have Parquet",
    )
    args = parser.parse_args()
    for dataset in DATASETS:
        CsvToParquetConverter(dataset, overwrite=args.overwrite).run()


if __name__ == "__main__":
    main()
