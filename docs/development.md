# Development Guide

## Prerequisites

- Python 3.12 or newer
- Node.js 22
- Docker Desktop and Docker Compose
- Firebase CLI when deploying Firestore rules
- A Firebase project and web application
- A FRED API key

## Environment Files

Environment files are ignored by Git. Create them from the committed templates:

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Use the root `.env` for Docker Compose, `backend/.env` for native Python development, and `frontend/.env` for native Vite development.

Do not commit service-account JSON, encoded service accounts, database URLs, passwords, or provider tokens.

## Firebase Development Setup

1. Create a Firebase project.
2. Enable **Authentication > Sign-in method > Email/Password**.
3. Create Cloud Firestore in production mode.
4. Register a Firebase web application and copy its values into `frontend/.env` and the root `.env`.
5. Generate a service-account key from **Project settings > Service accounts**.

For native backend development:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/firebase-service-account.json"
```

For Docker, place a one-line base64 value in the root `.env`:

```bash
base64 < /absolute/path/firebase-service-account.json | tr -d '\n'
```

Deploy the deny-by-default Firestore rules:

```bash
firebase login
firebase use --add
firebase deploy --only firestore
```

## Docker Development

Configure all required values in the root `.env`, then run:

```bash
make docker-up
```

Docker starts:

- Nginx serving the built React application on port `8080`
- FastAPI on port `8000`
- TimescaleDB on the configured PostgreSQL port
- The recurring market-data worker

The Nginx container proxies `/api/` to the backend container, so the default frontend API URL remains `/api/v1`.

Stop services while retaining database data:

```bash
make docker-down
```

Only remove the `timescale_data` volume when intentionally deleting local market history.

## Native Development

Install all dependencies:

```bash
make install
```

Start TimescaleDB and apply migrations:

```bash
docker compose up -d timescaledb
make migrate
```

Start the API:

```bash
make backend
```

Start Vite in another terminal:

```bash
make frontend
```

Vite runs on `http://localhost:5173` and proxies `/api` to `http://localhost:8000`.

## Common Commands

| Command | Purpose |
| --- | --- |
| `make install` | Create the Python virtual environment and install frontend dependencies |
| `make backend` | Run FastAPI with reload |
| `make frontend` | Run the Vite development server |
| `make migrate` | Apply TimescaleDB migrations |
| `make sync-fred` | Synchronize configured FRED series |
| `make sync-bitcoin` | Synchronize Bitcoin daily prices |
| `make sync-all` | Synchronize all configured providers |
| `make lint` | Run Ruff and ESLint |
| `make test` | Run backend and frontend tests |
| `make coverage` | Produce Python XML and TypeScript LCOV reports |
| `make build` | Build the production frontend |
| `make quality` | Run lint, coverage, and build checks |

## Testing Strategy

- Backend tests cover route behavior, analytics, provider parsing, repositories, configuration, migrations, and CLI dispatch.
- Frontend tests cover API adapters, authentication, routing, page workflows, and form behavior.
- External systems are replaced by deterministic fakes or mocks in unit tests.
- CI runs migrations against an isolated TimescaleDB service.

Coverage floors:

| Project | Required |
| --- | --- |
| Backend | 90% combined branch-aware coverage |
| Frontend statements and lines | 90% |
| Frontend branches | 80% |
| Frontend functions | 85% |

## Code Organization

New backend behavior should preserve the existing boundary:

```text
route -> service -> repository -> external system
```

New frontend server state should use TanStack Query. Keep Firebase identity handling inside the authentication feature and API authorization inside the Axios client.

Before opening a pull request:

```bash
make quality
docker compose config
```

