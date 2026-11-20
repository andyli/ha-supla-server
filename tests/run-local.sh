#!/usr/bin/env bash
# Build and run the app with plain Docker, next to a stub Supervisor and a Mosquitto broker.
#   tests/run-local.sh [up|down|logs]
# Cloud UI: https://localhost:8443  (account from tests/options.json)
# Devices:  localhost:2016 (TLS), localhost:2015 (plain)
set -euo pipefail
cd "$(dirname "$0")/.."

NET=supla-test
DATA=${DATA:-$PWD/tests/.data}

down() { docker rm -f supla-app supla-supervisor supla-mqtt >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }

up() {
  down
  docker build -t local/supla_server:dev supla_server
  mkdir -p "$DATA"
  cp tests/options.json "$DATA/options.json"
  docker network create "$NET" >/dev/null
  docker run -d --name supla-mqtt --network "$NET" eclipse-mosquitto:2.0.22 \
    sh -c 'printf "listener 1883\nallow_anonymous true\n" >/mosquitto/config/mosquitto.conf && exec mosquitto -c /mosquitto/config/mosquitto.conf' >/dev/null
  docker run -d --name supla-supervisor --network "$NET" --network-alias supervisor \
    -e MQTT_HOST=supla-mqtt -v "$PWD/tests/mock_supervisor.py:/mock.py:ro" -v "$DATA/options.json:/options.json:ro" \
    python:3.13-alpine python -u /mock.py >/dev/null
  until docker exec supla-supervisor wget -qO- http://127.0.0.1/addons/self/info >/dev/null 2>&1; do sleep 0.5; done
  docker run -d --name supla-app --network "$NET" -e SUPERVISOR_TOKEN=test \
    -v "$DATA:/data" -p 8443:443 -p 2016:2016 -p 2015:2015 local/supla_server:dev >/dev/null
  echo "started; follow with: $0 logs"
}

case "${1:-up}" in
  up) up ;;
  down) down ;;
  logs) docker logs -f supla-app ;;
  *) echo "usage: $0 [up|down|logs]"; exit 1 ;;
esac
