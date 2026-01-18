#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="${FRONTEND_DIR:-$BACKEND_DIR/../affordable-gadgets-frontend}"

echo "==> Generating OpenAPI schema in backend"
"$SCRIPT_DIR/generate-openapi.sh"

if [ ! -d "$FRONTEND_DIR" ]; then
  echo "Frontend directory not found: $FRONTEND_DIR"
  echo "Set FRONTEND_DIR to the correct path and re-run."
  exit 1
fi

echo "==> Syncing openapi.yaml to frontend"
cp "$BACKEND_DIR/openapi.yaml" "$FRONTEND_DIR/openapi.yaml"

echo "==> Regenerating API client in frontend"
npm --prefix "$FRONTEND_DIR/packages/api-client" run generate
npm --prefix "$FRONTEND_DIR/packages/api-client" run build

echo "==> Done"
