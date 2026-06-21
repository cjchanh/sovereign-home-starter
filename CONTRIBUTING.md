# Contributing

This project is a small local-first starter stack. Keep contributions boring,
private by default, and runnable on a normal Linux box.

## Ground rules

- Do not add cloud dependencies, SaaS requirements, telemetry, or paid services.
- Do not expose camera, assistant, or Frigate services to the public internet.
- Do not commit real `.env`, `assistant/config.json`, `nvr/config.yml`, memory
  files, recordings, tokens, camera URLs, or screenshots from a real home.
- Prefer standard-library Python and shell over new dependencies.
- Keep changes scoped to the stack: assistant, NVR, Tailscale, backup, hardening,
  Reticulum, docs, and tests.

## Local checks

Run these before opening a pull request:

```bash
python3 -m py_compile assistant/*.py
python3 -m unittest discover -s tests -v
for s in $(find . -name '*.sh'); do bash -n "$s"; done
docker compose config
```

`./doctor.sh` checks live services on your box. It is useful before release, but
it is not required for every doc-only pull request.

## Pull requests

- Explain what changed and why.
- Say whether the change touches privacy, networking, credentials, or alerts.
- Include the exact checks you ran.
- Add or update tests when behavior changes.

## Security

If you find a security issue, do not open a public exploit walkthrough. Open a
minimal issue with the affected surface and reproduction shape, or contact the
maintainer through the profile link on GitHub.
