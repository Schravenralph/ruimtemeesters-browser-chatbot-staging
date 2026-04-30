# Security: never expose databases publicly

## Status

Accepted — 2026-04-17

## Context

On 2026-04-17 a dev `docker-compose.yml` in `Ruimtemeesters-Transcriber`
published MongoDB on `0.0.0.0:27017` with no authentication. The AKIRA
ransomware group connected over the public internet, wiped the
`whisper_db.transcripts` collection, and dropped a ransom note in a new
`READ_ME_TO_RECOVER_YOUR_DATA` database asking 0.0059 BTC.

Unauthenticated public MongoDB, PostgreSQL, Redis, and Elasticsearch
instances are a continuous target for automated scanners. The exposure
window that led to this incident was short; the attack chain is fully
automated.

## Decision

Databases MUST NOT be published on `0.0.0.0` — in any compose file,
systemd unit, or deployment configuration, in dev or prod, on this
server or any other. This applies to MongoDB, PostgreSQL, Redis,
Elasticsearch, and every other datastore.

Required patterns:

- Services on the same docker-compose reach the DB by service name over
  the internal network. Use `expose: - "27017"` (or equivalent) instead
  of `ports:`.
- If host-side access is genuinely required for tooling, bind to
  `127.0.0.1:PORT` only — never `0.0.0.0` or the server's public
  interface.
- Authentication is enabled from day one (`--auth` + credentials).
  Network isolation alone is not sufficient defence.
- Remote access during debugging uses `ssh -L` tunnels, not published
  ports.

The same rule applies to adjacent infrastructure that attackers
regularly pivot through: VNC, Jupyter, unauthenticated LLM inference
endpoints, Redis without `requirepass`, etc.

## Consequences

- Compose files that publish a DB port to `0.0.0.0` fail review.
- Host-side DB tooling runs via `docker compose exec` or inside the
  container, not on the host.
- Dev convenience is never a reason to skip any of the above.

## References

- Incident write-up: `Ruimtemeesters-Transcriber` PR #34.
- MongoDB security checklist:
  https://www.mongodb.com/docs/manual/administration/security-checklist/
