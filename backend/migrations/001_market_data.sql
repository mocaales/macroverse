CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS market_series (
    series_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    name TEXT NOT NULL,
    symbol TEXT,
    interval TEXT NOT NULL,
    unit TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS market_observations (
    series_id TEXT NOT NULL REFERENCES market_series(series_id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL,
    provider TEXT NOT NULL,
    value DOUBLE PRECISION,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (series_id, observed_at),
    CONSTRAINT market_observation_has_value CHECK (
        value IS NOT NULL OR close IS NOT NULL
    )
);

SELECT create_hypertable(
    'market_observations',
    by_range('observed_at'),
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS market_observations_series_time_desc_idx
    ON market_observations (series_id, observed_at DESC);

ALTER TABLE market_observations SET (
    timescaledb.enable_columnstore = true,
    timescaledb.segmentby = 'series_id',
    timescaledb.orderby = 'observed_at DESC'
);

CALL add_columnstore_policy(
    'market_observations',
    after => INTERVAL '30 days',
    if_not_exists => TRUE
);
