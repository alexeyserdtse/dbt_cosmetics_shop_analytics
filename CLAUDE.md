# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

dbt project on DuckDB analyzing a cosmetics e-commerce clickstream (Kaggle dataset, see README). The database is a local file `dev.duckdb`; `profiles.yml` lives in the project root and is picked up automatically — no `~/.dbt` setup needed.

## Commands

Activate the venv first — dbt is installed there:

```bash
source .venv/bin/activate
dbt debug                                  # verify connection
dbt deps                                   # install packages (dbt_packages/ is gitignored)
dbt build                                  # models + tests in dependency order
dbt run --select <model_name>              # run a single model
dbt run --select +<model_name>             # model plus upstream dependencies
dbt test --select <model_name>             # test a single model
dbt build --select package:dbt_project_evaluator   # structure lint
sqlfluff lint models                       # SQL lint (same check CI runs)
```

## Data

Pipeline: Kaggle CSVs in `data/raw/` (gitignored, ~2.3 GB) → `python scripts/csv_to_parquet.py` (one shared inferred schema, snapshot in `data/raw/events.schema.json`) → `python scripts/load_events.py` (per-month idempotent replace into the `raw.events` landing table, UTC `ingestion_date`, every attempt audited in `raw.load_log`). The dbt source (`models/raw/_raw__sources.yml`) points at the physical `raw.events` table — no external_location. Never load this data with `dbt seed` and never commit it. Without a loaded `dev.duckdb`, models cannot build (CI therefore only runs `dbt parse`).

Known raw-data quirks (from profiling Oct 2019): ~5.2% exact duplicate rows (dedup belongs in stg), `category_code` ~98% null, `brand` ~40% null, ~20 negative prices on purchases (refunds — real data). Landing table stays constraint-free by design; enforce quality via dbt tests in stg.

Gotcha: DuckDB allows one writer — close DBeaver's connection to `dev.duckdb` before running the loader or `dbt run`/`dbt build`.

## Architecture

Three layers, **raw → stg → dwh** (this project deliberately does NOT use the dbt Labs staging/intermediate/marts names):

- `models/raw/` — source definitions over the `raw` landing schema plus thin `raw_<entity>.sql` views (`select * from source`) as the dbt-facing interface. The only layer that uses `{{ source(...) }}`. The physical `raw.events` table itself is owned by `scripts/load_events.py`, not dbt.
- `models/stg/` — 1:1 with raw; rename/cast, no joins; views. Naming `stg_<source>__<entity>.sql`. Selects from `{{ ref('raw_<entity>') }}`.
- `models/dwh/` — business-facing `dim_`/`fct_` models (tables) plus `int_` helpers (ephemeral, set `materialized='ephemeral'` in-file since the layer default is table).

Layer materializations and schemas are set centrally in `dbt_project.yml` (each layer lands in its own DuckDB schema — `raw`/`stg`/`dwh` — via `+schema` and the `generate_schema_name` macro override) — don't repeat `+materialized`/`+schema` in model configs unless overriding.

## Working rules

- Check dbt_utils / dbt_expectations for an existing test or macro before writing a custom one; scaffold source/model YAML with codegen macros rather than by hand.
- YAML doc files are prefixed with `_` (e.g. `_raw__sources.yml`, `_stg__models.yml`).
- Git: all git/GitHub operations go through the gitops agent; feature branch + PR always — `master` is protected (PR + green `dbt` CI check required, admins included). CI runs `dbt deps`, `dbt parse`, and sqlfluff on every PR.
