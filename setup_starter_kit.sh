#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-agrishield-new-project}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -e "$TARGET" ]; then
  echo "Target already exists: $TARGET" >&2
  exit 1
fi

mkdir -p "$TARGET/.agents/skills" "$TARGET/assets" "$TARGET/frontend" "$TARGET/backend" "$TARGET/edge" "$TARGET/docs" "$TARGET/tests"

cp -R "$SCRIPT_DIR/.agents/skills" "$TARGET/.agents/"
cp -R "$SCRIPT_DIR/assets/agents" "$TARGET/assets/"
cp "$SCRIPT_DIR/check_env.sh" "$TARGET/check_env.sh"
chmod +x "$TARGET/check_env.sh"

cat > "$TARGET/README.md" <<'EOF'
# New AgriTech Project

Generated from the AgriShield Starter Kit.

## Quick start

```bash
./check_env.sh
```

## Agent workflow

1. Use `agri-design` to write `docs/PRD.md`.
2. Use `agri-orchestrator` to split the PRD into tasks.
3. Use `agri-architect` for APIs, schemas and offline sync.
4. Use `crop-vision`, `telemetry-stream` and `voice-advisory` for specialized modules.
5. Use `agridoctor` before every demo or release.

## Suggested folders

- `frontend/` — mobile-first PWA or app
- `backend/` — API, database and AI integrations
- `edge/` — sensor/IoT/ML device code
- `docs/` — PRD, architecture, demo script and report
- `tests/` — unit and integration tests
EOF

cat > "$TARGET/docs/PRD.md" <<'EOF'
# Product Requirements Document

## Problem Statement

## Target Users

## Proposed Solution

## Core Features

## Offline Strategy

## AI/ML Strategy

## IoT/Telemetry Strategy

## Demo Flow

## Roadmap
EOF

cat > "$TARGET/docs/DEMO_SCRIPT.md" <<'EOF'
# Demo Script

## Pre-flight

- Open live app in incognito.
- Wake backend `/health`.
- Check AI/vision health endpoint if used.
- Prepare offline fallback story.

## Demo Flow

1. Problem hook
2. User onboarding
3. Main advisory dashboard
4. AI/sensor intelligence
5. Offline fallback
6. Impact and roadmap
EOF

cat > "$TARGET/.gitignore" <<'EOF'
node_modules/
dist/
build/
.venv/
.env
.env.*
__pycache__/
.pytest_cache/
.DS_Store
EOF

echo "✅ Created $TARGET"
echo "Next: cd $TARGET && ./check_env.sh"
