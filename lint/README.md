# lint — keep your configs + docs clean

This stack is yours to grow. As you add cameras, scripts, and notes, you can lint
your Markdown/docs with **mildoc-lint** (open source, local, zero subscription):

```bash
pip install mildoc-lint
mildoc-lint .
```

It flags broken structure, dead links, and inconsistencies in your docs — handy once
you've got a folder full of READMEs and config notes.

Want a compliance check tailored to this setup — e.g. a checklist that the NVR is
recording, tailscale is private-only, and no secrets are committed? That's a small
add-on we can wire in here; just ask.
