"""Smoke test, run inside the app container as its main command: /init python3 -u /smoke.py

s6-overlay runs it once every service has started, so init-supla and init-cloud
have already succeeded (if they fail, s6 stops the container instead).
The container exits with this script's exit code. Run it with `just test`.

The app image has no Python; the Dagger test installs Debian's python3 (3.13)
into the test container only. Standard library only.
"""

import functools
import json
import os
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable

SERVICES = ["mariadb", "apache", "supla-server", "supla-scheduler", "cloud-tasks", "cloud-messenger"]
STABLE_SECONDS = int(os.environ.get("STABLE_SECONDS", "30"))
OPTIONS = "/data/options.json"
BASE_URL = "https://localhost"
# The app's default certificate is self-signed.
TLS = ssl._create_unverified_context()

failures: list[str] = []


def ok(msg: str) -> None:
    print(f"[smoke] ok: {msg}")


def fail(msg: str) -> None:
    failures.append(msg)
    print(f"[smoke] FAIL: {msg}")


def retry(seconds: float, check: Callable[[], object]) -> Exception | None:
    """Call check() until it doesn't raise or time runs out. Returns the last error, or None."""
    end = time.monotonic() + seconds
    while True:
        try:
            check()
            return None
        except Exception as e:  # noqa: BLE001 - any error means "not yet"
            if time.monotonic() >= end:
                return e
            time.sleep(2)


def get_web_ui() -> None:
    urllib.request.urlopen(f"{BASE_URL}/", context=TLS, timeout=5).close()


def login(email: str, password: str) -> str:
    """Return an access token for the account, or raise."""
    req = urllib.request.Request(
        f"{BASE_URL}/api/webapp-auth",
        data=json.dumps({"username": email, "password": password}).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, context=TLS, timeout=10) as resp:
            token: str = json.load(resp)["access_token"]
            return token
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')}") from None


def connect(port: int) -> None:
    socket.create_connection(("127.0.0.1", port), timeout=2).close()


def check_internet_blocked() -> None:
    """With internet_access off, connections to the Internet must be refused at once, not hang."""
    start = time.monotonic()
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=10).close()
        fail("connected to 1.1.1.1:443 although Internet access is blocked")
    except ConnectionRefusedError:
        if (secs := time.monotonic() - start) < 2:
            ok("connection to 1.1.1.1:443 refused")
        else:
            fail(f"connection to 1.1.1.1:443 refused only after {secs:.0f}s")
    except OSError as e:
        fail(f"connection to 1.1.1.1:443: {e!r}, expected it to be refused")

    # SUPLA Cloud's HTTP client has no timeout: a request to SUPLA's servers must fail, and quickly.
    start = time.monotonic()
    result = subprocess.run(
        ["/command/s6-setuidgid", "www-data", "php", "bin/console", "supla:cyclic:energy-price-forecast-fetch"],
        cwd="/var/www/cloud", check=False, capture_output=True, text=True, timeout=120,
    )
    secs = time.monotonic() - start
    if result.returncode == 0:
        fail("SUPLA Cloud fetched the energy price forecast although Internet access is blocked")
    elif secs > 20:
        fail(f"SUPLA Cloud's request to autodiscover.supla.org failed only after {secs:.0f}s")
    else:
        ok(f"SUPLA Cloud's request to autodiscover.supla.org failed in {secs:.1f}s")


def service_states() -> dict[str, tuple[bool, str | None]]:
    """{service: (up, pid)} for each long-running service, from s6-svstat."""
    states: dict[str, tuple[bool, str | None]] = {}
    for name in SERVICES:
        out = subprocess.run(
            ["/command/s6-svstat", "-o", "up,pid", f"/run/service/{name}"],
            check=False, capture_output=True, text=True,
        ).stdout.split()
        states[name] = (out[0] == "true", out[1]) if len(out) == 2 else (False, None)
    return states


def main() -> int:
    print("[smoke] services started; running checks")

    if err := retry(60, get_web_ui):
        fail(f"web UI on 443: {err}")
    else:
        ok("web UI answers on 443")

    with open(OPTIONS) as f:
        options = json.load(f)
    email = options.get("user_email")
    if email:
        try:
            login(email, options.get("user_password", ""))
            ok(f"login as {email}")
        except Exception as e:  # noqa: BLE001
            fail(f"login as {email}: {e}")

    for port in (2016, 2015):
        if err := retry(30, functools.partial(connect, port)):
            fail(f"supla-server on {port}: {err}")
        else:
            ok(f"supla-server listens on {port}")

    if not options.get("internet_access", False):
        check_internet_blocked()

    # A service that crashed and was restarted by s6 has a new pid.
    before = service_states()
    time.sleep(STABLE_SECONDS)
    for name, (up, pid) in service_states().items():
        if not up:
            fail(f"{name} is down")
        elif before[name] != (up, pid):
            fail(f"{name} restarted during the last {STABLE_SECONDS}s")
        else:
            ok(f"{name} running")

    print("[smoke] FAILED" if failures else "[smoke] PASSED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
