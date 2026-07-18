# cosmetics_shop_analytics

Analytics for a cosmetics e-commerce clickstream ([Kaggle: eCommerce Events History in Cosmetics Shop](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop)) — a dbt project on DuckDB.

## Data

The dataset is not in the repo (~2.3 GB). Download it from Kaggle and place the five
monthly CSVs (`2019-Oct.csv` … `2020-Feb.csv`) in `data/raw/`, then convert them once
to Parquet:

```bash
python scripts/csv_to_parquet.py
```

Then load the landing table (`raw.events` in `dev.duckdb`, stamped with a UTC
`ingestion_date`, every attempt audited in `raw.load_log`):

```bash
python scripts/load_events.py --mode history      # all months
python scripts/load_events.py --file 2019-Oct     # or one month, idempotent
```

Columns: `event_time, event_type, product_id, category_id, category_code,
brand, price, user_id, user_session`.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
dbt deps           # install dbt packages
dbt debug          # check connection
dbt build          # models + tests in dependency order
```

The DuckDB database is a local file (`dev.duckdb`), configured in `profiles.yml`
(kept in the project directory, picked up automatically by dbt).

## Packages

| Package | Why it's here |
|---|---|
| dbt_utils | generic tests and macros (surrogate keys, date spine) |
| dbt_expectations | data-quality tests beyond dbt's built-ins |
| dbt_project_evaluator | lints the DAG against modeling best practices |
| codegen | scaffolds source/model YAML instead of hand-writing it |

## Structure

```
models/
├── raw/                # source defs + views over the raw.* landing tables
│   ├── _raw__sources.yml
│   └── raw_<entity>.sql
├── stg/                # 1:1 with raw sources — rename, cast, no joins (views)
│   └── stg_<source>__<entity>.sql
└── dwh/                # business-facing dims/facts (tables) + int_ helpers (ephemeral)
    ├── dim_<entity>.sql
    ├── fct_<event>.sql
    └── int_<description>.sql
scripts/                # data utilities (CSV → Parquet, Parquet → raw.events loader)
seeds/                  # small static CSVs loaded by `dbt seed`
tests/                  # singular data tests
macros/                 # reusable Jinja macros
snapshots/              # SCD type-2 snapshots
analyses/               # ad-hoc analytical SQL (compiled, not run)
```

## Conventions

- Layers: **raw → stg → dwh**. `raw` lands the external files as views; it is
  the only layer that selects from `{{ source(...) }}` — everything downstream
  uses `{{ ref(...) }}`.
- Naming: `raw_<entity>`, `stg_<source>__<entity>`, `dim_`/`fct_` for warehouse
  models, `int_` for ephemeral helpers inside `dwh`.
- Materializations are set per layer in `dbt_project.yml` (raw = view,
  stg = view, dwh = table); `int_` models override to ephemeral in-file.
- Each layer lands in its own DuckDB schema (`raw`/`stg`/`dwh`), via `+schema`
  plus a `generate_schema_name` override.
- YAML files are prefixed with `_` so they sort to the top of each folder.
- CI runs `dbt parse` and sqlfluff on every PR; `master` is protected and only
  merges through green PRs.
