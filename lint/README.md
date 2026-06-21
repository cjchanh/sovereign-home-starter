# lint — keep your configs + docs clean

This stack is yours to grow. Once you've got a folder full of READMEs and config
notes, a linter keeps them consistent.

## Generic Markdown
Any Markdown linter works:
```bash
pipx install pymarkdownlnt     # or: npm i -g markdownlint-cli
pymarkdown scan .
```

## Compliance documents
If you ever need to lint *compliance* docs — CUI/PII markings, military
correspondence, readiness records — there's a local-first tool called
**mildoc-lint** (`pip install mildoc-lint`, Apache-2.0). It's purpose-built for
that, **not** a general Markdown linter, so reach for it only if compliance-doc
checking is something you actually do.

## Tailored checklist
Want a check tailored to this stack — NVR is actually recording, tailscale is
private-only, no secrets committed? That's a small add-on we can wire in here.
