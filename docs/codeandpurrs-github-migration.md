# CodeAndPurrs GitHub Migration

The new GitHub repository is:

```text
https://github.com/NekoAshenUwU/CodeAndPurrs
```

Use `scripts/migrate-codeandpurrs-to-github.sh` to copy the current CodeAndPurrs project brief into that clean repository without bringing over the unrelated `usage-bridge` Android project.


## If you just want the simple version

Use the short Chinese copy-paste guide instead:

```text
docs/codeandpurrs-simple-move-guide.md
```

## What gets moved

- `docs/codeandpurrs-product-brief.md`
- A small `README.md` that points to the product brief
- A starter `.gitignore` for the future frontend/backend project

## How to run on a machine with GitHub access

```bash
bash scripts/migrate-codeandpurrs-to-github.sh /tmp/CodeAndPurrs
cd /tmp/CodeAndPurrs
git push origin HEAD
```

If GitHub asks for credentials, sign in with a token or GitHub CLI. The script intentionally does not store credentials.

## Why this is separate

`Veyron-Solace` still contains older work like `usage-bridge`, while `CodeAndPurrs` should start clean as its own web app repository.
