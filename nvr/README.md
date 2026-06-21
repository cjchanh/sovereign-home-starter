# nvr — local AI camera recorder (Frigate)

[Frigate](https://docs.frigate.video) records your RTSP cameras and runs
person/vehicle detection **on this machine** — no cloud, no subscription.

## Bring it up
```bash
cp config.example.yml config.yml      # setup.sh does this
# edit config.yml: set each camera's IP + RTSP path
# (confirm a camera works first: ./check-camera.sh 'rtsp://user:pass@IP:554/stream2')
docker compose up -d                  # auth UI at http://localhost:8971
```

From the repo root, the equivalent command is:

```bash
docker compose up -d frigate
```

## Cameras (Tapo + most RTSP cams)
Tapo: app -> camera -> **Advanced Settings -> Camera Account** -> create a
user/password, enable RTSP. The URL is `rtsp://<user>:<pass>@<camera-ip>:554/stream1`
(HD) or `/stream2` (SD). Put the password in `../.env` as `FRIGATE_RTSP_PASSWORD`
and reference it in `config.yml` as `{FRIGATE_RTSP_PASSWORD}` (already wired in the
example).

> **Use only letters and digits in the camera-account password.** Frigate doesn't
> URL-encode it, so special characters (`@ : / # ? % &`) will break the stream.

Add cameras by copying the camera block. You're only limited by this box's
CPU / RAM / disk — not an 8-camera hub.

## Tips
- Detect on the **substream** (low-res) and record the **main** stream — already set
  up in the example. Match `detect: width/height` to your substream resolution.
- Many cameras or high CPU? Add a Google Coral TPU or enable iGPU hardware
  acceleration (uncomment the `devices:` line in `docker-compose.yml`). See docs.
- Recordings land in `./storage` (gitignored). Set retention to taste — and watch
  your disk: motion + alerts at 14-day retain on a busy camera can eat a lot of space.
  Lower the `days:` values, or point `./storage` at a big disk.
- **Sizing:** the CPU detector handles ~2–3 cameras at 5fps comfortably. More cameras
  or higher fps → use OpenVINO / a Coral TPU / an iGPU (see [TUNING.md](TUNING.md)).

## Advanced tuning
Zones, motion masks, and faster detectors (OpenVINO/Coral): see **[TUNING.md](TUNING.md)**.
