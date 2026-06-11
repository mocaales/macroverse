# Macroverse Documentation

This directory contains the authoritative technical and operational documentation for Macroverse. The root README is intentionally limited to project orientation and the shortest successful setup path.

## Documentation Map

| Document | Audience | Contents |
| --- | --- | --- |
| [Architecture](architecture.md) | Engineers and reviewers | System boundaries, components, data models, and runtime flows |
| [Development](development.md) | Contributors | Local setup, environment configuration, commands, tests, and conventions |
| [API reference](api.md) | Frontend and API consumers | Authentication, endpoints, response behavior, and examples |
| [Deployment](deployment.md) | Maintainers | Firebase, Tiger Cloud, Render, CI/CD, and container releases |
| [Operations](operations.md) | Operators | Migrations, ingestion, monitoring, backfills, and recovery |
| [Security](security.md) | Engineers and operators | Threat boundaries, secret handling, CORS, Firestore rules, and reviews |

## Documentation Principles

- Keep the root README concise and task-oriented.
- Put implementation details next to the subsystem they describe.
- Treat executable configuration and generated OpenAPI output as authoritative when documentation conflicts with code.
- Update diagrams and operational procedures in the same pull request as architecture or deployment changes.
- Never include real credentials, connection strings, tokens, user data, or private infrastructure details.

## Sources of Truth

| Concern | Authoritative source |
| --- | --- |
| API schema | Running `/api/docs` and FastAPI route models |
| Environment variables | `.env.example`, `backend/.env.example`, `frontend/.env.example` |
| CI behavior | `.github/workflows/*.yml` |
| Production services | `render.yaml` |
| Local containers | `docker-compose.yml` |
| Database schema | `backend/migrations/*.sql` |
| Quality thresholds | `backend/pyproject.toml` and `frontend/vite.config.ts` |

