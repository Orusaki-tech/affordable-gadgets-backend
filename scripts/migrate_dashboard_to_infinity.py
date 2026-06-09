#!/usr/bin/env python3
"""Convert marcusolsson-json-datasource panel targets to yesoreyeram-infinity-datasource."""

from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from pathlib import Path

INFINITY_TYPE = "yesoreyeram-infinity-datasource"
INFINITY_UID = "json-api"


def _column_type(result_type: str) -> str:
    return "number" if result_type == "string" and False else "string"


def _infer_column_type(field: str, result_type: str) -> str:
    if result_type == "string":
        if field in ("status", "grafana_token_valid", "authenticated_as"):
            return "string"
        return "number"
    return "string"


def convert_target(target: dict) -> dict:
    ds = target.get("datasource", {})
    if ds.get("type") != "marcusolsson-json-datasource":
        return target

    url_path = target.get("urlPath", "")
    method = target.get("method", "GET")
    json_path = target.get("jsonPath", "$")
    result_type = target.get("resultType", "table")

    query: dict = {
        "datasource": {"type": INFINITY_TYPE, "uid": INFINITY_UID},
        "refId": target.get("refId", "A"),
        "type": "json",
        "source": "url",
        "format": "table",
        "url": url_path,
        "parser": "backend",
        "url_options": {"method": method, "params": [], "headers": []},
        "columns": [],
    }

    if result_type == "table":
        query["root_selector"] = json_path if json_path else "$"
        return query

    # Scalar stat panels: extract a single field from the JSON object.
    field = json_path.removeprefix("$.").removeprefix("$")
    if not field:
        field = "value"
        query["root_selector"] = "$"
    elif "." in field:
        query["root_selector"] = "$"
    else:
        query["root_selector"] = "$"

    query["columns"] = [
        {
            "selector": field,
            "text": field.split(".")[-1],
            "type": _infer_column_type(field.split(".")[-1], result_type),
        }
    ]
    return query


def convert_panel(panel: dict) -> dict:
    panel = deepcopy(panel)
    if panel.get("datasource", {}).get("type") == "marcusolsson-json-datasource":
        panel["datasource"] = {"type": INFINITY_TYPE, "uid": INFINITY_UID}

    if "targets" in panel:
        panel["targets"] = [convert_target(t) for t in panel["targets"]]

    return panel


def convert_dashboard(path: Path) -> None:
    data = json.loads(path.read_text())
    data["panels"] = [convert_panel(p) for p in data.get("panels", [])]
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Converted {path}")


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        print("Usage: migrate_dashboard_to_infinity.py <dashboard.json> ...", file=sys.stderr)
        sys.exit(1)
    for path in paths:
        convert_dashboard(path)


if __name__ == "__main__":
    main()
