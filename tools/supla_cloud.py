#!/usr/bin/env python3
"""Small client for a SUPLA Cloud instance, e.g. the one in this app.

List devices and their channels, and rename (set the caption of) a channel.
supla-server republishes the MQTT discovery after a rename, so Home Assistant
picks up the new name. The entity is unavailable for a few seconds meanwhile.

Usage:
  supla_cloud.py [options] devices
  supla_cloud.py [options] rename-channel CHANNEL_ID CAPTION

Options (or environment variables):
  --url URL        SUPLA Cloud address, e.g. https://192.168.1.10   (SUPLA_URL)
  --email EMAIL    account email                                   (SUPLA_EMAIL)
  --insecure       don't check the certificate (the app's default one is self-signed)
The password is read from SUPLA_PASSWORD, or asked for. It is never printed.

Only the Python standard library is needed.
"""
import argparse
import getpass
import json
import os
import ssl
import sys
import urllib.error
import urllib.request


class Cloud:
    def __init__(self, url, email, password, insecure):
        self.base = url.rstrip("/") + "/api"
        self.ctx = ssl._create_unverified_context() if insecure else ssl.create_default_context()
        self.token = self._call("POST", "/webapp-auth", {"username": email, "password": password})["access_token"]

    def _call(self, method, path, body=None):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if getattr(self, "token", None):
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(
            self.base + path, method=method, headers=headers,
            data=None if body is None else json.dumps(body).encode())
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=30) as r:
                raw = r.read().decode()
        except urllib.error.HTTPError as e:
            sys.exit(f"{method} {path}: HTTP {e.code}: {e.read().decode()[:300]}")
        return json.loads(raw) if raw else None

    def devices(self):
        return self._call("GET", "/v3/iodevices?include=channels,connected")

    def rename_channel(self, channel_id, caption):
        # safe=true: refuse changes that would delete data (rules, history, etc.)
        return self._call("PUT", f"/v3/channels/{channel_id}?safe=true", {"caption": caption})


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--url", default=os.environ.get("SUPLA_URL"))
    p.add_argument("--email", default=os.environ.get("SUPLA_EMAIL"))
    p.add_argument("--insecure", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("devices", help="list devices and their channels")
    r = sub.add_parser("rename-channel", help="set a channel's caption")
    r.add_argument("channel_id", type=int)
    r.add_argument("caption")
    a = p.parse_args()

    if not a.url or not a.email:
        p.error("--url and --email (or SUPLA_URL and SUPLA_EMAIL) are required")
    password = os.environ.get("SUPLA_PASSWORD") or getpass.getpass(f"SUPLA password for {a.email}: ")
    cloud = Cloud(a.url, a.email, password, a.insecure)

    if a.cmd == "devices":
        for d in cloud.devices():
            state = "online" if d.get("connected") else "offline"
            print(f"device {d['id']}: {d.get('name')!r} ({state}, comment={d.get('comment')!r})")
            for c in d.get("channels") or []:
                fn = (c.get("function") or {}).get("name")
                print(f"  channel {c['id']}: {fn} caption={c.get('caption')!r}")
    elif a.cmd == "rename-channel":
        res = cloud.rename_channel(a.channel_id, a.caption)
        print(f"channel {a.channel_id}: caption={res.get('caption')!r}")


if __name__ == "__main__":
    main()
