#!/usr/bin/env python3
"""Generate deploy/ansible/vars/generated_from_terraform.yml from terraform output JSON."""

import json
import sys
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: generate_ansible_vars.py <terraform-output.json>", file=sys.stderr)
    sys.exit(1)

data = json.loads(Path(sys.argv[1]).read_text())
out = {k: v["value"] for k, v in data.items() if "value" in v}

lines = [
    "# Auto-generated from terraform output — do not commit secrets",
    f"aws_region: {out.get('aws_region', 'eu-north-1')}",
    f"aws_account_id: \"{out.get('aws_account_id', '')}\"",
    f"deploy_config_bucket: \"{out.get('deploy_config_bucket', '')}\"",
    f"api_instance_id: \"{out.get('api_instance_id', '')}\"",
    f"monitoring_instance_id: \"{out.get('monitoring_instance_id', '')}\"",
    f"api_private_ip: \"{out.get('api_private_ip', '')}\"",
    f"monitoring_private_ip: \"{out.get('monitoring_private_ip', '')}\"",
    f"rds_endpoint: \"{out.get('rds_endpoint', '')}\"",
    f"api_image: \"{out.get('api_image', '').rsplit(':', 1)[0] if out.get('api_image') else ''}\"",
    "",
]

dest = Path(__file__).resolve().parents[1] / "ansible/vars/generated_from_terraform.yml"
dest.write_text("\n".join(lines))
print(f"Wrote {dest}")
