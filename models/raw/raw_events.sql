-- dbt-facing view over the physical landing table raw.events
-- (loaded by scripts/load_events.py).
select *
from {{ source('raw', 'events') }}
