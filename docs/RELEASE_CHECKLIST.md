# Release checklist

Target: `v0.1.0`

## Local verification

```bash
python3 -m py_compile assistant/*.py
python3 -m unittest discover -s tests -v
for s in $(find . -name '*.sh'); do bash -n "$s"; done
docker compose config
./security/audit.sh
```

Optional live check on the target box:

```bash
./doctor.sh
```

## Boundary steps

These are operator-gated. Do not run them without an explicit commit/release
authorization.

```bash
git status --short        # review everything first
git add -A
git commit -m "release: prepare v0.1.0 public starter stack"
git tag -a v0.1.0 -m "v0.1.0"
git push origin main
git push origin v0.1.0
gh release create v0.1.0 --title "v0.1.0" --notes-file CHANGELOG.md
```
