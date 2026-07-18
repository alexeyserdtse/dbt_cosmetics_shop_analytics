# cosmetics_shop_analytics

Analytics for a cosmetics e-commerce clickstream ([Kaggle: eCommerce Events History in Cosmetics Shop](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop)) — a dbt project on DuckDB following [dbt Labs' recommended project structure](https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview).

## Setup

```bash
source .venv/bin/activate
dbt debug          # check connection
dbt build          # seeds + models + tests in dependency order
```

The DuckDB database is a local file (`dev.duckdb`), configured in `profiles.yml`
(kept in the project directory, picked up automatically by dbt).

## Structure

```
models/
├── staging/            # 1:1 with source tables — rename, cast, no joins
│   └── <source>/       # one folder per source system, e.g. models/staging/stripe/
│       ├── _<source>__sources.yml   # source definitions
│       ├── _<source>__models.yml    # model docs + tests
│       └── stg_<source>__<entity>.sql
├── intermediate/       # reusable joins/transformations (ephemeral)
│   └── int_<description>.sql
└── marts/              # business-facing dims/facts (tables)
    └── <domain>/       # e.g. marts/finance/, marts/marketing/
        ├── dim_<entity>.sql
        └── fct_<event>.sql
seeds/                  # small static CSVs loaded by `dbt seed`
tests/                  # singular data tests
macros/                 # reusable Jinja macros
snapshots/              # SCD type-2 snapshots
analyses/               # ad-hoc analytical SQL (compiled, not run)
```

## Conventions

- Staging models: `stg_<source>__<entity>.sql`, materialized as views.
- Intermediate models: `int_<description>.sql`, materialized as ephemeral.
- Marts: `dim_`/`fct_` prefixes, materialized as tables.
- YAML files are prefixed with `_` so they sort to the top of each folder.
- Only staging models select from `{{ source(...) }}`; everything downstream
  uses `{{ ref(...) }}`.
