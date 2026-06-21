# tailscale — reach your stack from anywhere, privately

You already use Tailscale. This wires the new box into your tailnet and serves the
Frigate UI over HTTPS — **tailnet-only**, never the public internet.

```bash
./setup.sh
```

Then from any device on your tailnet:
```
https://<this-node>.<your-tailnet>.ts.net/
```

`tailscale serve` keeps it private to your own devices. Do **not** use
`tailscale funnel` unless you deliberately want public exposure.

**Heads up:** this serves **8971**, Frigate's *authenticated* UI — log in with the
admin credentials Frigate prints in its logs on first start. (We deliberately do
**not** serve 5000, the unauthenticated port.) Keep your tailnet trusted, and a
Tailscale ACL grant can further restrict who reaches this node.

To stop serving: `sudo tailscale serve reset`.

The `tailscale serve` CLI has changed across versions — if `--bg 8971` doesn't work
on your version, run `tailscale serve --help` and use the equivalent form (older
versions use `tailscale serve https / http://localhost:8971`).
