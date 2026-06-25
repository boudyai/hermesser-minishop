# Local Remnawave QA stand

This stand runs the Mini Shop development compose together with a pinned
Remnawave Panel and Remnawave Subscription Page. It is intended for manual
backend-QA of the Svelte runes migration paths that the Playwright mock smoke
cannot cover.

Verified upstream versions on 2026-06-25:

- Remnawave Panel `v2.7.4` (`remnawave/backend:2.7.4`)
- Remnawave Subscription Page `7.2.4` (`remnawave/subscription-page:7.2.4`)

## Prepare env

```powershell
Copy-Item deploy/dev/remnawave-dev.env.example .env.remnawave-dev
```

The example intentionally uses dry-run panel writes:

```env
PANEL_WRITE_MODE=dry_run
PANEL_DRY_RUN_VALIDATE_REMOTE=False
PANEL_DRY_RUN_SYNTHETIC_CREATE=True
```

`REMNAWAVE_DEV_API_TOKEN` in the example is a deterministic local-only API JWT
seeded by `deploy/dev/seed-remnawave.sql`. For your own live token, open
`http://127.0.0.1:3000`, create an API token in Remnawave Settings -> API
Tokens, then replace the seeded value in `.env.remnawave-dev`:

```env
REMNAWAVE_DEV_API_TOKEN=...
PANEL_API_KEY=...
PANEL_WRITE_MODE=live
PANEL_DRY_RUN_VALIDATE_REMOTE=True
```

## Start

```powershell
$env:APP_ENV_FILE = ".env.remnawave-dev"
docker compose --env-file .env.remnawave-dev `
  -f docker-compose-dev.yml `
  -f docker-compose.remnawave-dev.yml `
  --profile seed `
  up -d --build postgres redis remnawave-db remnawave-redis remnawave remnawave-dev-seed remnawave-subscription-page migrate dev-seed backend frontend
```

Local URLs:

- Mini Shop frontend: `http://127.0.0.1:8082`
- Mini Shop backend health: `http://127.0.0.1:8080/healthz`
- Remnawave Panel: `http://127.0.0.1:3000`
- Remnawave metrics health: `http://127.0.0.1:3001/health`
- Remnawave Subscription Page upstream: `http://127.0.0.1:3010`

The Subscription Page image requires a reverse proxy with HTTPS for direct
browser use. In this compose overlay `127.0.0.1:3010` is the local upstream;
plain HTTP requests to it can return an empty reply while the service is still
healthy and connected to the Remnawave Panel.

## Seed data

The `dev-seed` profile runs `deploy/dev/seed-minishop.sql` after migrations.
It also runs `deploy/dev/seed-remnawave.sql`, which creates a local Remnawave
API token plus matching Remnawave users in
`Default-Squad`. The Mini Shop seed creates three local users:

- `910000001` / `runes_admin@example.test`: active standard subscription,
  admin ID from the example env.
- `910000002` / `runes_active@example.test`: active premium subscription near
  traffic limit, useful for devices, traffic and payment table checks.
- `910000003` / `runes_expired@example.test`: expired subscription, useful for
  renewal and empty-state checks.

The seed is idempotent, so it is safe to rerun:

```powershell
docker compose --env-file .env.remnawave-dev `
  -f docker-compose-dev.yml `
  -f docker-compose.remnawave-dev.yml `
  --profile seed `
  run --rm dev-seed
```

The overlay uses separate Mini Shop database volumes
`remnawave-minishop-runes-dev-db-data` and
`remnawave-minishop-runes-dev-redis-data`, so it does not reuse or mutate an
older default dev stack volume with different credentials.

## Stop

```powershell
docker compose --env-file .env.remnawave-dev `
  -f docker-compose-dev.yml `
  -f docker-compose.remnawave-dev.yml `
  --profile seed `
  down
```

Add `-v` only when you want to delete the local databases and seeded data.
