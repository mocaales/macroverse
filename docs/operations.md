# Operations Guide

## Market Data Lifecycle

Market data can be synchronized by:

- The hourly GitHub Actions workflow
- A manual CLI command

Routine runs request a rolling seven-day provider window and upsert by `(series_id, observed_at)`. This captures provider corrections without duplicate observations.

## Migrations

Apply all pending migrations:

```bash
make migrate
```

Migrations are ordered SQL files in `backend/migrations`. Applied filenames are recorded in `schema_migrations`.

Never edit an already deployed migration. Add a new numbered migration.

## Synchronization

Routine synchronization:

```bash
make sync-all
```

Initial historical backfill:

```bash
cd backend
.venv/bin/python -m app.cli sync-all --full
```

The full option should be used only for initial loading or deliberate repair. In GitHub Actions, run **Market data sync** manually with **Load complete provider history** enabled.

Provider-specific commands:

```bash
make sync-fred
make sync-bitcoin
```

## Provider Configuration

Bitcoin uses the Coin Metrics Community API and requires no token:

```dotenv
COINMETRICS_API_BASE_URL=https://community-api.coinmetrics.io/v4
```

FRED requires:

```dotenv
FRED_API_KEY=
```

CryptoQuant configuration is optional:

```dotenv
CRYPTOQUANT_ACCESS_TOKEN=
CRYPTOQUANT_SERIES_JSON=[{"series_id":"cryptoquant:btc:example:1d","endpoint":"your/endpoint","value_key":"your_value_field","name":"Example","unit":"BTC","window":"day"}]
```

Verify provider licensing before retaining or redistributing third-party data.

## Health and Monitoring

| Check | Expected result |
| --- | --- |
| `GET /api/v1/health` | `status: ok` |
| `GET /api/v1/health/market` | `status: ok` |
| Render API service | Healthy |
| GitHub `Market data sync` | Latest run successful |
| SonarQube quality gate | Passed |

Local container status:

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f timescaledb
```

## Data Verification

Series coverage:

```sql
SELECT
    s.series_id,
    s.provider,
    COUNT(o.*) AS observations,
    MIN(o.observed_at) AS earliest,
    MAX(o.observed_at) AS latest
FROM market_series s
LEFT JOIN market_observations o USING (series_id)
GROUP BY s.series_id, s.provider
ORDER BY s.provider, s.series_id;
```

Latest values:

```sql
SELECT series_id, observed_at, value, close
FROM market_observations
ORDER BY observed_at DESC
LIMIT 100;
```

## Failure Handling

### Provider failure

1. Check the GitHub Actions workflow log or manual CLI output for the provider name.
2. Confirm credentials and plan access.
3. Verify provider availability and endpoint changes.
4. Rerun routine synchronization.
5. Use a full backfill only when the historical range is incomplete.

### Database connection failure

1. Check `/api/v1/health/market`.
2. Verify `MARKET_DATABASE_URL` and TLS requirements.
3. Check service status and connection limits in Tiger Cloud.
4. Confirm network allow-list rules.
5. Rerun migrations after connectivity is restored.

### Partial ingestion

Writes are committed in small batches. A failed run can be restarted safely because inserts are idempotent upserts.

## Backup and Recovery

- Use Tiger Cloud backup and point-in-time recovery capabilities for market data.
- Use Firebase/Google Cloud export procedures for Firestore production data.
- Retain infrastructure configuration and migrations in Git.
- Test recovery procedures before relying on them for production incidents.

Local Docker volumes are not a production backup.
