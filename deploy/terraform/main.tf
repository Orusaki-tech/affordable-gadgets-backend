# Root Terraform entry.
# - legacy.tf: single VM (platform_enabled=false, legacy_mode=true) — default for backward compatibility
# - platform.tf: VPC, Cloud SQL, Redis, MIGs, LBs (platform_enabled=true)
#
# See deploy/README-GCP-PLATFORM.md and environments/*.tfvars
