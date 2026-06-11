# Macroverse

Macroverse is a portfolio, trade-journal, and market-research application built with a React TypeScript frontend and a FastAPI backend.

Firebase provides:

- Firebase Authentication for email/password accounts
- Cloud Firestore for portfolio data
- Firebase Admin SDK identity verification in FastAPI

TimescaleDB provides:

- durable storage for FRED, Coin Metrics, and configured CryptoQuant time series
- efficient time-range queries for charts
- local development through Docker and production hosting through Tiger Cloud

## Architecture

```text
.
├── frontend/                  React, TypeScript, Vite, Firebase Web SDK
├── backend/
│   ├── app/
│   │   ├── api/               FastAPI routes and Firebase token verification
│   │   ├── core/              configuration, Firebase, and database connections
│   │   ├── models/            Pydantic API contracts
│   │   ├── repositories/      Firestore and TimescaleDB persistence
│   │   └── services/          analytics, provider clients, and data ingestion
│   ├── migrations/            TimescaleDB schema
│   ├── tests/
│   └── legacy_streamlit/      previous implementation, reference only
├── firestore.rules            denies direct client database access
├── .github/workflows/         CI, market sync, and container releases
└── docker-compose.yml         application, worker, and local TimescaleDB
```

The browser authenticates directly with Firebase Authentication. Before each protected API request, it retrieves a Firebase ID token. FastAPI verifies that token with Firebase Admin and uses the immutable Firebase `uid` to access the user's Firestore documents.

Market data is shared application data, not user data. The `market-sync` worker downloads it from providers and upserts it into TimescaleDB. Chart routes read the stored data first and retain a direct-provider fallback while the database is empty or unavailable.

## Firebase Setup

### 1. Create a Firebase project

1. Open https://console.firebase.google.com/.
2. Select **Add project**.
3. Complete the project creation flow.

### 2. Enable email/password authentication

1. Open **Build > Authentication**.
2. Select **Get started**.
3. Open **Sign-in method**.
4. Enable **Email/Password**.

### 3. Create Cloud Firestore

1. Open **Build > Firestore Database**.
2. Select **Create database**.
3. Choose **Production mode**.
4. Select the region closest to the application's users.

The repository's [firestore.rules](firestore.rules) denies all direct web-client reads and writes. All portfolio operations go through FastAPI and Firebase Admin IAM credentials.

Deploy the rules with the Firebase CLI:

```bash
npm install -g firebase-tools
firebase login
firebase use --add
firebase deploy --only firestore
```

### 4. Register the web application

1. Open **Project settings > General**.
2. Under **Your apps**, select the web icon.
3. Register the app.
4. Copy the Firebase configuration values into `.env` and `frontend/.env`.

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

Required frontend variables:

```dotenv
VITE_FIREBASE_API_KEY=
VITE_FIREBASE_AUTH_DOMAIN=
VITE_FIREBASE_PROJECT_ID=
VITE_FIREBASE_STORAGE_BUCKET=
VITE_FIREBASE_MESSAGING_SENDER_ID=
VITE_FIREBASE_APP_ID=
```

These web configuration values are public identifiers, not server credentials. Firestore authorization still depends on security rules and backend token verification.

### 5. Configure backend credentials

For local native development:

1. Open **Project settings > Service accounts**.
2. Select **Generate new private key**.
3. Store the downloaded JSON outside version control.
4. Set Application Default Credentials:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/firebase-service-account.json"
```

Then create the backend environment:

```bash
cp backend/.env.example backend/.env
```

Set:

```dotenv
FIREBASE_PROJECT_ID=your-firebase-project-id
```

For Docker Compose, encode the service-account file into one line:

```bash
base64 < /absolute/path/firebase-service-account.json | tr -d '\n'
```

Place the result in the root `.env`:

```dotenv
FIREBASE_SERVICE_ACCOUNT_BASE64=encoded-value
```

Never commit the service-account JSON or encoded credential.

## Firestore Data Model

```text
users/{firebaseUid}
├── email
├── favourites[]
├── accounts/{accountId}
├── trades/{tradeId}
└── investments/{investmentId}
```

Passwords and sessions are not stored in Firestore. Firebase Authentication stores credentials, and Firebase ID tokens provide the authenticated session.

## Market Database Setup

### Local setup with Docker

This is the simplest way to start. Docker creates PostgreSQL with the TimescaleDB extension, applies the migration, and starts the hourly ingestion worker.

1. Create local environment files:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
cp backend/.env.example backend/.env
```

2. Fill in the Firebase variables and `FRED_API_KEY`. Keep the default local database values.

3. Start the complete stack:

```bash
docker compose up --build
```

The first image download can take several minutes. The persistent `timescale_data` Docker volume retains market data after containers restart.

Useful checks:

```bash
docker compose ps
docker compose logs -f market-sync
curl http://localhost:8000/api/v1/health/market
```

To stop containers without deleting data:

```bash
docker compose down
```

Only use `docker compose down --volumes` when you intentionally want to delete the local market database.

### Production setup with Tiger Cloud

Tiger Cloud is the managed TimescaleDB option. It avoids operating database backups, upgrades, failover, and storage yourself.

1. Open [Tiger Cloud](https://console.cloud.timescale.com/) and create an account.
2. Select **Create service**.
3. Choose a PostgreSQL/Timescale service and a region close to the production backend.
4. Wait for the service to become ready.
5. Open the service and select **Connect**.
6. Copy the PostgreSQL connection string and store the generated password securely.

The connection string should resemble:

```dotenv
MARKET_DATABASE_URL=postgres://tsdbadmin:password@host:port/tsdb?sslmode=require
```

Do not commit this value. Add it to the production backend's secret environment variables.

Apply the schema and load the initial data:

```bash
cd backend
MARKET_DATABASE_URL='postgres://...' .venv/bin/python -m app.cli migrate
MARKET_DATABASE_URL='postgres://...' FRED_API_KEY='...' .venv/bin/python -m app.cli sync-all
```

For production, run the `market-sync` container continuously next to the backend. The scheduled GitHub workflow is also provided as a recovery mechanism, but GitHub scheduled jobs can be delayed and should not be the only scheduler for strict freshness requirements.

### GitHub Actions secrets

In GitHub, open **Settings > Secrets and variables > Actions > New repository secret** and add:

| Secret | Purpose |
| --- | --- |
| `MARKET_DATABASE_URL` | Tiger Cloud PostgreSQL URL with `sslmode=require` |
| `FRED_API_KEY` | FRED API key |
| `CRYPTOQUANT_ACCESS_TOKEN` | CryptoQuant API token, when used |
| `CRYPTOQUANT_SERIES_JSON` | JSON configuration for CryptoQuant series |

The workflow in `.github/workflows/market-sync.yml` runs hourly and can also be started from **Actions > Market data sync > Run workflow**.

The Firebase web configuration is public and should be stored as GitHub repository variables, not secrets. Open **Settings > Secrets and variables > Actions > Variables** and add:

- `VITE_FIREBASE_API_KEY`
- `VITE_FIREBASE_AUTH_DOMAIN`
- `VITE_FIREBASE_PROJECT_ID`
- `VITE_FIREBASE_STORAGE_BUCKET`
- `VITE_FIREBASE_MESSAGING_SENDER_ID`
- `VITE_FIREBASE_APP_ID`
- `VITE_API_URL` when the production API is hosted separately from the frontend

The release workflow injects these values when building the frontend container.

If a database IP allow list is enabled, standard GitHub-hosted runners do not have a stable outbound IP. Use a self-hosted runner or another scheduler with static egress instead of opening unrestricted database access.

### Provider configuration

Bitcoin prices use the free Coin Metrics Community API:

```dotenv
COINMETRICS_API_BASE_URL=https://community-api.coinmetrics.io/v4
```

No API key is required. Macroverse stores the daily `PriceUSD` reference-rate metric from January 1, 2011 onward.

FRED:

```dotenv
FRED_API_KEY=your-fred-api-key
```

CryptoQuant series are configured as a single-line JSON array. Use the exact endpoint and field names available in your CryptoQuant account:

```dotenv
CRYPTOQUANT_ACCESS_TOKEN=your-token
CRYPTOQUANT_SERIES_JSON=[{"series_id":"cryptoquant:btc:example:1d","endpoint":"your/endpoint","value_key":"your_value_field","name":"BTC Example Metric","unit":"BTC","window":"day"}]
```

Provider API plans and licences determine which data may be downloaded, retained, and redistributed. Verify those terms before exposing stored data publicly.

### Market data model

```text
market_series
├── series_id                 stable internal identifier
├── provider                  fred, coinmetrics, or cryptoquant
├── name, symbol, interval
├── unit and metadata
└── last_synced_at

market_observations           TimescaleDB hypertable
├── series_id + observed_at   primary key
├── value                     scalar metric
├── open, high, low, close
├── volume
└── ingested_at
```

Each synchronization overlaps the previous seven days and uses an upsert. This captures provider corrections without creating duplicate observations.

## Existing MongoDB Data

The application no longer reads MongoDB.

Existing portfolio data is not automatically copied into Firestore. Existing custom PBKDF2 users also do not automatically become Firebase Authentication users.

For a clean development environment, register new users through the application. For production migration:

1. Create or import each user in Firebase Authentication.
2. Build an email-to-Firebase-UID mapping.
3. Copy each MongoDB user's accounts, trades, investments, and favourites into `users/{uid}`.
4. Validate document counts and financial totals before switching production traffic.

Do not delete the MongoDB database until this reconciliation is complete.

## Run With Docker

After completing the root `.env`:

```bash
docker compose up --build
```

- Application: http://localhost:8080
- API documentation: http://localhost:8000/api/docs
- API health: http://localhost:8000/api/v1/health
- Market database health: http://localhost:8000/api/v1/health/market

Stop the stack with:

```bash
docker compose down
```

Firestore remains hosted by Firebase. Docker starts a local TimescaleDB container only for shared market time-series data.

## Native Development

Install dependencies:

```bash
make install
```

Run FastAPI:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/firebase-service-account.json"
make backend
```

Run React in another terminal:

```bash
make frontend
```

Vite runs at http://localhost:5173 and proxies `/api` to http://localhost:8000.

For native backend development, start only the local market database and apply its migration:

```bash
docker compose up -d timescaledb
make migrate
make sync-all
```

## Quality Checks

```bash
make lint
make test
docker compose config
docker compose build
```

GitHub Actions runs backend linting/tests, frontend linting/builds, and Docker image builds. Version tags publish frontend and backend images to GitHub Container Registry.

## API

Protected routes require:

```http
Authorization: Bearer <Firebase-ID-token>
```

| Area | Routes |
| --- | --- |
| Authentication verification | `/auth/me` |
| Accounts | `/portfolio/accounts` |
| Trades | `/portfolio/trades` |
| Investments | `/portfolio/assets` |
| Analytics | `/portfolio/dashboard/{account}`, `/portfolio/journal/{account}/summary` |
| Charts | `/charts`, `/charts/{slug}/series`, `/charts/favourites` |
| Health | `/health`, `/health/market` |

Use `/api/docs` as the authoritative request and response contract.
