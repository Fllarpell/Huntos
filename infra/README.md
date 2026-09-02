# Infrastructure — work_finding

Single-VPS origin for the Job CRM (FastAPI + Next.js). Not a mil-RPS platform.
Compose is the orchestrator until there is a second host or a real replica count.

## Topology

```
Internet → Cloudflare (WAF, TLS) → origin :80/:443 (nginx)
                                      ├─ /api  → backend:8000   (app net)
                                      └─ /     → frontend:3000  (app net)
backend ── data net (internal) ── pgbouncer → postgres
Grafana / Prometheus / Loki: 10.7.0.1:3001 (WireGuard) or 127.0.0.1 via SSH -L
SSH after lockdown: 10.7.0.1:2222 only
```

## Load model (why these numbers)

Human CRM + polite scrapers + one Telethon session. Design point: **<20 rps**,
not 1M. Sysctl backlogs are 4096, postgres `max_connections=40`, pgbouncer
`default_pool_size=10`. BBR is still correct: scraper egress is RTT-bound.

## SPOF register (current code, not hypothetical)

| Component | Why it is a SPOF | Cutover |
|---|---|---|
| SQLite + local `/data` | No HA, no replica, backup = file copy | `DATABASE_URL` → pgbouncer (needs asyncpg + Alembic) |
| APScheduler | Was in uvicorn; now `python -m app.worker` + APP_ROLE=api | Redis is in compose for the next queue cutover |
| Telethon session files | Sticky disk state | Volume today; dedicated worker later |
| Single VPS | Disk/host death | Second box + postgres replica + CF origin pool |
| In-process scrape/LLM | Holds API latency | Queue (Redis) + worker profile |

Do **not** run `replicas: 2` on backend while DATABASE_URL is sqlite (writer lock). Worker is already a separate container.

## Bring-up

### Host (Ubuntu 24.04)

```bash
# on the laptop: generate a client WG keypair
wg genkey | tee client.key | wg pubkey > client.pub

# on the VPS
cp infra/bootstrap/bootstrap.env.example /root/bootstrap.env
# fill ADMIN_USER, ADMIN_SSH_PUBKEY, WG_CLIENT_PUBKEY
sudo -E infra/bootstrap/bootstrap.sh
# bring the client up, then from a WG session:
sudo -E infra/bootstrap/bootstrap.sh --lockdown
sudo infra/bootstrap/verify.sh
```

Lockdown refuses unless a handshake landed in the last 180s.

### App

```bash
cd infra/compose
./gen-secrets.sh
# put OPENAI_API_KEY etc in generated/app.env
docker compose --profile data --profile app --profile edge --profile obs up -d --build
```

Laptop without WireGuard:

```bash
cd infra/compose
./gen-secrets.sh
docker compose -f compose.yaml -f compose.laptop.yaml \
  --profile data --profile app --profile edge --profile obs up -d --build
```

Grafana: http://127.0.0.1:3001  Origin: https://127.0.0.1:8443 (`curl -k`).

Replace `infra/edge/tls/origin.{crt,key}` with a Cloudflare Origin CA cert
before switching the zone to Full (strict). Enable origin pulls:

```bash
cp infra/edge/nginx/snippets/origin-pull.enabled.conf \
   infra/edge/nginx/snippets/origin-pull.conf
```

Then run `infra/edge/nginx/fetch-cloudflare-ips.sh` (or wait for the weekly timer)
so `CF-Connecting-IP` is trusted.

### Cloud-init

```bash
cp infra/bootstrap/bootstrap.env.example /tmp/bootstrap.env
# fill ADMIN_*, WG_CLIENT_PUBKEY
REPO_URL=git@github.com:you/work_finding.git REPO_REF=main \
  infra/cloud-init/render.sh /tmp/bootstrap.env
# attach generated/user-data.yaml at provider
```

Lockdown is still a second step (`bootstrap.sh --lockdown`) after WG handshake.

## Secrets

- Never in git, compose.yaml, or images.
- Laptop/VPS: `infra/compose/generated/` (mode 600, gitignored).
- Age+SOPS: `./infra/secrets/init-age.sh` then `sops -e -i infra/secrets/secrets.yaml`.
- Docker secrets for postgres/grafana passwords; pgbouncer userlist is a bind mount
  from `generated/userlist.txt`.

## Backups

```bash
sudo ./infra/backup/backup.sh
sudo ./infra/backup/restore-drill.sh
```

Copy `infra/backup/restic.env.example` → `restic.env` once the Object-Lock bucket exists.

## What is intentionally not here

- Kubernetes / Swarm — control plane cost with one node.
- Kafka / NATS — no consumer group yet; APScheduler is the queue.
- MinIO — no object store in the app.
- Fail2Ban / port knocking — CrowdSec + WireGuard.
- Distroless backend — bcrypt + uvicorn on CPython; slim + uid 65532 instead.
