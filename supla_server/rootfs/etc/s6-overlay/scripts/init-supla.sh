#!/command/with-contenv bashio
# shellcheck shell=bash
# Prepares config, secrets, certificates and the MariaDB data dir.
# Replaces upstream's server-entrypoint.sh and the first half of cloud-entrypoint.sh.
set -euo pipefail

DATA=/data
CLOUD=/var/www/cloud

mkdir -p /run/supla /var/run/supla /run/mysqld "${DATA}/ssl" "${DATA}/cloud-local" "${DATA}/backup"
chown mysql:mysql /run/mysqld
chown -R www-data:www-data "${DATA}/cloud-local"

# --- options ---
host_address=$(bashio::config 'host_address')
if [[ -z "${host_address}" ]]; then
  bashio::exit.nok "Set 'host_address' to the address SUPLA apps and browsers use to reach this app, e.g. 192.168.1.10."
fi
host_only=${host_address%%:*}
# SUPLA Cloud needs its address with the port. Without one in host_address,
# add the host port that the web UI (443/tcp in the container) is mapped to.
if [[ "${host_address}" != *:* ]]; then
  https_port=$(bashio::app.port 443)
  if [[ -z "${https_port}" ]]; then
    bashio::log.warning "The HTTPS port (443/tcp) is disabled; SUPLA apps won't reach SUPLA Cloud."
  elif [[ "${https_port}" != 443 ]]; then
    host_address="${host_address}:${https_port}"
  fi
fi
bashio::log.info "SUPLA Cloud address: https://${host_address}"
registration=$(bashio::config 'accounts_registration')

# --- Internet access ---
# Unless 'internet_access' is on, reject new outgoing connections to public addresses, in this
# container only. Rejected rather than dropped, so they fail at once: SUPLA Cloud's HTTP client has
# no timeout and would otherwise wait minutes. Still allowed: loopback; private and link-local
# addresses (Supervisor, DNS, Mosquitto, the LAN); host_address, which SUPLA Cloud connects to
# for its server status; and replies to incoming connections, such as phones on mobile data.
nft delete table inet supla_egress 2>/dev/null || true
if bashio::config.true 'internet_access'; then
  bashio::log.info "Internet access: allowed"
else
  host_ips=$(getent ahosts "${host_only}" | awk '{print $1}' | sort -u || true)
  host_v4=$(grep -v : <<<"${host_ips}" | paste -sd, - || true)
  host_v6=$(grep -F : <<<"${host_ips}" | paste -sd, - || true)
  allow_host=""
  if [[ -n "${host_v4}" ]]; then allow_host+="ip daddr { ${host_v4} } accept"$'\n'; fi
  if [[ -n "${host_v6}" ]]; then allow_host+="ip6 daddr { ${host_v6} } accept"$'\n'; fi
  if ! nft -f - <<EOF; then
table inet supla_egress {
  chain output {
    type filter hook output priority filter; policy accept;
    ct state established,related accept
    oifname "lo" accept
    ip daddr { 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16 } accept
    ip6 daddr { fc00::/7, fe80::/10 } accept
    ${allow_host}
    meta l4proto tcp reject with tcp reset
    reject with icmpx admin-prohibited
  }
}
EOF
    bashio::exit.nok "Could not block Internet access (see the nft error above). Turn on 'internet_access' to start without the block."
  fi
  bashio::log.info "Internet access: blocked"
fi

# --- generated secrets, kept in /data so they survive restarts and are backed up ---
if [[ ! -f "${DATA}/secrets.env" ]]; then
  bashio::log.info "Generating secrets"
  (
    umask 077
    printf 'DATABASE_PASSWORD=%s\nAPP_SECRET=%s\n' "$(openssl rand -hex 24)" "$(openssl rand -hex 32)" >"${DATA}/secrets.env"
  )
fi
# shellcheck disable=SC1091
source "${DATA}/secrets.env"

# --- certificates ---
self_signed() { # <name> <subjectAltName>
  if [[ ! -f "${DATA}/ssl/$1.crt" ]]; then
    bashio::log.info "Generating self-signed certificate: $1"
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
      -keyout "${DATA}/ssl/$1.key" -out "${DATA}/ssl/$1.crt" \
      -subj "/CN=SUPLA" -addext "subjectAltName=$2" \
      -addext "basicConstraints=critical,CA:FALSE" 2>/dev/null
    chmod 600 "${DATA}/ssl/$1.key"
  fi
}
if [[ "${host_only}" =~ ^[0-9.]+$ ]]; then san="IP:${host_only}"; else san="DNS:${host_only}"; fi

# Devices connect to supla-server over TLS on 2016. They do not check the certificate.
self_signed server "${san}"

# Browsers and the SUPLA mobile apps connect to the cloud over HTTPS.
if bashio::config.has_value 'ssl_certfile' && bashio::config.has_value 'ssl_keyfile'; then
  ln -sf "/ssl/$(bashio::config 'ssl_certfile')" /run/supla/cloud.crt
  ln -sf "/ssl/$(bashio::config 'ssl_keyfile')" /run/supla/cloud.key
else
  self_signed cloud "${san}"
  ln -sf "${DATA}/ssl/cloud.crt" /run/supla/cloud.crt
  ln -sf "${DATA}/ssl/cloud.key" /run/supla/cloud.key
fi

# --- MQTT (Mosquitto app) ---
mqtt_enabled=false
mqtt_host="" mqtt_port=1883 mqtt_ssl=0 mqtt_user="" mqtt_pass=""
if bashio::config.true 'mqtt'; then
  if bashio::services.available 'mqtt'; then
    mqtt_enabled=true
    mqtt_host=$(bashio::services 'mqtt' 'host')
    mqtt_port=$(bashio::services 'mqtt' 'port')
    mqtt_user=$(bashio::services 'mqtt' 'username')
    mqtt_pass=$(bashio::services 'mqtt' 'password')
    if bashio::var.true "$(bashio::services 'mqtt' 'ssl')"; then mqtt_ssl=1; fi
    bashio::log.info "Publishing to MQTT broker ${mqtt_host}:${mqtt_port}"
  else
    bashio::log.warning "'mqtt' is on but no MQTT broker app is available; not publishing to MQTT"
  fi
fi
echo "${mqtt_enabled}" >/run/supla/mqtt_enabled

# --- supla-server / supla-scheduler config (both read /etc/supla-server/supla.cfg) ---
mkdir -p /etc/supla-server
(
  umask 077
  cat >/etc/supla-server/supla.cfg <<EOF
[GLOBAL]
group=www-data

[NET]
cert=${DATA}/ssl/server.crt
private_key=${DATA}/ssl/server.key

[OAUTH]
url=https://${host_address}

[IPC]
socket_path=/var/run/supla/supla-server-ctrl.sock

[MySQL]
host=127.0.0.1
port=3306
database=supla
user=supla
password=${DATABASE_PASSWORD}

[MQTT-BROKER]
enabled=$([[ ${mqtt_enabled} == true ]] && echo 1 || echo 0)
host=${mqtt_host}
port=${mqtt_port}
ssl=${mqtt_ssl}
username=${mqtt_user}
password=${mqtt_pass}
client_id=supla-server
EOF
)

# --- SUPLA Cloud config ---
cat >"${CLOUD}/.env.local" <<EOF
APP_ENV=prod
APP_DEBUG=0
APP_SECRET=${APP_SECRET}
DATABASE_HOST=127.0.0.1
DATABASE_PORT=3306
DATABASE_NAME=supla
DATABASE_USER=supla
DATABASE_PASSWORD=${DATABASE_PASSWORD}
DATABASE_FOR_LOGS=mariadb
SUPLA_PROTOCOL=https
SUPLA_HOST_ADDRESS=${host_address}
MAILER_DSN=null://null
SUPLA_MAILER_FROM=
SUPLA_ADMIN_EMAIL=
SUPLA_REQUIRE_REGULATIONS_ACCEPTANCE=false
SUPLA_REQUIRE_COOKIE_POLICY_ACCEPTANCE=false
SUPLA_BRUTE_FORCE_AUTH_PREVENTION_ENABLED=true
SUPLA_ACCOUNTS_REGISTRATION_ENABLED=${registration}
SUPLA_MQTT_BROKER_ENABLED=${mqtt_enabled}
SUPLA_MQTT_BROKER_HOST=${host_only}
SUPLA_MQTT_BROKER_PORT=${mqtt_port}
SUPLA_MQTT_BROKER_TLS=false
EOF
chown www-data:www-data "${CLOUD}/.env.local"
chmod 600 "${CLOUD}/.env.local"

# Cloud state that must persist (upstream mounts this as a volume).
if [[ ! -L "${CLOUD}/var/local" ]]; then
  rm -rf "${CLOUD}/var/local"
  ln -s "${DATA}/cloud-local" "${CLOUD}/var/local"
fi

# --- MariaDB data dir ---
rm -f /run/supla/db-fresh
if [[ ! -d "${DATA}/mysql/mysql" ]]; then
  bashio::log.info "Creating MariaDB data directory"
  mkdir -p "${DATA}/mysql"
  chown mysql:mysql "${DATA}/mysql"
  mariadb-install-db --user=mysql --datadir="${DATA}/mysql" \
    --auth-root-authentication-method=socket --skip-test-db >/dev/null
  touch /run/supla/db-fresh
fi
