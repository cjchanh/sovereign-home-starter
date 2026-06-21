# backup — mirror the stack to another box (e.g. your Pi)

`backup.sh` rsyncs your config + assistant memory (and, opt-in, the camera
recordings) to another machine on your tailnet over ssh. Idempotent — it copies
only what changed, and it never deletes on the far side (no `--delete`).

```bash
./backup/backup.sh pi@raspberrypi                 # configs + assistant memory
WITH_RECORDINGS=1 ./backup/backup.sh pi@raspberrypi  # also mirror NVR video (large)
```

The host can also come from the environment:
```bash
TAILSCALE_BACKUP_HOST=pi@raspberrypi ./backup/backup.sh
```

Lands at `~/sovereign-home-backup/` on the target (`state/` + `recordings/`).
Needs `rsync` on both ends and ssh access (Tailscale makes this easy).
