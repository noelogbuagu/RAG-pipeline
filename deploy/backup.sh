#!/usr/bin/env bash
# Back up everything the stack keeps: Inngest run history (Postgres), the Qdrant
# index (a snapshot per collection), and the uploaded source documents.
#
#   deploy/backup.sh                 # writes backups/<UTC timestamp>/
#   BACKUP_DIR=/mnt/backups KEEP_DAYS=30 deploy/backup.sh
#
# Copy the result off this server (object storage, another machine): a backup on
# the same disk does not survive losing the disk. See docs/DEPLOYMENT.md to restore.
set -euo pipefail

cd "$(dirname "$0")/.."
ENV_FILE="${ENV_FILE:-deploy/.env.production}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"

dc() { docker compose -f deploy/docker-compose.yml --env-file "$ENV_FILE" "$@"; }

destination="$BACKUP_DIR/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$destination"
umask 077

echo "Backing up Inngest state (Postgres)..."
dc exec -T postgres pg_dump -U inngest inngest | gzip > "$destination/inngest.sql.gz"

echo "Backing up the Qdrant index (snapshots)..."
dc exec -T api python - > "$destination/qdrant-snapshots.tar" <<'PY'
import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request

base = os.environ["QDRANT_URL"].rstrip("/")
headers = {"api-key": os.environ["QDRANT_API_KEY"]}


def call(path, method="GET"):
    request = urllib.request.Request(base + path, method=method, headers=headers)
    return urllib.request.urlopen(request, timeout=900)


collections = json.load(call("/collections"))["result"]["collections"]
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as archive:
    for item in collections:
        name = item["name"]
        snapshot = json.load(call(f"/collections/{name}/snapshots", "POST"))["result"]["name"]
        with tempfile.TemporaryFile() as spool:
            shutil.copyfileobj(call(f"/collections/{name}/snapshots/{snapshot}"), spool)
            info = tarfile.TarInfo(f"{name}/{snapshot}")
            info.size = spool.tell()
            spool.seek(0)
            archive.addfile(info, spool)
        # The copy is in the archive; do not leave snapshots filling the Qdrant disk.
        call(f"/collections/{name}/snapshots/{snapshot}", "DELETE")
PY

echo "Backing up uploaded documents..."
docker run --rm --mount type=volume,src=rag-pipeline_uploads,dst=/data,readonly \
  alpine:3 tar czf - -C /data . > "$destination/uploads.tar.gz"

# Fail loudly on a truncated or corrupt file instead of discovering it at restore time.
gzip -t "$destination/inngest.sql.gz"
gzip -t "$destination/uploads.tar.gz"
tar -tf "$destination/qdrant-snapshots.tar" > /dev/null

# Remove only timestamped backup folders this script created, older than KEEP_DAYS.
find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '20*T*Z' -mtime "+$KEEP_DAYS" \
  -exec rm -rf {} +

echo "Backup complete: $destination"
ls -lh "$destination"
