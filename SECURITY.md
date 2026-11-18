# Security policy

## Deployment guidance

- Use a unique, randomly generated PostgreSQL password.
- Keep `.env` readable only by the deployment account.
- Leave PostgreSQL bound to `127.0.0.1` unless remote access is deliberately
  secured with a firewall and transport encryption.
- Treat CSV files, database volumes, backups, and logs as private data.
- Keep Docker, the host operating system, and base images updated.
- Review image changes before deploying updates.

Host networking is required for accurate route and interface measurements. It
also gives the measurement container visibility into the host network
namespace. Run only images built from source you have reviewed.

## Reporting a vulnerability

Open a GitHub issue only when the report contains no credentials, public IPs,
local network details, database exports, or other private deployment data. For
sensitive reports, use GitHub's private vulnerability reporting feature when
it is enabled for the repository.
