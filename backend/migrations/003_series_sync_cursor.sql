ALTER TABLE market_series
ADD COLUMN IF NOT EXISTS latest_observed_at TIMESTAMPTZ;

-- Existing successful sync timestamps are a safe incremental cursor because
-- ingestion overlaps seven days on every subsequent run.
UPDATE market_series
SET latest_observed_at = last_synced_at
WHERE latest_observed_at IS NULL
  AND last_synced_at IS NOT NULL;
