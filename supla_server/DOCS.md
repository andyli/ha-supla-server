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
   - **Host address**: the IP address or host name of your Home Assistant, as your phone sees it, e.g. `192.168.1.10`. The app adds the web UI's port (4433 by default) itself.
   - **Account email** and **Account password**: the app creates this SUPLA Cloud account when it starts.
4. Start the app and open the web UI (`https://192.168.1.10:4433`). The certificate is self-signed, so your browser will warn you the first time.
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
| `host_address` | Required. Address of this Home Assistant as SUPLA apps and browsers reach it. The app adds the web UI's port; to use another address or port, for example behind a reverse proxy, include it: `supla.example.com:443`. |
| `user_email`, `user_password` | Creates this account on start if it doesn't exist. Changing the password here later has no effect. |
| `accounts_registration` | Lets anyone who can reach the web UI sign up. Off by default. |
| `mqtt` | Publishes devices to the Mosquitto broker app. On by default. |
| `ssl_certfile`, `ssl_keyfile` | Certificate and key in `/ssl` for the web UI, e.g. `fullchain.pem` and `privkey.pem`. Leave empty for a self-signed certificate. |

## Network

| Container port | Default host port | Used by |
|---|---|---|
| 2016/tcp | 2016 | Devices and SUPLA mobile apps, TLS. Devices don't check the certificate. |
| 2015/tcp | off | Old devices without TLS. |
| 443/tcp | 4433 | SUPLA Cloud web UI and API, HTTPS. |
| 80/tcp | off | SUPLA Cloud over plain HTTP. |

Don't change 2016 or 2015: devices and the SUPLA mobile apps always connect to those ports, and neither lets you set another. The web UI port can be anything.

## Internet access

The app works without Internet access. Devices, the SUPLA mobile apps, the web UI and MQTT only need your local network.

It does contact SUPLA's servers by itself, even if you never use an online feature. This section lists what it contacts, from reading the source of SUPLA Cloud 26.05.01 and supla-server 26.05, so you can decide whether to block it.

### What it contacts without you doing anything

All three go to `autodiscover.supla.org`. They send the SUPLA Cloud version, not your account, devices or data.

| Part | Address | How often | What for |
|---|---|---|---|
| supla-server | `https://autodiscover.supla.org/service-tokens` | Every minute from start (every hour once SUPLA refuses) | Tokens for push notifications and Google Home. SUPLA gives none to servers not registered with it, and this app doesn't register. |
| SUPLA Cloud | `https://autodiscover.supla.org/energy-price-forecast` | Every 5 minutes | Polish energy market prices, for "energy price forecast" channels. |
| SUPLA Cloud | `https://autodiscover.supla.org/esp-updates` | Every 2 hours | The list of firmware updates for older ESP-based devices. |

### What it contacts only when you use a feature

| Feature | Address | Sends |
|---|---|---|
| OpenWeather channels | `autodiscover.supla.org` | The city, every 5 minutes while such a channel exists. |
| Unlocking a locked device | `autodiscover.supla.org` | The device's name and ID, and the email addresses of its owner and of the person unlocking it. |
| Signing in to a third-party app that SUPLA Cloud doesn't know yet (OAuth) | `autodiscover.supla.org` | The app's client ID. |
| State webhooks, set up by a third-party app | The address the app gave | Channel states. |
| Push notifications, Alexa, Google Home | SUPLA's push servers, Amazon, Google | Nothing: these need the server registered with SUPLA, so they never start. |
| Email | None | Nothing: the app sends no email. |

### What you lose by blocking it

Energy price forecast channels, OpenWeather channels, device unlocking, and the firmware update list for older ESP devices. Push notifications, Alexa and Google Home don't work in this app either way.

### How to block it

There is no option in the app for this yet. Two things to know if you block it outside the app, for example on your router or DNS server:

- **Block it by name, not by Home Assistant's address.** The app's traffic leaves from Home Assistant's own IP address, so a rule for that address blocks Home Assistant too. Blocking `autodiscover.supla.org` in a DNS blocker such as Pi-hole or AdGuard Home stops all the traffic listed above, except webhooks you set up.
- **Make blocked connections fail at once.** If you block with a firewall, reject the connection instead of dropping it. SUPLA Cloud sets no time limit on its requests, so with a dropped connection each one waits about 5 minutes. That holds up the app's other periodic jobs, such as running schedules. A DNS blocker fails at once.

Blocking the app doesn't stop your devices or phones from reaching the Internet. The SUPLA mobile app contacts `autodiscover.supla.org` when **Auto** is on (see [Connecting the SUPLA mobile app](#connecting-the-supla-mobile-app)). Devices download firmware from `updates.supla.org` when you update them.

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
