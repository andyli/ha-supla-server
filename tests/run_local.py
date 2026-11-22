#!/usr/bin/env python3
"""Build and run the app with plain Docker, next to a stub Supervisor and a Mosquitto broker.

Usage: tests/run_local.py [up|down|logs]   (or `just up`, `just down`, `just logs`)
  Cloud UI: https://localhost:8443  (account from tests/options.json)
  Devices:  localhost:2016 (TLS), localhost:2015 (plain)
The app's /data is tests/.data/, or the DATA environment variable.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("DATA", ROOT / "tests" / ".data")).resolve()
NET = "supla-test"
IMAGE = "local/supla_server:dev"
MOSQUITTO_IMAGE = "eclipse-mosquitto:2.0.22"
PYTHON_IMAGE = "python:3.13-alpine"
CONTAINERS = ["supla-app", "supla-supervisor", "supla-mqtt"]


def docker(*args: str, check: bool = True, quiet: bool = False) -> subprocess.CompletedProcess[bytes]:
    out = subprocess.DEVNULL if quiet else None
    return subprocess.run(["docker", *args], check=check, stdout=out, stderr=out)


def down() -> None:
    docker("rm", "-f", *CONTAINERS, check=False, quiet=True)
    docker("network", "rm", NET, check=False, quiet=True)


def up() -> None:
    down()
    docker("build", "-t", IMAGE, str(ROOT / "supla_server"))
    DATA.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "tests" / "options.json", DATA / "options.json")
    # Dual-stack, like Home Assistant's own network, so IPv6 problems show up here too.
    docker("network", "create", "--ipv6", "--subnet", "fd0c:ac1e:2200::/64", NET, quiet=True)
    docker(
        "run", "-d", "--name", "supla-mqtt", "--network", NET, MOSQUITTO_IMAGE,
        "sh", "-c",
        'printf "listener 1883\\nallow_anonymous true\\n" >/mosquitto/config/mosquitto.conf'
        " && exec mosquitto -c /mosquitto/config/mosquitto.conf",
        quiet=True,
    )
    docker(
        "run", "-d", "--name", "supla-supervisor", "--network", NET, "--network-alias", "supervisor",
        "-e", "MQTT_HOST=supla-mqtt",
        "-v", f"{ROOT / 'tests' / 'mock_supervisor.py'}:/mock.py:ro",
        "-v", f"{DATA / 'options.json'}:/options.json:ro",
        PYTHON_IMAGE, "python", "-u", "/mock.py",
        quiet=True,
    )
    for _ in range(60):
        probe = ("exec", "supla-supervisor", "wget", "-qO-", "http://127.0.0.1/addons/self/info")
        if docker(*probe, check=False, quiet=True).returncode == 0:
            break
        time.sleep(0.5)
    else:
        sys.exit("the stub Supervisor did not start; see: docker logs supla-supervisor")
    docker(
        "run", "-d", "--name", "supla-app", "--network", NET, "--cap-add", "NET_ADMIN", "-e", "SUPERVISOR_TOKEN=test",
        "-v", f"{DATA}:/data", "-p", "8443:443", "-p", "2016:2016", "-p", "2015:2015", IMAGE,
        quiet=True,
    )
    print("started; follow with: just logs")


def logs() -> NoReturn:
    os.execvp("docker", ["docker", "logs", "-f", "supla-app"])


def main() -> None:
    commands: dict[str, Callable[[], None]] = {"up": up, "down": down, "logs": logs}
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("command", nargs="?", default="up", choices=commands)
    commands[parser.parse_args().command]()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
