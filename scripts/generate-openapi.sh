#!/usr/bin/env bash
set -euo pipefail

# Generate OpenAPI spec from Django/DRF
# Adjust this command if you use a different generator.
if command -v python3 >/dev/null 2>&1; then
  python3 manage.py spectacular --file openapi.yaml
else
  python manage.py spectacular --file openapi.yaml
fi
