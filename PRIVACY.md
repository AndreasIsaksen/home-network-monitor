# Privacy notes

Home Network Monitor is self-hosted. The application does not send stored
database rows or CSV exports to the project maintainers.

## Data handled by the application

A measurement can include:

- Local interface and router addresses
- Public IP address and ISP name returned by the speed-test provider
- Speed-test server metadata and a provider result URL
- Network-performance and interface-health measurements
- Measurement timestamps

Depending on jurisdiction and context, some of these fields may be personal or
household-identifying data. The PostgreSQL volume and CSV exports should
therefore be protected like other private infrastructure logs.

## External network services

The application sends test traffic to the configured public DNS addresses and
to an Ookla-selected speed-test server. Those services can observe the source
public IP address as part of normal internet communication. Review their terms
and privacy policies before use.

## Operator responsibilities

- Keep `.env`, database backups, volumes, and CSV exports private.
- Restrict access to the Docker host and its loopback-published database port.
- Define an appropriate retention period for the deployment.
- Delete expired rows, exports, and backups according to that policy.
- Do not attach real exports or logs to public bug reports without redaction.

The project does not include automatic remote telemetry or a cloud dashboard.
It also does not implement an automatic retention policy; the operator controls
the database and is responsible for its lifecycle.
