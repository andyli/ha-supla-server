# Changelog

## 0.1.3

- The image is now one multi-arch image, `ghcr.io/andyli/supla_server`, for both amd64 and aarch64. Nothing else changed.

## 0.1.2

- Installs and updates download a pre-built image from GitHub Container Registry instead of compiling SUPLA on the device.

## 0.1.1

- The web UI is on port 4433 by default instead of 443. Installed apps keep their port.
- `host_address` no longer needs the port: the app adds the web UI's port itself. An address with a port still works.
- The port settings warn that devices and the SUPLA apps always use 2016 and 2015.

## 0.1.0

- First version: SUPLA Cloud 26.05.01, supla-server and supla-scheduler 26.05, MariaDB 11.8 (Debian trixie).
