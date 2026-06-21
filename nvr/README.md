# nvr — local AI camera recorder (Frigate)

[Frigate](https://docs.frigate.video) records your RTSP cameras and runs
person/vehicle detection **on this machine** — no cloud, no subscription.

## Bring it up
```bash
cp config.example.yml config.yml      # setup.sh does this
# edit config.yml: set each camera's IP + RTSP path
# (confirm a camera works first: ./check-camera.sh 'rtsp://user:pass@IP:554/stream2')
docker compose up -d                  # UI at http://localhost:5000
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
- Recordings land in `./storage` (gitignored). Set `retain.days` to taste.

## Advanced tuning
Zones, motion masks, and faster detectors (OpenVINO/Coral): see **[TUNING.md](TUNING.md)**.
