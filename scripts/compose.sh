#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec docker compose --env-file image-lock.env --env-file .env "$@"
