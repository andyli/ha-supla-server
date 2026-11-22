# SUPLA Server app for Home Assistant

A Home Assistant app (formerly add-on) that runs [SUPLA](https://www.supla.org) Cloud and SUPLA Server locally, so SUPLA devices work without `cloud.supla.org`.

**Unofficial:** this app is not made, supported or endorsed by SUPLA. The SUPLA name and logo belong to their owners.

User documentation: [supla_server/DOCS.md](supla_server/DOCS.md).

## Install

In Home Assistant: **Settings → Apps → Install app → ⋮ → Repositories**, add `https://github.com/andyli/ha-supla-server`, then install **SUPLA Server**.

Home Assistant downloads a pre-built image for `amd64` or `aarch64` from GitHub Container Registry (`ghcr.io/andyli/{arch}-supla_server`), so nothing is compiled on the device.

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
  run_local.py                Run the app with plain Docker, with a stub Supervisor and Mosquitto
  mock_supervisor.py          Stub Supervisor API: app options and the mqtt service
  options.json                App options for local runs and tests
  smoke.py                    Smoke test, run inside the app container
tools/
  supla_cloud.py              List devices and rename channels through the SUPLA Cloud API
.github/workflows/ci.yaml     CI: lint, smoke test on amd64 and aarch64, publish images to GHCR
.dagger/                      Dagger module (Python): builds the image, runs the tests, publishes
dagger.json                   Dagger module metadata
justfile                      Build, run and test commands
mise.toml, mise.lock          Tool versions (just, dagger, uv)
pyproject.toml, uv.lock       Python dev tools (mypy, ruff); .python-version sets the Python version
```

## Tools

[tools/supla_cloud.py](tools/supla_cloud.py) talks to a SUPLA Cloud instance through its API. It needs only Python. Use it to name channels after moving devices, without opening the web UI:

```sh
export SUPLA_URL=https://192.168.1.10:4433 SUPLA_EMAIL=you@example.com
tools/supla_cloud.py --insecure devices                 # devices, channels and their captions
tools/supla_cloud.py --insecure rename-channel 1 "kitchen table dimmer"
```

The password comes from `SUPLA_PASSWORD`, or the tool asks for it. `--insecure` skips the certificate check, which the app's self-signed certificate needs.

## Development

You need Docker and [mise](https://mise.jdx.dev). mise installs the other tools, [just](https://just.systems), [Dagger](https://dagger.io), [uv](https://docs.astral.sh/uv/) and Python, at the versions in [mise.toml](mise.toml), `mise.lock` and [.python-version](.python-version). The repository is a [uv project](https://mise.jdx.dev/mise-cookbook/python.html#mise-uv): mise creates and activates `.venv`, and `uv run` installs the dev tools from `uv.lock` into it.

```sh
mise install
just              # list the commands
```

Run the app locally with Docker:

```sh
just up           # build and start; web UI at https://localhost:8443
just logs
just down
```

The options come from [tests/options.json](tests/options.json). The data is stored in `tests/.data/`.

### Tests

```sh
just test
```

This runs a smoke test in Dagger. It builds the image and starts it next to a stub Supervisor and Mosquitto. Then [tests/smoke.py](tests/smoke.py) runs inside the container as its main command, after s6-overlay has started all services. It checks that:

- the init steps succeed (if one fails, s6 stops the container and the test fails)
- the web UI answers on 443, and the account from `tests/options.json` can log in
- supla-server listens on 2016 and 2015
- no service is down or restarts within 30 seconds

The first run takes several minutes because it compiles supla-core. Later runs reuse Dagger's build cache.

To test other options, pass a file: `dagger call smoke-test --options=path/to/options.json`.

### Lint

```sh
just lint
```

This type-checks `tests/` and `tools/` with mypy in strict mode and lints all Python code with ruff. Their settings are in [pyproject.toml](pyproject.toml). Python is 3.13 everywhere: `.python-version`, `.dagger/.python-version`, and the images the tests use.

To try it on a Home Assistant box, copy `supla_server/` into the box's `/addons` folder, called `local_apps` in newer docs. Delete the `image:` line from the copied `config.yaml`, or Home Assistant downloads the published image instead of building your copy. Then go to **Settings → Apps → Install app**, choose **Check for updates**, and install it from **Local apps**.

### CI and published images

[.github/workflows/ci.yaml](.github/workflows/ci.yaml) runs on every push and pull request:

1. `just lint`
2. `just test` on an amd64 runner and on an arm64 runner (`ubuntu-24.04-arm`), so each arch's image is built and smoke-tested natively

On `main`, each test job then pushes the image it has just tested to `image` in [supla_server/config.yaml](supla_server/config.yaml) (`ghcr.io/andyli/{arch}-supla_server`), tagged with `version`. A version is published only once. If its tag already exists, the job skips publishing, so a change only reaches users after a `version` bump. Home Assistant offers the update as soon as the new `config.yaml` is on `main`, but the image appears only after CI finishes, about the length of a test run later.

The Dagger functions behind this also work locally: `dagger call image-ref` prints the reference for your machine's arch, and `dagger call publish` pushes with your `docker login` credentials.

The GHCR packages must be public for Home Assistant to pull them. GitHub makes a new package private, so after the first publish of each arch, open the package's **Package settings** and change its visibility to public.

### Updating SUPLA

Upstream versions are set as build arguments in [supla_server/Dockerfile](supla_server/Dockerfile):

- `SUPLA_CORE_VERSION`: a tag of [supla-core](https://github.com/SUPLA/supla-core/tags).
- `SUPLA_CLOUD_VERSION`: a release of [supla-cloud](https://github.com/SUPLA/supla-cloud/releases).

Check what changed on supla-docker's `src` branch since the last update. Then bump `version` in `config.yaml` and add an entry to `CHANGELOG.md`. CI publishes the new images when the change reaches `main`.

## License

[GPL-2.0-or-later](LICENSE), the same as SUPLA Cloud and supla-core, which the image contains.
