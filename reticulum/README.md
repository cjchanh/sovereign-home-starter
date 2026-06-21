# reticulum — sovereign mesh networking node

[Reticulum](https://reticulum.network) is a crypto-native networking stack with
no central authority, no DNS, no CA, and no subscription. Every node has a
cryptographic identity derived from its keys — not an IP address or a username.
It runs over anything: TCP/IP today, LoRa radio tomorrow, serial lines, I2P,
or packet radio.

This is a **node starter** — install, config, daemon, honest docs. It does not
include a messaging or application layer (see nomadnet / LXMF for that).

## Setup

```bash
./reticulum/setup.sh
```

This installs `rns` via pip and seeds `~/.reticulum/config` from
`config.example` if no config exists yet. It will never overwrite an existing
config — your node identity lives there.

## Start the daemon

```bash
rnsd            # foreground — good for first run, watch the log
rnsd --daemon   # background
rnstatus        # shows interfaces, announce rate, reachable destinations
```

The default config connects to the public Reticulum testnet over TCP so the
node works immediately on your existing network. Edit `~/.reticulum/config` to
add or change interfaces.

## Optional: nomadnet

A terminal browser and messenger for the Reticulum network. Single-user,
local-first, no accounts.

```bash
pip3 install nomadnet
nomadnet
```

## Optional: run as a systemd service

```bash
cp reticulum/rnsd.service.example ~/.config/systemd/user/rnsd.service
systemctl --user daemon-reload
systemctl --user enable --now rnsd
systemctl --user status rnsd
```

## LoRa / RNode — the long-range future

`config.example` includes a commented-out `RNodeInterface` block. An RNode is
an open-source LoRa radio (LilyGO TTGO, Heltec, RAK modules) flashed with
[RNode firmware](https://github.com/markqvist/RNode_Firmware). Once you have
the hardware:

1. Flash it with `rnodeconf` (ships with rns): `rnodeconf /dev/ttyUSB0 --autoinstall`
2. Uncomment the `[[RNode LoRa]]` block in `~/.reticulum/config`.
3. Set the correct serial port, frequency (legal for your region), and bandwidth.
4. Restart `rnsd`.

**Honest bandwidth note:** LoRa is a few kbps at best. It is excellent for
sensor readings, telemetry, and short messages across acreage or between
off-grid buildings with no WiFi infrastructure — especially on solar power.
It is not for video. Your Frigate cameras stay on WiFi; LoRa is for everything
that works at low data rates.

## Your node identity

`~/.reticulum/` holds the node's private identity (keys). RNS generates it on
first run. It lives in your home directory, outside this repo, so it is never
committed — keep it private and backed up. If you lose it, the node gets a new
identity and peers that knew the old one will not recognize it.
