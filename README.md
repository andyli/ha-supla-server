# SUPLA Server app for Home Assistant

A Home Assistant app (formerly add-on) that runs [SUPLA](https://www.supla.org) Cloud and SUPLA Server locally, so SUPLA devices work without `cloud.supla.org`.

User documentation: [supla_server/DOCS.md](supla_server/DOCS.md).

## Install

In Home Assistant: **Settings → Apps → Install app → ⋮ → Repositories**, add `https://github.com/andyli/ha-supla-server`, then install **SUPLA Server**.

## How it relates to supla-docker

[SUPLA/supla-docker](https://github.com/SUPLA/supla-docker) runs three containers with Docker Compose. A Home Assistant app is one container, so this app puts the same pieces in one image and runs them with s6-overlay. The image sources are on the [`src` branch](https://github.com/SUPLA/supla-docker/tree/src) of supla-docker.

| supla-docker (`src` branch) | This app |
|---|---|
| `supla-db`: `mariadb` image | Debian `mariadb-server`, data in `/data/mysql`, s6 service `mariadb` |
| `cloud/Dockerfile`: `php:8.4-apache` + release tarball | Debian `apache2` + `php8.4`, same release tarball (SHA-1 checked) |
| `cloud/cloud-entrypoint.sh` | `init-supla` (writes `.env.local`) and `init-cloud` (migrations) |
| `cloud/crontab` | s6 services `cloud-tasks` and `cloud-messenger` |
| `server/Dockerfile`: supla-core built on Debian 11 | supla-core built on Debian 13 (trixie), in a build stage |
| `server/server-entrypoint.sh`, `server/supla.cfg` | `init-supla` writes `/etc/supla-server/supla.cfg` |
| `supervisord` | s6-overlay from the Home Assistant base image |
| `.env` | App options, plus secrets generated in `/data/secrets.env` |
| `supla-server-socket` volume | `/var/run/supla` in the same container |
| `supla.sh backup` | `backup_pre` hook writes `/data/backup/supla.sql.gz` |
| MQTT to an external broker (`SUPLA_MQTT_BROKER_*`) | Mosquitto app found through the Supervisor `mqtt` service |

## Layout

```
repository.yaml               App repository metadata
supla_server/
  config.yaml                 App configuration: options, ports, backup hooks
  Dockerfile                  Build stage for supla-core; runtime on ghcr.io/home-assistant/base-debian
  rootfs/
    etc/s6-overlay/           Services: init-supla → mariadb → init-cloud → apache, supla-server, ...
    etc/apache2/              SUPLA Cloud virtual hosts
    etc/mysql/                MariaDB settings
    etc/php/                  PHP settings from supla-docker
    usr/local/bin/            supla-backup-pre, supla-console
tests/
  run-local.sh                Run the app with plain Docker, with a stub Supervisor and Mosquitto
```

## Development

Run the app locally with Docker:

```sh
tests/run-local.sh          # build and start; web UI at https://localhost:8443
tests/run-local.sh logs
tests/run-local.sh down
```

The options come from [tests/options.json](tests/options.json). The data is stored in `tests/.data/`.

To try it on a Home Assistant box, copy `supla_server/` into the box's `/addons` folder, called `local_apps` in newer docs. Then go to **Settings → Apps → Install app**, choose **Check for updates**, and install it from **Local apps**.

### Updating SUPLA

Upstream versions are set as build arguments in [supla_server/Dockerfile](supla_server/Dockerfile):

- `SUPLA_CORE_VERSION`: a tag of [supla-core](https://github.com/SUPLA/supla-core/tags).
- `SUPLA_CLOUD_VERSION`: a release of [supla-cloud](https://github.com/SUPLA/supla-cloud/releases).

Check what changed on supla-docker's `src` branch since the last update. Then bump `version` in `config.yaml` and add an entry to `CHANGELOG.md`.

## License

[GPL-2.0-or-later](LICENSE), the same as SUPLA Cloud and supla-core, which the image contains.
