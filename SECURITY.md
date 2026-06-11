# Security Policy

## Reporting a Vulnerability

Do not report security vulnerabilities through a public issue.

Use GitHub's private vulnerability reporting or open a private security advisory for this repository. Include:

- Affected component and version or commit
- Reproduction steps
- Expected impact
- Any known workaround

Do not include real credentials, access tokens, personal data, or production database contents in the report.

## Response

Reports will be assessed for reproducibility, severity, and affected deployments. Confirmed issues will be fixed on a private branch where appropriate, validated through the normal quality gate, and disclosed after affected credentials or deployments have been remediated.

## Supported Version

The latest revision of the `main` branch is the supported development version. Production deployments should track a tested release or a commit with passing CI.

For the system security model and deployment checklist, see [docs/security.md](docs/security.md).
