# Tools (just, dagger, uv, python) come from mise.toml: run `mise install` once.
# Python dev tools (mypy, ruff) come from pyproject.toml and uv.lock.

# List recipes
default:
    @just --list

# Build the app image with local Docker
build:
    docker build -t local/supla_server:dev supla_server

# Run the app with local Docker, next to a stub Supervisor and Mosquitto (https://localhost:8443)
up:
    python tests/run_local.py up

# Stop the app started with `just up`
down:
    python tests/run_local.py down

# Follow the logs of the app started with `just up`
logs:
    python tests/run_local.py logs

# Smoke test in Dagger: build, start, check the web UI, login, ports, and that no service crashes
test:
    dagger call smoke-test

# Type-check and lint the Python code (mypy --strict, ruff)
lint:
    uv run mypy
    uv run ruff check

# SUPLA Cloud CLI, e.g. `just cloud --insecure devices` (see tools/supla_cloud.py)
[positional-arguments]
cloud *args:
    python tools/supla_cloud.py "$@"
