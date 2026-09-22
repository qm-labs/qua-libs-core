# Browsing runs in a web interface (optional self-hosting Uptrace)

With telemetry on, your runs are recorded to a file on your machine and you can
query that file directly. If you would rather browse them — search runs, compare
durations, chart them over time — you can run **Uptrace**, an open-source web
application, on the same machine or elsewhere in your network.

This is entirely optional. It needs Docker, it does not replace the local file
(runs keep going there too), and nothing leaves your network unless you choose to
host it somewhere else.

## Set it up

You need Docker: Docker Engine on Linux, or Docker Desktop on Windows or macOS.

The setup scripts are in `tools/installer/telemetry-self-host/` and
[`self-hosting/`](./self-hosting/). From either folder:

```bash
# Linux / macOS
bash setup_uptrace_local.sh
```

```powershell
# Windows (PowerShell)
.\setup_uptrace_local.ps1
```

> If PowerShell refuses to run the script ("running scripts is disabled on this
> system"), start it as
> `powershell -ExecutionPolicy Bypass -File setup_uptrace_local.ps1`.

The script starts Uptrace and its databases, waits until they are ready, and
prints the address your runs should be sent to. Open
**http://localhost:14318** and log in with `admin@example.com` / `admin`.

The installer can do all of this during installation — check the box for **Also start local
Uptrace (Docker)** if Docker is already installed.

## Point your runs at it

Add the printed address to your settings file
([CONFIGURATION.md](CONFIGURATION.md)):

```toml
[telemetry]
enabled = true
dsn = "http://project1_secret@localhost:14318?grpc=14317"
```

Uptrace calls that address a **DSN**: it is the server location plus the token
that identifies your project. If the installer set Uptrace up for you, it is
already in the file.

Run a script, then open the UI and look at **Spans** — each row is one recorded
step, and they appear within about ten seconds. Your local file keeps recording
either way; removing `dsn` only stops the copy going to Uptrace.

## Stopping and starting

Stopping keeps your data, so previous runs are still there when you start it
again. Add the wipe flag to delete them.

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

Stopping the server does not turn telemetry off — runs are still recorded locally.

## If runs do not appear

- **Wrong port.** A self-hosted server uses `14317` and `14318`. The ports
  `4317` / `4318` belong to the hosted Uptrace Cloud service and are the most
  common cause of an empty UI.
- **Telemetry is off.** Check `enabled = true` and that you restarted the script
  or kernel afterwards.
- **Your code runs in its own container.** `localhost` then means that container.
  Use `host.docker.internal` in the address, or put your container on the same
  Docker network as Uptrace.
- **A port is already taken.** Change the host-side port in `docker-compose.yml`
  (the number on the left of the colon).
- **A service keeps restarting.** The database Uptrace uses wants memory; give
  Docker at least 6 GB (Docker Desktop → Settings → Resources) and start it again.

## Setting it up by hand

The scripts above are enough for most people. If you want your own arrangement,
Uptrace publishes a ready-made Docker setup:

```bash
git clone https://github.com/uptrace/uptrace.git
cd uptrace/example/docker
docker compose up -d        # the first run downloads about 2 GB of images
docker compose ps           # everything should be running or healthy
```

Create a project and choose its token in `uptrace.yml`:

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

Your address is then `http://<your-token>@localhost:14318?grpc=14317`, which goes
into `dsn` as above. Example secret token is `project1_secret`.

## Running it for the whole lab

The same Docker setup runs on a shared machine (8 GB RAM or more, and an SSD —
storing runs is disk-bound rather than CPU-bound). If you move it off your own
computer:

- Put it behind a reverse proxy that terminates TLS, and change the address in
  `dsn` to `https://`.
- Set a retention limit on the database, otherwise the disk fills up over time.
- Back up its data directories.
- Update `dsn` on every machine that sends runs to it.

Uptrace also offers a hosted service; using it is the same setup with a different
address in `dsn`.
