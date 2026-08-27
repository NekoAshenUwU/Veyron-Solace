#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${CODEANDPURRS_REPO_URL:-https://github.com/NekoAshenUwU/CodeAndPurrs.git}"
TARGET_DIR="${1:-/tmp/CodeAndPurrs}"
SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$SOURCE_ROOT/docs/codeandpurrs-product-brief.md" ]]; then
  echo "Missing docs/codeandpurrs-product-brief.md in $SOURCE_ROOT" >&2
  exit 1
fi

if [[ ! -d "$TARGET_DIR/.git" ]]; then
  rm -rf "$TARGET_DIR"
  git clone "$REPO_URL" "$TARGET_DIR"
fi

mkdir -p "$TARGET_DIR/docs"
cp "$SOURCE_ROOT/docs/codeandpurrs-product-brief.md" "$TARGET_DIR/docs/codeandpurrs-product-brief.md"

cat > "$TARGET_DIR/README.md" <<'README_EOF'
# CodeAndPurrs

CodeAndPurrs is a private, pastel, cat-themed AI companion home for chat, voice, stickers, virtual red packets, vault memories, model switching, local archives, and export/migration.

Start with the product brief:

- [`docs/codeandpurrs-product-brief.md`](docs/codeandpurrs-product-brief.md)
README_EOF

cat > "$TARGET_DIR/.gitignore" <<'GITIGNORE_EOF'
node_modules/
dist/
build/
.env
.env.*
!.env.example
.DS_Store
*.log
GITIGNORE_EOF

cd "$TARGET_DIR"
git add README.md .gitignore docs/codeandpurrs-product-brief.md
if git diff --cached --quiet; then
  echo "No CodeAndPurrs migration changes to commit."
else
  git commit -m "Add CodeAndPurrs project brief"
fi

echo "Migration prepared in: $TARGET_DIR"
echo "To push when GitHub auth is available:"
echo "  cd '$TARGET_DIR' && git push origin HEAD"
