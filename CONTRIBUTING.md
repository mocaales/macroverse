# Contributing

## Workflow

1. Create a focused branch from `main`.
2. Make the smallest coherent change.
3. Add or update tests for changed behavior.
4. Update documentation when configuration, architecture, API behavior, or operations change.
5. Run the local quality gate.
6. Open a pull request with the problem, approach, verification, and deployment impact.

```bash
make quality
docker compose config
```

## Pull Request Expectations

- CI and the SonarQube quality gate pass.
- Coverage does not fall below configured thresholds.
- No credentials or private data appear in code, tests, logs, fixtures, or screenshots.
- Database changes use a new migration.
- New environment variables are added to the appropriate `.env.example` files and documentation.
- Public API changes are reflected in `docs/api.md`.
- Architecture changes update `docs/architecture.md`.

## Engineering Conventions

### Backend

- Keep HTTP concerns in `app/api`.
- Keep calculations and provider workflows in `app/services`.
- Keep persistence behavior in `app/repositories`.
- Validate external inputs with Pydantic models.
- Use parameterized SQL and bounded database batches.

### Frontend

- Use TypeScript for application code.
- Use TanStack Query for server state.
- Keep authentication behavior in `features/auth`.
- Test user-visible behavior with Testing Library.
- Avoid importing real external SDK configuration in isolated unit tests.

## Commits

Use concise, imperative commit subjects. Keep formatting-only changes separate from behavior changes when practical.

## Documentation

Mermaid diagrams are preferred for architecture and workflows because GitHub renders them natively and they remain reviewable as text.

