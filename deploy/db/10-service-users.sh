#!/bin/sh
# Fresh volumes: docker-entrypoint-initdb.d. Existing volumes: compose exec db.
set -eu
read_hex_secret() {
    value=$(cat "/run/secrets/$1")
    case "$value" in
        ''|*[!0-9a-f]*) echo "Invalid database secret format" >&2; exit 1 ;;
    esac
    printf '%s' "$value"
}
app_password=$(read_hex_secret db_password)
migration_password=$(read_hex_secret db_migration_password)
radius_password=$(read_hex_secret db_radius_password)
MYSQL_PWD=$(cat /run/secrets/db_root_password)
export MYSQL_PWD
# Credentials go through stdin, never CLI arguments or generated SQL files.
mariadb --user=root --protocol=socket <<SQL
CREATE USER IF NOT EXISTS 'netloom_migrate'@'%' IDENTIFIED BY '$migration_password';
ALTER USER 'netloom_migrate'@'%' IDENTIFIED BY '$migration_password';
GRANT ALL PRIVILEGES ON netloom.* TO 'netloom_migrate'@'%';
CREATE USER IF NOT EXISTS 'netloom_app'@'%' IDENTIFIED BY '$app_password';
ALTER USER 'netloom_app'@'%' IDENTIFIED BY '$app_password';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'netloom_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON netloom.* TO 'netloom_app'@'%';
CREATE USER IF NOT EXISTS 'netloom_radius'@'%' IDENTIFIED BY '$radius_password';
ALTER USER 'netloom_radius'@'%' IDENTIFIED BY '$radius_password';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'netloom_radius'@'%';
CREATE VIEW IF NOT EXISTS netloom.radius_authorization AS SELECT 1 AS placeholder WHERE 1 = 0;
GRANT SELECT ON netloom.radius_authorization TO 'netloom_radius'@'%';
SQL
