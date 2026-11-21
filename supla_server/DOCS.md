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

## Connecting the SUPLA mobile app

In the SUPLA app, add an account (or edit one) with **Advanced** on:

- **E-mail address**: the account email from the app configuration.
- **Server address**: your Home Assistant's address only, e.g. `192.168.1.10`. No `https://` and no port: the app connects to supla-server on port 2016, not to the web UI. With a URL here, the app shows "Host not found".
- **Auto**: off. Auto looks the email up on `autodiscover.supla.org`, which only knows SUPLA's own servers.

A new account accepts new phones and devices for its first 7 days. After that, turn on **Client registration** on the **Smartphones** page before adding a phone, or **I/O devices registration** on the **My SUPLA** page before adding a device.

On Android 16 and later, apps need the **Nearby devices** (local network) permission to reach addresses on your home network. Without it the SUPLA app can't connect, and browsers fail with `ERR_TOO_MANY_RETRIES` when opening the web UI. Allow it in **Settings → Apps → *the app* → Permissions**.

## Moving a device to this server

Each SUPLA device stores a server address and an account email. Moving it here gives it a new ID, so Home Assistant creates a new entity for it.

1. Connect the SUPLA app to this server (see above).
2. Reset the device's settings: put it into configuration mode (usually a long press on its button; see the device manual).
3. In the SUPLA app, add the device with **Add device**. The app connects to the device's Wi-Fi access point and writes your Wi-Fi settings, this server's address and your account email to it.
4. The device restarts and connects. It shows up in SUPLA Cloud and, a few seconds later, in Home Assistant.

You can also set the server by hand: in configuration mode, connect to the device's access point, open its page (usually `http://192.168.4.1`), and set **Server** (address only, no port) and **E-mail**.

Then, in SUPLA Cloud, give the channel the name it had before. Home Assistant updates the entity's name from MQTT discovery, but not its entity ID. To keep automations and dashboards working, rename the old entity's ID out of the way and give its ID to the new entity (**Settings → Entities**), and set the device's area again.

## MQTT

When **Publish to MQTT** is on and the Mosquitto broker app is installed, supla-server publishes to it:

- `supla/<account id>/...`: device and channel state, and topics to control channels.
- `homeassistant/...`: MQTT discovery, so Home Assistant creates the entities.

The app also turns on MQTT for every SUPLA Cloud account. You can't turn it off per account here.

If you used to bridge your Mosquitto broker to SUPLA's MQTT broker (`mqttXXX.supla.org`), the moved devices keep an unavailable copy in Home Assistant that comes from the bridge. Deleting that copy in Home Assistant doesn't help: the bridge brings its discovery message back. Delete the device from your cloud.supla.org account instead, or remove the bridge once all devices have moved.

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
