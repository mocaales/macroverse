# API Reference

The FastAPI application is served under `/api/v1`. Interactive OpenAPI documentation is available at `/api/docs`.

## Authentication

Protected endpoints require a Firebase ID token:

```http
Authorization: Bearer <firebase-id-token>
```

The backend verifies the signature and expiration with Firebase Admin. Missing, invalid, or expired tokens return `401`. A valid token without an email claim returns `403`.

## Endpoints

| Method | Path | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | No | API process health |
| `GET` | `/health/market` | No | TimescaleDB connectivity |
| `GET` | `/auth/me` | Yes | Return verified identity |
| `GET` | `/portfolio/accounts` | Yes | List accounts |
| `POST` | `/portfolio/accounts` | Yes | Create or update an account by name |
| `GET` | `/portfolio/trades` | Yes | List trades, optionally filtered by account |
| `POST` | `/portfolio/trades` | Yes | Create a trade, deposit, or withdrawal |
| `PUT` | `/portfolio/trades/{trade_id}` | Yes | Update a ledger entry |
| `DELETE` | `/portfolio/trades/{trade_id}` | Yes | Delete a ledger entry |
| `GET` | `/portfolio/assets` | Yes | List investments, optionally filtered by account |
| `POST` | `/portfolio/assets` | Yes | Create an investment holding |
| `DELETE` | `/portfolio/assets/{asset_id}` | Yes | Delete an investment holding |
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

### Create an account

```bash
curl -X POST \
  -H "Authorization: Bearer ${FIREBASE_ID_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"name":"Primary","starting_balance":10000,"type":"Trading"}' \
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

For deposits and withdrawals, the backend normalizes the symbol to `CASH`, removes direction, and applies the appropriate P&L sign.

### Read a chart series

```bash
curl http://localhost:8000/api/v1/charts/year_to_date_roi/series
```

## Error Format

FastAPI errors use the standard detail object:

```json
{
  "detail": "Trade not found."
}
```

Client applications should handle `401` by clearing the Firebase session and prompting the user to sign in again.

