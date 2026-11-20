# SUPLA Server

This app runs your own SUPLA server on Home Assistant. It includes:

- **SUPLA Server** (`supla-server`, `supla-scheduler`): devices and the SUPLA mobile apps connect to it.
- **SUPLA Cloud**: the web UI and API for managing your account, devices, schedules and scenes.
- **MariaDB**: the database for both. It runs inside the app and is not shared with other apps.

With the Mosquitto broker app installed, devices show up in Home Assistant through MQTT discovery. You don't need the SUPLA integration.

## Installation

1. Install the **Mosquitto broker** app, if you haven't already, and set up the MQTT integration.
2. Install this app.
3. On the **Configuration** tab, set:
   - **Host address**: the IP address or host name of your Home Assistant, as your phone sees it, e.g. `192.168.1.10`. If you changed the HTTPS port below, add it: `192.168.1.10:8443`.
   - **Account email** and **Account password**: the app creates this SUPLA Cloud account when it starts.
4. Start the app and open the web UI. The certificate is self-signed, so your browser will warn you the first time.
5. Log in with the account from step 3.

## Moving a device to this server

Each SUPLA device stores a server address and an account email. To move a device here:

1. In SUPLA Cloud on this app, open **My SUPLA** and turn on **I/O devices registration**. It switches itself off after a while. A new account starts with it on for 7 days.
2. Put the device into configuration mode. This is usually a long press on its button; see the device manual. The device opens a Wi-Fi access point.
3. Connect to that access point and open the device's page, usually `http://192.168.4.1`.
4. Set **Server** to your Home Assistant's address (IP only, no port) and **E-mail** to the account email from the app configuration. Keep your Wi-Fi settings, then save.
5. The device restarts and shows up in SUPLA Cloud and, a few seconds later, in Home Assistant.

A device that moves gets a new ID on this server, so Home Assistant creates new entities for it. Update your automations and dashboards to the new entities.

## MQTT

When **Publish to MQTT** is on and the Mosquitto broker app is installed, supla-server publishes to it:

- `supla/<account id>/...`: device and channel state, and topics to control channels.
- `homeassistant/...`: MQTT discovery, so Home Assistant creates the entities.

The app also turns on MQTT for every SUPLA Cloud account. You can't turn it off per account here.

If you used to bridge your Mosquitto broker to SUPLA's MQTT broker (`mqttXXX.supla.org`), remove that bridge once all devices have moved. Otherwise both send messages under the same `homeassistant/` topics.

## Configuration

| Option | Description |
|---|---|
| `host_address` | Required. Address of this Home Assistant as SUPLA apps and browsers reach it. |
| `user_email`, `user_password` | Creates this account on start if it doesn't exist. Changing the password here later has no effect. |
| `accounts_registration` | Lets anyone who can reach the web UI sign up. Off by default. |
| `mqtt` | Publishes devices to the Mosquitto broker app. On by default. |
| `ssl_certfile`, `ssl_keyfile` | Certificate and key in `/ssl` for the web UI, e.g. `fullchain.pem` and `privkey.pem`. Leave empty for a self-signed certificate. |

## Network

| Port | Used by |
|---|---|
| 2016/tcp | Devices and SUPLA mobile apps, TLS. Devices don't check the certificate. |
| 2015/tcp | Old devices without TLS. Off by default. |
| 443/tcp | SUPLA Cloud web UI and API, HTTPS. |
| 80/tcp | SUPLA Cloud over plain HTTP. Off by default. |

Devices always connect to 2016 or 2015, so don't change those ports.

## Backups

Home Assistant backups include the app's data. Before each backup the app writes a dump of the database to `/data/backup/supla.sql.gz`. The backup contains this dump, not the raw database files. When you restore a backup, the app rebuilds the database from the dump on its next start.

## SUPLA Cloud console

To run SUPLA Cloud console commands, open a shell in the app's container (for example with the "Advanced SSH & Web Terminal" app with protection mode off) and run:

```sh
docker exec -it addon_<slug> supla-console list supla
```

## Known limitations

- No email: SUPLA Cloud can't send mail, so password reset by email doesn't work.
- Not connected to SUPLA's services: push notifications, Alexa and Google Home through SUPLA don't work.
- The web UI doesn't work through Home Assistant ingress, so it opens on its own port.
