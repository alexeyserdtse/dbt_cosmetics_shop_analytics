# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

dbt project on DuckDB analyzing a cosmetics e-commerce clickstream (Kaggle: eCommerce Events History in Cosmetics Shop). The database is a local file `dev.duckdb`; `profiles.yml` lives in the project root and is picked up automatically — no `~/.dbt` setup needed.

## Commands

Activate the venv first — dbt is installed there (dbt-core 1.12, dbt-duckdb):

```bash
source .venv/bin/activate
dbt debug                                  # verify connection
dbt deps                                   # install packages (dbt_packages/ is gitignored)
dbt build                                  # seeds + models + tests in dependency order
dbt run --select <model_name>              # run a single model
dbt run --select +<model_name>             # model plus upstream dependencies
dbt test --select <model_name>             # test a single model
dbt build --select state:modified+         # only changed models + downstream (needs prior state)
```

Installed packages: dbt_utils, dbt_expectations, dbt_project_evaluator, codegen (use codegen macros to scaffold source/model YAML rather than writing it by hand).

## Raw data

`data/raw/*.csv` — five monthly event files (2019-Oct … 2020-Feb, ~2.3 GB total, gitignored; too big for dbt seeds). Columns: `event_time, event_type, product_id, category_id, category_code, brand, price, user_id, user_session`. `event_type` is one of view/cart/remove_from_cart/purchase. Load into DuckDB externally (e.g. `read_csv_auto` via a dbt-duckdb external source or a one-off load script), not via `dbt seed`.

## Architecture & conventions

Follows dbt Labs' recommended structure (see README.md for the full layout):

- `models/staging/<source>/` — 1:1 with source tables; rename/cast only, no joins; materialized as **views**. Only staging models use `{{ source(...) }}`; everything downstream uses `{{ ref(...) }}`.
- `models/intermediate/` — reusable joins/transformations; materialized as **ephemeral**.
- `models/marts/<domain>/` — business-facing dims/facts; materialized as **tables**.

Naming: `stg_<source>__<entity>.sql`, `int_<description>.sql`, `dim_<entity>.sql` / `fct_<event>.sql`. YAML doc files are prefixed with `_` (e.g. `_<source>__sources.yml`, `_<source>__models.yml`) so they sort to the top of each folder.

Layer materializations are set centrally in `dbt_project.yml` — don't repeat `+materialized` in individual model configs unless overriding.
