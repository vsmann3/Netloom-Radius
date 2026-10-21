#!/bin/sh
# Writes a consistent application database dump; excludes deployment secrets.
set -eu
cd "$(dirname "$0")/.."
umask 077
mkdir -p backups
target="backups/netloom-$(date -u +%Y%m%dT%H%M%SZ).sql"
if [ -e "$target" ]; then
    echo "Backup filename already exists" >&2
    exit 1
fi
# No pipeline: a dump failure must not be hidden by a successful compressor.
if ! sh scripts/compose.sh exec -T db sh -ec '
    export MYSQL_PWD="$(cat /run/secrets/db_root_password)"
    exec mariadb-dump --user=root --single-transaction --quick --routines --events --triggers netloom
' > "$target.partial"; then
    echo "Dump failed; partial backup retained for diagnosis" >&2
    exit 1
fi
mv "$target.partial" "$target"
gzip "$target"
echo "Created $target.gz; copy it to protected off-VM storage."
