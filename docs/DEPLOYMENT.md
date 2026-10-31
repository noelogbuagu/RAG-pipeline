# Production deployment

This runs the app for a team on **one server with Docker Compose**. Users sign in
with your identity provider (OIDC) and share one pool of documents. For local
development, keep using the [README](../README.md); nothing there changes.

## What runs

| Service | Role | Reachable from |
| --- | --- | --- |
| `caddy` | HTTPS certificate, request size limit, security headers | Internet (ports 80, 443) |
| `oauth2-proxy` | OIDC login in front of the app | `caddy` only |
| `ui` | Streamlit upload and question screens | `oauth2-proxy` only |
| `api` | FastAPI app that hosts the Inngest workflows | `inngest` and `ui` only |
| `inngest` | Self-hosted workflow server (retries, run history) | Server loopback `127.0.0.1:8288` |
| `postgres`, `redis` | Inngest state and queue, persisted to volumes | Internal network |
| `qdrant` | Vector database server, API-key protected | Internal network |

Only Caddy is public. Nothing reaches the app without signing in, and only people
whose email domain you allow can. The Inngest dashboard is not on the internet;
use an SSH tunnel (below).

## Before you start

- A Linux server with Docker Engine and the Compose plugin. Allow about 2 vCPUs and
  4 GB of memory, plus disk for documents and the index. The next section prepares one
  on Hetzner.
- A domain name whose DNS record points at the server, with ports 80 and 443 open
  to the internet. Caddy needs both to obtain the certificate.
- An OIDC client from your identity provider (Google, Microsoft Entra ID, Okta, and
  so on) with the redirect URI `https://<your-domain>/oauth2/callback`.
- An OpenAI API key with billing, and access to `text-embedding-3-large` and
  `gpt-5.4-mini`.

## Prepare a Hetzner server

Skip this section if you host elsewhere; any Linux server works. These steps follow
Hetzner Cloud's own guides ([create a server](https://docs.hetzner.com/cloud/servers/getting-started/creating-a-server),
[create a firewall](https://docs.hetzner.com/cloud/firewalls/getting-started/creating-a-firewall),
[connect to it](https://docs.hetzner.com/cloud/servers/getting-started/connecting-to-the-server)),
so check them for any screen that has changed.

### 1. Create the server

In the [Hetzner Cloud Console](https://console.hetzner.cloud/), create a server in a
project of its own, so that tokens, billing, and clean-up stay separate from your
other work.

- **Image:** a current Ubuntu LTS release.
- **Size:** at least 4 GB of memory. Eight containers run on it and the image build
  needs headroom. Check the Console for current sizes and prices.
- **SSH key:** add your public key when you create the server and sign in with it.
  Do not rely on an emailed root password.
- **Use a fresh server.** If you reuse one that already runs another stack, make sure
  nothing else is using ports 80 and 443 (an existing Caddy or nginx would clash with
  this stack's Caddy).

### 2. Create the firewall

Hetzner Cloud Firewalls filter traffic before it reaches the server, so they also
block ports that Docker publishes. That makes them a useful second layer. Create a
firewall with these inbound rules and apply it to the server. A server with no
firewall accepts traffic on every port.

| Port | Source | Why |
| --- | --- | --- |
| 22 (SSH) | **Your IP address only** | Full control of the server; keep it narrow |
| 80 (HTTP) | Any IPv4 and IPv6 | Certificate issuance and redirect to HTTPS |
| 443 (HTTPS) | Any IPv4 and IPv6 | The app |

Do **not** open 8000, 8288, or 8501. The Inngest dashboard is reached through an SSH
tunnel instead (see Operate). If your home IP changes, update the SSH rule in the
Console; a VPN with a fixed address avoids this.

### 3. Point a hostname at it

At the registrar or DNS host for your domain, create an `A` record for the hostname
you will use, such as `rag`, pointing at the server's IPv4 address. Add an `AAAA`
record for its IPv6 address only if you want IPv6 (the firewall rules above already
allow it). Wait until the name resolves before starting the stack:

```sh
dig +short rag.example.com      # should print the server's IP address
```

Caddy requests its certificate the first time it starts. Starting before DNS is
correct means failed attempts, and Let's Encrypt limits repeated failures.

### 4. Install Docker and fetch the code

Connect with `ssh root@<server-ip>` (or the user you created), then install Docker
Engine with the Compose plugin by following Docker's
[Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/). Check it:

```sh
docker --version && docker compose version
```

Install pending security updates (`apt update && apt upgrade`) and consider enabling
automatic security updates. Then fetch the code where the other steps expect it:

```sh
git clone https://github.com/noelogbuagu/RAG-pipeline.git /opt/RAG-pipeline
cd /opt/RAG-pipeline
```

Continue with **Deploy**, skipping its `git clone` and `cd` lines. Hetzner's optional
server backups and snapshots help with rebuilding the machine, but they do not replace
`deploy/backup.sh`; copy those backups to a separate location such as a Hetzner
Storage Box or object storage.

## Deploy

```sh
git clone https://github.com/noelogbuagu/RAG-pipeline.git
cd RAG-pipeline
cp deploy/.env.production.example deploy/.env.production
chmod 600 deploy/.env.production
```

Edit `deploy/.env.production`. The file explains every value and how to generate
each secret with `openssl` on the server. Then start everything:

```sh
docker compose -f deploy/docker-compose.yml --env-file deploy/.env.production up -d --build
docker compose -f deploy/docker-compose.yml --env-file deploy/.env.production ps
```

All services should become `healthy` or `Up`. Open `https://<your-domain>`: you
are sent to your identity provider and then to the app. Compose stops with a
message naming any setting you left blank, and the app refuses to start in
production without its required settings.

Upload a document and ask a question to confirm the whole path works.

### Who can sign in

`ALLOWED_EMAIL_DOMAINS` admits everyone with an address at those domains. To admit
specific people instead, replace `OAUTH2_PROXY_EMAIL_DOMAINS` in
`deploy/docker-compose.yml` with `OAUTH2_PROXY_AUTHENTICATED_EMAILS_FILE` and mount a
file with one address per line. See the
[oauth2-proxy documentation](https://oauth2-proxy.github.io/oauth2-proxy/) for
provider-specific options and group restrictions.

## Operate

```sh
alias rag='docker compose -f deploy/docker-compose.yml --env-file deploy/.env.production'
rag logs -f api            # application and workflow logs
rag ps                     # health of every service
git pull && rag up -d --build   # update to the latest code
rag down                   # stop; volumes (your data) are kept
```

**Inngest dashboard** (failed steps, run history). From your own computer:

```sh
ssh -L 8288:127.0.0.1:8288 <user>@<server>
```

Then open [localhost:8288](http://localhost:8288). Never publish port 8288: the
dashboard has no login of its own.

**Rotating secrets.** Change the value in `deploy/.env.production` and run
`rag up -d`. Changing `QDRANT_API_KEY` also needs a Qdrant restart (`rag restart qdrant`).
Changing `POSTGRES_PASSWORD` after the first start requires changing the password
inside Postgres as well, so decide it before the first deployment.

## Backups and restore

`deploy/backup.sh` writes a timestamped folder with the Inngest database dump, a
Qdrant snapshot of each collection, and the uploaded documents. It verifies the
files and deletes backup folders older than `KEEP_DAYS` (14 by default).

```sh
deploy/backup.sh                        # backups/<timestamp>/
BACKUP_DIR=/mnt/backups deploy/backup.sh
```

Schedule it with cron, for example `15 2 * * * cd /srv/RAG-pipeline && deploy/backup.sh`, and
**copy the folders off the server**: a backup on the same disk is lost with the disk.
Backups contain your documents and the text of their passages; protect them like the
originals.

**Restore onto an empty stack** (the project name `rag-pipeline` is part of the
volume names). Stop the application services first:

```sh
rag up -d postgres qdrant                 # databases only
B=backups/<timestamp>

# 1. Inngest database
gunzip -c $B/inngest.sql.gz | rag exec -T postgres psql -U inngest inngest

# 2. Uploaded documents
docker run --rm -i --mount type=volume,src=rag-pipeline_uploads,dst=/data \
  alpine:3 tar xzf - -C /data < $B/uploads.tar.gz

# 3. Qdrant index: unpack the snapshot, then upload it to the collection
mkdir -p /tmp/snap && tar -xf $B/qdrant-snapshots.tar -C /tmp/snap
NAME=documents-openai-3-large-3072
docker run --rm --network rag-pipeline_default -v /tmp/snap/$NAME:/s curlimages/curl:8.10.1 \
  -s -H "api-key: $QDRANT_API_KEY" -X POST \
  "http://qdrant:6333/collections/$NAME/snapshots/upload?priority=snapshot" \
  -F snapshot=@/s/<snapshot-file-name>

rag up -d                                 # start everything
```

## Security notes

- **Secrets** live only in `deploy/.env.production` (ignored by Git) and in the
  containers' environment. Anyone with shell access to the server can read them.
- **Data handling.** Document text and questions are sent to OpenAI for embeddings and
  answers. Use only material you may send. Inngest keeps workflow inputs and outputs
  in its Postgres database, and uploads stay on the server until you remove them.
- **Everyone who signs in sees every document.** This build has one shared pool.
  Per-user or per-client separation would need a design change in storage, search,
  and the workflows.
- **Docker and firewalls.** Published ports bypass host firewalls such as `ufw`.
  That is why only Caddy publishes public ports and Inngest is bound to loopback.
  Do not add `ports:` entries to other services.
- Keep the server patched, and keep Docker images current by rebuilding and
  updating the pinned versions in `deploy/docker-compose.yml`.

## Limits and what is verified

Verified on a laptop with Docker Desktop: the image builds; every service becomes
healthy; the app registers with the self-hosted Inngest server; a real PDF ingests
and answers questions through the Streamlit UI against the Qdrant server; unauthenticated
requests, including the websocket path, are redirected to the login provider; and the
backup script runs and its Qdrant snapshot restores (the collection was deleted
and recovered with all 18 chunks).

**Not yet verified:** a real OIDC sign-in with a registered client and domain, public
HTTPS certificate issuance, Streamlit's websocket through an authenticated session,
the Inngest database and uploads restore steps, running on a Linux server, and load
or long-running behavior. Rehearse a restore and a sign-in before relying on this.

Known limits carried over from the demo: no OCR, no relevance threshold on
retrieval, no automatic cleanup of old document versions, documents capped at 256
chunks and 2 MiB of text per workflow step, and a single API process (Inngest
concurrency is set to one run at a time per function). Monitoring and alerting are
not included beyond container health checks and logs.
