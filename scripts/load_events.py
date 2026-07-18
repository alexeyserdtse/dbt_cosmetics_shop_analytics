"""Load raw Parquet files into the DuckDB landing schema (raw.events).

Modes:
  --file <name|earliest>   load a single monthly file (idempotent: the
                           file's month is deleted before re-insert)
  --mode history           load all monthly files in order

Every loaded row is stamped with ingestion_date (UTC datetime of the load
run), and every load attempt is recorded in raw.load_log.

Usage:
  python scripts/load_events.py --file earliest
  python scripts/load_events.py --mode history
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "dev.duckdb"
DATA_DIR = PROJECT_ROOT / "data" / "raw"

DDL = """
create schema if not exists raw;

create table if not exists raw.events (
    event_time     timestamp,
    event_type     varchar,
    product_id     bigint,
    category_id    bigint,
    category_code  varchar,
    brand          varchar,
    price          double,
    user_id        bigint,
    user_session   varchar,
    ingestion_date timestamp not null
);

create sequence if not exists raw.load_log_id_seq;

create table if not exists raw.load_log (
    load_id       bigint primary key default nextval('raw.load_log_id_seq'),
    source_file   varchar not null,
    month_start   date not null,
    started_at    timestamp not null,
    finished_at   timestamp,
    status        varchar not null default 'running',
    rows_deleted  bigint,
    rows_inserted bigint,
    error_message varchar
);
"""


def utc_now() -> datetime:
    """Naive UTC timestamp, matching DuckDB's plain TIMESTAMP columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class EventsLoader:
    """Loads monthly Parquet files into raw.events, one month per file."""

    def __init__(self, db_path: Path = DB_PATH, data_dir: Path = DATA_DIR) -> None:
        self.data_dir = data_dir
        self.con = duckdb.connect(str(db_path))
        self.con.execute("set preserve_insertion_order = false")
        self.con.execute("set memory_limit = '8GB'")
        self.con.execute(DDL)

    def parquet_files(self) -> list[Path]:
        """Monthly files sorted chronologically (filenames are %Y-%b)."""
        return sorted(
            self.data_dir.glob("*.parquet"), key=lambda p: self.month_start(p)
        )

    @staticmethod
    def month_start(path: Path) -> datetime:
        return datetime.strptime(path.stem, "%Y-%b")

    def load_file(self, path: Path) -> None:
        """Idempotently load one monthly file: replace that month's rows."""
        start = self.month_start(path)
        # Log row lives outside the data transaction so failures stay recorded.
        log_id = self.con.execute(
            "insert into raw.load_log (source_file, month_start, started_at)"
            " values (?, ?, ?) returning load_id",
            [path.name, start.date(), utc_now()],
        ).fetchone()[0]
        try:
            self.con.execute("begin")
            deleted = self.con.execute(
                "delete from raw.events where event_time >= ? and event_time < ? + interval 1 month",
                [start, start],
            ).fetchone()[0]
            inserted = self.con.execute(
                "insert into raw.events select *, ? as ingestion_date from read_parquet(?)",
                [utc_now(), str(path)],
            ).fetchone()[0]
            self.con.execute("commit")
        except duckdb.Error as exc:
            logger.error("load of %s failed: %s", path.name, exc)
            try:
                self.con.execute("rollback")
            except duckdb.Error as rollback_exc:
                logger.warning(
                    "rollback failed (usually no open transaction): %s", rollback_exc
                )
            self.con.execute(
                "update raw.load_log set status = 'failed', finished_at = ?,"
                " error_message = ? where load_id = ?",
                [utc_now(), str(exc), log_id],
            )
            raise
        self.con.execute(
            "update raw.load_log set status = 'success', finished_at = ?,"
            " rows_deleted = ?, rows_inserted = ? where load_id = ?",
            [utc_now(), deleted, inserted, log_id],
        )
        logger.info(
            "%s: replaced %d rows, inserted %d rows for %s",
            path.name,
            deleted,
            inserted,
            f"{start:%Y-%m}",
        )

    def load_history(self) -> None:
        for path in self.parquet_files():
            self.load_file(path)

    def resolve_file(self, name: str) -> Path:
        files = self.parquet_files()
        if not files:
            raise SystemExit(
                f"No Parquet files in {self.data_dir} — run csv_to_parquet.py first."
            )
        if name == "earliest":
            return files[0]
        match = self.data_dir / f"{name}.parquet"
        if match not in files:
            raise SystemExit(f"{match} not found; available: {[f.stem for f in files]}")
        return match


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="monthly file stem (e.g. 2019-Oct) or 'earliest'")
    group.add_argument(
        "--mode", choices=["history"], help="history: load all files in order"
    )
    args = parser.parse_args()

    loader = EventsLoader()
    if args.mode == "history":
        loader.load_history()
    else:
        loader.load_file(loader.resolve_file(args.file))


if __name__ == "__main__":
    main()
