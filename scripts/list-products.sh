#!/usr/bin/env bash
# list-products.sh — Print all products with id, slug, name, and stock.
#
# Usage:
#   ./scripts/list-products.sh
#   ./scripts/list-products.sh --in-stock          # only available_stock > 0
#   ./scripts/list-products.sh --published         # only is_published=true (default)
#   ./scripts/list-products.sh --all               # include unpublished
#   ./scripts/list-products.sh --csv               # CSV instead of table
#
# Env overrides:
#   API_BASE=https://api.affordable-gadgetske.com
#   API_USERNAME=admin
#   API_PASSWORD=6foot7foot

set -euo pipefail

API_BASE="${API_BASE:-https://api.affordable-gadgetske.com}"
API_USERNAME="${API_USERNAME:-admin}"
API_PASSWORD="${API_PASSWORD:-6foot7foot}"

IN_STOCK=0
PUBLISHED_ONLY=1
CSV=0

usage() {
  sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --in-stock) IN_STOCK=1; shift ;;
    --published) PUBLISHED_ONLY=1; shift ;;
    --all) PUBLISHED_ONLY=0; shift ;;
    --csv) CSV=1; shift ;;
    -h|--help) usage ;;
    *)
      echo "Unknown flag: $1" >&2
      usage
      ;;
  esac
done

API_BASE="${API_BASE%/}"

LOGIN_RESP="$(curl -sS -X POST "${API_BASE}/api/auth/token/login/" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${API_USERNAME}\",\"password\":\"${API_PASSWORD}\"}")"

TOKEN="$(
  python3 -c '
import json,sys
d=json.loads(sys.argv[1])
tok=d.get("auth_token") or d.get("token") or ""
if not tok:
    raise SystemExit("Login failed: " + json.dumps(d)[:500])
print(tok)
' "$LOGIN_RESP"
)"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
PAGE=1
COUNT=0

while true; do
  RESP="$(curl -sS \
    "${API_BASE}/api/inventory/products/?page=${PAGE}&page_size=200" \
    -H "Authorization: Token ${TOKEN}" \
    -H "Accept: application/json")"
  echo "$RESP" >"${TMP_DIR}/page-${PAGE}.json"
  NEXT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("next") or "")' "${TMP_DIR}/page-${PAGE}.json")"
  N="$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1])).get("results") or []))' "${TMP_DIR}/page-${PAGE}.json")"
  COUNT=$((COUNT + N))
  if [[ -z "$NEXT" || "$N" -eq 0 ]]; then
    break
  fi
  PAGE=$((PAGE + 1))
done

python3 - "$TMP_DIR" "$IN_STOCK" "$PUBLISHED_ONLY" "$CSV" <<'PY'
import json, sys
from pathlib import Path

tmp = Path(sys.argv[1])
in_stock = sys.argv[2] == "1"
published_only = sys.argv[3] == "1"
as_csv = sys.argv[4] == "1"

rows = []
for path in sorted(tmp.glob("page-*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    for p in data.get("results") or []:
        if published_only and not p.get("is_published"):
            continue
        stock = p.get("available_stock")
        try:
            stock_n = int(stock or 0)
        except (TypeError, ValueError):
            stock_n = 0
        if in_stock and stock_n <= 0:
            continue
        rows.append(
            {
                "id": p.get("id"),
                "slug": p.get("slug") or "",
                "product_name": p.get("product_name") or "",
                "available_stock": stock_n,
                "is_published": bool(p.get("is_published")),
            }
        )

rows.sort(key=lambda r: (r["product_name"].lower(), r["id"] or 0))

if as_csv:
    print("id,slug,product_name,available_stock,is_published")
    for r in rows:
        name = (r["product_name"] or "").replace('"', '""')
        slug = (r["slug"] or "").replace('"', '""')
        print(f'{r["id"]},"{slug}","{name}",{r["available_stock"]},{str(r["is_published"]).lower()}')
else:
    print(f"{'ID':<6} {'STOCK':>5}  {'SLUG':<55} PRODUCT")
    print("-" * 120)
    for r in rows:
        print(f'{r["id"]:<6} {r["available_stock"]:>5}  {(r["slug"] or "-"):<55} {r["product_name"]}')
    print("-" * 120)
    print(f"{len(rows)} products")
PY
