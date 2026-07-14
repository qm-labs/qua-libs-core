# Self-Hosting Uptrace (the default telemetry destination)

`qua_libs_core.telemetry` is off by default. When you enable it, the **standard, recommended
destination is a self-hosted Uptrace** — all telemetry stays on your own machine/network,
nothing leaves the site. This is the right default for QM-managed systems and for air-gapped
or privacy-sensitive installations. (Uptrace Cloud also works — it's just a different
`UPTRACE_DSN` value; see the note at the end.)

**No code changes are needed.** Enable telemetry via `.qua-libs/telemetry.toml` or
environment variables; the package passes the DSN to `uptrace.configure_opentelemetry`.
See [CONFIGURATION.md](CONFIGURATION.md).

## Quick start (recommended): one command

This repo bundles a ready-to-run local Uptrace. You need Docker (Docker Engine on
Linux, or Docker Desktop on Windows/macOS).

Scripts are in `tools/installer/telemetry-self-host/` and [`self-hosting/`](./self-hosting/).

From either directory:

**Linux / macOS:**

```bash
bash setup_uptrace_local.sh
```

**Windows (PowerShell):**

```powershell
.\setup_uptrace_local.ps1
```

> If PowerShell refuses to run the script ("running scripts is disabled on this
> system"), launch it as `powershell -ExecutionPolicy Bypass -File setup_uptrace_local.ps1`.

It checks for Docker, brings up the stack (ClickHouse + PostgreSQL + Redis + Uptrace),
waits until it's healthy, and prints the DSN.

When it finishes, open the UI at **http://localhost:14318** (login
`admin@example.com` / `admin`). Then enable span export:

**Option A — project file (recommended):** create or edit
`<repo>/.qua-libs/telemetry.toml`:

```toml
[telemetry]
enabled = true
dsn = "http://project1_secret@localhost:14318?grpc=14317"
```

**Option B — environment variables:**
```bash
# Linux / macOS
export UPTRACE_ENABLED="true"
export UPTRACE_DSN="http://project1_secret@localhost:14318?grpc=14317"
```

```powershell
# Windows (PowerShell)
$env:UPTRACE_ENABLED = "true"
$env:UPTRACE_DSN = "http://project1_secret@localhost:14318?grpc=14317"
```

If you used the QUA Libraries installer with telemetry enabled, the TOML file is
already written — start Uptrace and run instrumented code.

Run an instrumented node or script, and spans appear under the project's **Spans** tab.

### Stopping

Stopping keeps your data by default (so spans survive a restart); add the wipe flag to
also delete the ClickHouse + PostgreSQL volumes.

```bash
# Linux / macOS
bash stop_uptrace_local.sh         # stop, keep data
bash stop_uptrace_local.sh --wipe  # stop and delete all data
```

```powershell
# Windows (PowerShell)
.\stop_uptrace_local.ps1           # stop, keep data
.\stop_uptrace_local.ps1 -Wipe     # stop and delete all data
```

The sections below describe the **manual equivalent**, e.g. for a customised stack.

## 1. Stand up a local Uptrace

Uptrace ships a ready-to-run Docker Compose stack. You need Docker (Desktop, or `docker-ce`
plus the compose plugin).

```bash
git clone https://github.com/uptrace/uptrace.git
cd uptrace/example/docker
docker compose up -d        # first run pulls ~2 GB of images
docker compose ps           # every service should be running / healthy
```

The stack includes ClickHouse (data store), PostgreSQL (metadata), Redis, the Uptrace UI +
ingest, and an OpenTelemetry Collector. Open the UI at **http://localhost:14318** to confirm
it is healthy end-to-end.

> ClickHouse is memory-hungry. If a service is stuck `restarting`, give Docker ≥ 6 GB
> (Docker Desktop → Settings → Resources) and bring the stack back up.

## 2. Create a project and get your DSN

Edit `uptrace.yml` in `example/docker` and set a project + token:

```yaml
projects:
  - id: 2
    name: qua-libs
    token: <choose-a-secret-token>
    pinned_attrs:
      - service.name
      - host.name
      - deployment.environment
```

```bash
docker compose restart uptrace
```

Your **self-hosted DSN** is then:

```
http://<your-token>@localhost:14318?grpc=14317
```

> **DSN format:** `http(s)://<token>@<host>:<http_port>?grpc=<grpc_port>`.
>
> **The #1 gotcha:** self-hosted ingest ports are **14317 (gRPC)** and **14318 (HTTP)** —
> *not* the cloud `4317` / `4318`. Most "no spans appear" problems are the wrong port.

## 3. Point qua-libs telemetry at it

No code change — enable span export and set the self-hosted DSN via
[`.qua-libs/telemetry.toml`](CONFIGURATION.md) or environment variables:

```toml
[telemetry]
enabled = true
dsn = "http://<your-token>@localhost:14318?grpc=14317"
```

```bash
export UPTRACE_ENABLED="true"
export UPTRACE_DSN="http://<your-token>@localhost:14318?grpc=14317"
```

That DSN value is the *only* thing that differs between cloud and self-hosted.

## 4. Verify

Run any instrumented node/script with telemetry enabled, then in the Uptrace UI
(http://localhost:14318) pick the project → **Spans**. Spans should appear within
~10 seconds. Telemetry is off by default until `enabled = true` in TOML or
`UPTRACE_ENABLED=true`.

## Gotchas

- **Wrong port** — `14317` for self-hosted gRPC, not `4317`.
- **App runs in its own container** — `localhost` then refers to the container, not the host.
  Use `host.docker.internal` in the DSN, or attach your app's container to the Uptrace compose
  network.
- **Port already in use** — change the host-side port mappings in `docker-compose.yml`
  (left side is host, right side is container).

## Moving to a real host (production)

The same `docker-compose.yml` runs unchanged on a VM (≥ 8 GB RAM, fast SSD — ClickHouse's cost
is I/O, not CPU). To promote it:

- Put Uptrace behind a TLS-terminating reverse proxy and switch the client DSN scheme to
  **`https://`**.
- Set ClickHouse table **TTL** to your retention target — otherwise disk fills indefinitely.
- Back up ClickHouse and PostgreSQL.
- Recreate dashboards/alerts (they do not migrate from Cloud automatically).
- Update every service's `UPTRACE_DSN` to point at the new host.
