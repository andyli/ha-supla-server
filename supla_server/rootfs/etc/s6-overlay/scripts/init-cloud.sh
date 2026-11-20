#!/command/with-contenv bashio
# shellcheck shell=bash
# Runs after MariaDB is up: database and user, restore from backup, migrations, first account.
# Replaces the second half of upstream's cloud-entrypoint.sh.
set -euo pipefail

DATA=/data
CLOUD=/var/www/cloud
# shellcheck disable=SC1091
source "${DATA}/secrets.env"

sql() { mariadb -uroot "$@"; }
console() { (cd "${CLOUD}" && s6-setuidgid www-data php bin/console "$@"); }

if [[ -f /run/supla/db-fresh ]]; then
  bashio::log.info "Loading time zone tables"
  mariadb-tzinfo-to-sql /usr/share/zoneinfo 2>/dev/null | sql mysql
fi

sql <<EOF
CREATE DATABASE IF NOT EXISTS supla CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'supla'@'127.0.0.1' IDENTIFIED BY '${DATABASE_PASSWORD}';
ALTER USER 'supla'@'127.0.0.1' IDENTIFIED BY '${DATABASE_PASSWORD}';
GRANT ALL PRIVILEGES ON supla.* TO 'supla'@'127.0.0.1';
FLUSH PRIVILEGES;
EOF

# The MariaDB data dir is left out of HA backups; backup_pre dumps it instead.
# After a restore the data dir is new, so load the dump.
if [[ -f /run/supla/db-fresh && -f "${DATA}/backup/supla.sql.gz" ]]; then
  bashio::log.info "Restoring database from ${DATA}/backup/supla.sql.gz"
  zcat "${DATA}/backup/supla.sql.gz" | sql supla
fi
rm -f /run/supla/db-fresh

bashio::log.info "Initializing SUPLA Cloud (database migrations)"
rm -rf "${CLOUD}/var/cache/"*
chown -R www-data:www-data "${CLOUD}/var"
console supla:initialize
console cache:warmup >/dev/null

if bashio::config.has_value 'user_email' && bashio::config.has_value 'user_password'; then
  console supla:user:create "$(bashio::config 'user_email')" "$(bashio::config 'user_password')" --if-not-exists
fi

# Publish every account's devices to MQTT (the per-account switch in the Cloud UI).
if [[ "$(cat /run/supla/mqtt_enabled)" == true ]]; then
  sql supla -e "UPDATE supla_user SET mqtt_broker_enabled = 1 WHERE mqtt_broker_enabled = 0"
fi
