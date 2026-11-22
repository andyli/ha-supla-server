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
| `internet_access` | Lets the app reach the Internet. Off by default: see [Internet access](#internet-access). |
| `ssl_certfile`, `ssl_keyfile` | Certificate and key in `/ssl` for the web UI, e.g. `fullchain.pem` and `privkey.pem`. Leave empty for a self-signed certificate. |

## Network

| Container port | Default host port | Used by |
|---|---|---|
| 2016/tcp | 2016 | Devices and SUPLA mobile apps, TLS. Devices don't check the certificate. |
| 2015/tcp | off | Old devices without TLS. |
| 443/tcp | 4433 | SUPLA Cloud web UI and API, HTTPS. |
| 80/tcp | off | SUPLA Cloud over plain HTTP. |

Don't change 2016 or 2015: devices and the SUPLA mobile apps always connect to those ports, and neither lets you set another. The web UI port can be anything.

With 2015 off, SUPLA Cloud's server status reports the server as down: `/api/server-status` answers "503" with `{"status":"CANNOT_CONNECT_2015: Connection refused (111)"}`, and `/api/v2.4.0/server-info` has the same text in `serverStatus`. The check connects to `host_address` on port 2015 as well as 2016. Devices connect to supla-server directly and aren't affected.

## Internet access

The app blocks its own Internet access: it can only reach your local network. Devices, the SUPLA mobile apps, the web UI and MQTT only need your local network, so they work as usual. To let the app reach the Internet, turn on `internet_access`.

### How the block works

The app installs a firewall rule in its own container when it starts. It doesn't affect Home Assistant or other apps.

- New connections to public addresses are refused at once.
- These stay allowed: private addresses (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, link-local, IPv6 `fc00::/7`), which include Home Assistant's own services and your local network; IPv6 link-local multicast, which IPv6 needs to find other devices on the network; the address in `host_address`; and replies to connections that come in, so a phone away from home can still connect through a port forward.
- Name lookups still go through Home Assistant's DNS. The app can look up `autodiscover.supla.org`, but the connection after the lookup is refused.

The refused connections would fill the app log with errors: supla-server's request for tokens every minute, and SUPLA Cloud's energy price fetch every 5 minutes and ESP update fetch every 2 hours. The app leaves exactly those errors out of its log while the block is on. Other errors still show, including refused connections for features you set up, such as OpenWeather channels.

To install the rule, the app needs the `NET_ADMIN` privilege, so Home Assistant shows it on the app's page and lowers the app's security rating. The app uses it for nothing else. If the rule can't be installed, the app doesn't start, instead of running without it.

### What the app contacts with Internet access on

This is from reading the source of SUPLA Cloud 26.05.01 and supla-server 26.05. SUPLA's server answers "403 Forbidden" to servers not registered with it, and this app doesn't register, so nothing below that goes to SUPLA works in this app, even with Internet access on.

These happen without you doing anything. All three go to `autodiscover.supla.org`, and send the SUPLA Cloud version, not your account, devices or data.

| Part | Address | How often | What for |
|---|---|---|---|
| supla-server | `https://autodiscover.supla.org/service-tokens` | Every hour (every minute while blocked) | Tokens for push notifications and Google Home. |
| SUPLA Cloud | `https://autodiscover.supla.org/energy-price-forecast` | Every 5 minutes | Polish energy market prices, for "energy price forecast" channels. |
| SUPLA Cloud | `https://autodiscover.supla.org/esp-updates` | Every 2 hours | The list of firmware updates for older ESP-based devices. |

These happen only when you use a feature:

| Feature | Address | Sends |
|---|---|---|
| OpenWeather channels | `autodiscover.supla.org` | The city, every 5 minutes while such a channel exists. |
| Unlocking a locked device | `autodiscover.supla.org` | The device's name and ID, and the email addresses of its owner and of the person unlocking it. |
| Signing in to a third-party app that SUPLA Cloud doesn't know yet (OAuth) | `autodiscover.supla.org` | The app's client ID. |
| State webhooks, set up by a third-party app | The address the app gave | Channel states. |
| Push notifications, Alexa, Google Home | SUPLA's push servers, Amazon, Google | Nothing: these need the server registered with SUPLA, so they never start. |
| Email | None | Nothing: the app sends no email. |

### What the block costs

Only state webhooks to addresses on the Internet. The other features above don't work in this app either way.

### Your devices and phones

The block covers only the app. The SUPLA mobile app contacts `autodiscover.supla.org` when **Auto** is on (see [Connecting the SUPLA mobile app](#connecting-the-supla-mobile-app)). Devices download firmware from `updates.supla.org` when you update them.

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
