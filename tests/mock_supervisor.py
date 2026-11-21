"""Minimal stand-in for the Supervisor API, for running the app with plain Docker.

Serves the app options from /data/options.json (mounted at /options.json) and,
when MQTT_HOST is set, the `mqtt` service.
"""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, data):
        body = json.dumps({"result": "ok" if code == 200 else "error", "data": data}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/addons/self/options/config":
            with open("/options.json") as f:
                return self._send(200, json.load(f))
        if self.path == "/services/mqtt" and os.environ.get("MQTT_HOST"):
            return self._send(200, {
                "host": os.environ["MQTT_HOST"], "port": 1883, "ssl": False,
                "username": "supla", "password": "secret", "protocol": "3.1.1",
            })
        if self.path == "/addons/self/info":
            return self._send(200, {"slug": "supla_server", "version": "dev",
                                    "network": {"2016/tcp": 2016, "443/tcp": 8443}})
        self._send(404, {})


HTTPServer(("0.0.0.0", 80), Handler).serve_forever()
