#!/bin/sh
set -eu
RADIUS_DB_PASSWORD=$(cat /run/secrets/db_radius_password)
case "$RADIUS_DB_PASSWORD" in
    ''|*[!0-9a-f]*) echo "Invalid RADIUS database secret format" >&2; exit 1 ;;
esac
export RADIUS_DB_PASSWORD
if [ "${1:-}" = check ]; then
    exec freeradius -XC
fi
freeradius -XC
exec freeradius -f -l stdout
