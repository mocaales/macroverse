# Architecture

## Architectural Goals

Macroverse separates interactive portfolio workflows from shared market-data ingestion:

- The browser owns presentation and Firebase sign-in.
- FastAPI owns authorization, validation, analytics, and persistence orchestration.
- Firestore stores private, user-scoped application data.
- TimescaleDB stores shared market observations optimized for time-range queries.
- Provider ingestion runs outside request handling so external latency does not block normal application traffic.

## System Context

```mermaid
flowchart TB
    Person[Portfolio user]
    Web[Macroverse web application]
    API[Macroverse API]
    Auth[Firebase Authentication]
    UserDB[(Cloud Firestore)]
    MarketDB[(TimescaleDB)]
    Sync[Market sync process]
    FRED[FRED]
    CoinMetrics[Coin Metrics]
    CryptoQuant[CryptoQuant]

    Person --> Web
    Web --> Auth
    Web --> API
    API --> Auth
    API --> UserDB
    API --> MarketDB
    Sync --> FRED
    Sync --> CoinMetrics
    Sync --> CryptoQuant
    Sync --> MarketDB
```

## Container View

```mermaid
flowchart LR
    subgraph Browser
        React[React application]
        Query[TanStack Query]
        FirebaseSDK[Firebase Web SDK]
        React --> Query
        React --> FirebaseSDK
    end

    subgraph Backend
        Routes[FastAPI routes]
        Services[Analytics and sync services]
        Repositories[Repository layer]
        Admin[Firebase Admin SDK]
        Routes --> Services
        Routes --> Repositories
        Routes --> Admin
    end

    Query -->|HTTPS + bearer token| Routes
    FirebaseSDK --> FirebaseAuth[Firebase Authentication]
    Admin --> FirebaseAuth
    Repositories --> Firestore[(Firestore)]
    Repositories --> Timescale[(TimescaleDB)]
    Worker[Python market worker] --> Services
    Services --> Providers[Market-data providers]
```

Backend packages follow a layered dependency direction:

```text
api -> services -> repositories -> infrastructure
 |         |             |
 models <-+-------------+
```

Routes translate HTTP requests into domain operations. Services contain calculations and provider synchronization. Repositories isolate Firestore and PostgreSQL behavior. Core modules construct external clients from environment configuration.

## Authenticated Request Sequence

```mermaid
sequenceDiagram
    actor User
    participant Web as React
    participant FA as Firebase Auth
    participant API as FastAPI
    participant Admin as Firebase Admin
    participant FS as Firestore

    User->>Web: Open portfolio
    Web->>FA: Sign in with email and password
    FA-->>Web: Firebase session
    Web->>FA: Request ID token
    FA-->>Web: Signed ID token
    Web->>API: GET /portfolio/accounts<br/>Authorization: Bearer token
    API->>Admin: Verify ID token
    Admin-->>API: uid and email
    API->>FS: Read users/{uid}/accounts
    FS-->>API: User-scoped documents
    API-->>Web: Validated JSON response
```

The immutable Firebase `uid`, not an email supplied by the browser, determines the Firestore document path.

## Portfolio Activity

```mermaid
flowchart TD
    Start([Authenticated user]) --> Select{Account exists?}
    Select -- No --> Create[Create account]
    Create --> Workspace
    Select -- Yes --> Workspace[Open account workspace]
    Workspace --> Type{Account type}
    Type -- Trading / Banking --> Entry[Record trade, deposit, or withdrawal]
    Entry --> Normalize[Normalize symbol and cash sign]
    Normalize --> StoreTrade[Store ledger entry in Firestore]
    StoreTrade --> Analytics[Recalculate balance and performance]
    Type -- Investing --> Asset[Add or remove holding]
    Asset --> StoreAsset[Store investment in Firestore]
    Type -- Overall --> Aggregate[Display account overview]
    Analytics --> End([Updated dashboard])
    StoreAsset --> End
    Aggregate --> End
```

## Market Synchronization Activity

```mermaid
flowchart TD
    Trigger([Worker interval or GitHub schedule]) --> Migrate[Apply pending migrations]
    Migrate --> Mode{Full backfill?}
    Mode -- Yes --> StartFull[Request complete provider history]
    Mode -- No --> StartRecent[Request rolling 7-day window]
    StartFull --> Fetch
    StartRecent --> Fetch[Fetch configured provider series]
    Fetch --> Normalize[Normalize timestamps and numeric values]
    Normalize --> Metadata[Upsert series metadata]
    Metadata --> Batch[Write observations in small batches]
    Batch --> Conflict{Existing timestamp?}
    Conflict -- Yes --> Correct[Update provider correction]
    Conflict -- No --> Insert[Insert observation]
    Correct --> Cursor[Update latest observation and sync time]
    Insert --> Cursor
    Cursor --> Next{More series?}
    Next -- Yes --> Fetch
    Next -- No --> Complete([Sync complete])
```

## Data Model

### Firestore

```mermaid
erDiagram
    USER ||--o{ ACCOUNT : owns
    USER ||--o{ TRADE : records
    USER ||--o{ INVESTMENT : holds

    USER {
        string uid PK
        string email
        string favourites
        timestamp updated_at
    }
    ACCOUNT {
        string name
        string type
        number starting_balance
        timestamp created_at
    }
    TRADE {
        string id PK
        string account
        timestamp trade_time
        string action
        string type
        string symbol
        number pnl
        string notes
    }
    INVESTMENT {
        string id PK
        string account
        string symbol
        number quantity
        string unit
        number display_quantity
    }
```

All documents are nested under `users/{firebaseUid}`. Firestore client rules deny direct browser access; the backend uses Firebase Admin IAM.

### TimescaleDB

```mermaid
erDiagram
    MARKET_SERIES ||--o{ MARKET_OBSERVATION : contains

    MARKET_SERIES {
        string series_id PK
        string provider
        string name
        string symbol
        string interval
        string unit
        json metadata
        timestamp last_synced_at
        timestamp latest_observed_at
    }
    MARKET_OBSERVATION {
        string series_id PK
        timestamp observed_at PK
        string provider
        float value
        float open
        float high
        float low
        float close
        float volume
        timestamp ingested_at
    }
```

`market_observations` is a TimescaleDB hypertable keyed by series and observation time.

## Key Decisions

| Decision | Rationale |
| --- | --- |
| Firebase Auth with backend token verification | Managed identity without trusting browser-provided user identifiers |
| Firestore for portfolio documents | Natural user-scoped document model and low operational overhead |
| TimescaleDB for market observations | Efficient time-series storage, range queries, and PostgreSQL compatibility |
| Repository boundary | Keeps route and service code independent of persistence SDK details |
| Rolling seven-day ingestion | Captures late provider corrections while avoiding expensive full-history reads |
| Provider fallback in chart routes | Keeps selected charts usable while a database is initially empty or temporarily unavailable |
