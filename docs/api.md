# API Reference

The FastAPI application is served under `/api/v1`. Interactive OpenAPI documentation is available at `/api/docs`.

## Authentication

Protected endpoints require a Firebase ID token:

```http
Authorization: Bearer <firebase-id-token>
```

The backend verifies the signature, expiration, and revocation state with Firebase Admin. Missing, invalid, expired, or revoked tokens return `401`. A valid token without an email claim returns `403`.

The response from `/auth/me` includes a server-derived `role` of `admin` or `user`. The configured `ADMIN_EMAIL` is the only identity assigned the administrator role; all other Firebase accounts are normal users.

## Endpoints

| Method | Path | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | No | API process health |
| `GET` | `/health/market` | No | TimescaleDB connectivity |
| `GET` | `/auth/me` | Yes | Return verified identity |
| `GET` | `/admin/users` | Admin | List registered Firebase users |
| `DELETE` | `/admin/users/{uid}` | Admin | Delete a Firebase user and private Firestore data |
| `GET` | `/portfolio/accounts` | Yes | List accounts |
| `POST` | `/portfolio/accounts` | Yes | Create or update an account by name |
| `DELETE` | `/portfolio/accounts/{account_name}` | Yes | Delete an account and its related portfolio records |
| `GET` | `/portfolio/trades` | Yes | List trades, optionally filtered by account |
| `POST` | `/portfolio/trades` | Yes | Create a trade, deposit, or withdrawal |
| `PUT` | `/portfolio/trades/{trade_id}` | Yes | Update a ledger entry |
| `DELETE` | `/portfolio/trades/{trade_id}` | Yes | Delete a ledger entry |
| `GET` | `/portfolio/recurring-transactions` | Yes | List recurring bank transactions |
| `POST` | `/portfolio/recurring-transactions` | Yes | Create recurring bank automation |
| `PUT` | `/portfolio/recurring-transactions/{id}` | Yes | Edit recurring bank automation |
| `DELETE` | `/portfolio/recurring-transactions/{id}` | Yes | Delete recurring bank automation |
| `GET` | `/portfolio/dashboard` | Yes | Return the aggregate dashboard and live per-account balances for one currency |
| `GET` | `/portfolio/dashboard/{account}` | Yes | Return account performance summary |
| `GET` | `/portfolio/journal/{account}/summary` | Yes | Return journal summary |
| `GET` | `/charts` | No | List chart definitions |
| `GET` | `/charts/{slug}/series` | No | Return chart time series |
| `GET` | `/charts/favourites` | Yes | List user favourites |
| `POST` | `/charts/favourites/{chart_name}` | Yes | Toggle a favourite |

## Examples

### Health

```bash
curl http://localhost:8000/api/v1/health
```

### List accounts

```bash
curl \
  -H "Authorization: Bearer ${FIREBASE_ID_TOKEN}" \
  http://localhost:8000/api/v1/portfolio/accounts
```

### List registered users

```bash
curl \
  -H "Authorization: Bearer ${FIREBASE_ID_TOKEN}" \
  http://localhost:8000/api/v1/admin/users
```

The token must belong to the configured administrator. The administrator account is included in the response but cannot be deleted.

### Create an account

```bash
curl -X POST \
  -H "Authorization: Bearer ${FIREBASE_ID_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"name":"Primary","starting_balance":10000,"type":"Trading Account","currency":"EUR"}' \
  http://localhost:8000/api/v1/portfolio/accounts
```

### Record a trade

```bash
curl -X POST \
  -H "Authorization: Bearer ${FIREBASE_ID_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "account":"Primary",
    "trade_time":"2026-06-12",
    "action":"Trade",
    "type":"Long",
    "symbol":"BTCUSD",
    "pnl":250,
    "notes":"Breakout"
  }' \
  http://localhost:8000/api/v1/portfolio/trades
```

Savings and bank accounts reject trade actions. Their deposits and withdrawals require a description; bank transactions additionally require a category. Trading accounts preserve the existing trade, deposit, and withdrawal workflow.

### Create a recurring bank transaction

```bash
curl -X POST \
  -H "Authorization: Bearer ${FIREBASE_ID_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "account":"Primary bank",
    "action":"Deposit",
    "amount":100,
    "description":"Monthly salary allocation",
    "category":"Salary",
    "day_of_month":1,
    "start_date":"2026-07-01"
  }' \
  http://localhost:8000/api/v1/portfolio/recurring-transactions
```

Due occurrences are materialized immediately when automation is created and whenever portfolio data is requested afterward. Each generated transaction uses a deterministic monthly identifier, so concurrent refreshes cannot create duplicate ledger entries.

Editing an automation preserves its identifier and changes the rules used for subsequent synchronization. Deleting an automation stops future occurrences; transactions already materialized in the ledger remain as historical records.

Account balances are derived from the persisted starting balance and Firestore ledger entries. The aggregate dashboard returns these live balances for the Portfolio account list; it does not rely on a separately stored balance field that could become stale.

### Read a chart series

```bash
curl http://localhost:8000/api/v1/charts/year_to_date_roi/series
```

Chart endpoints read exclusively from TimescaleDB. Provider APIs are used only by synchronization jobs; normal browser requests never call FRED, Coin Metrics, or CryptoQuant directly. An unavailable database returns `503`, while a known chart without stored observations returns `404`.

## Error Format

FastAPI errors use the standard detail object:

```json
{
  "detail": "Trade not found."
}
```

Client applications should handle `401` by clearing the Firebase session and prompting the user to sign in again. Admin endpoints return `403` for normal users, `400` for an attempt to delete the administrator account, and `404` when the requested user no longer exists.
