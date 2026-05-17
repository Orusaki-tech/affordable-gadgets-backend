# Monitoring Configs

This directory is a local development convenience copy.

**Source of truth:** `deploy/ansible/roles/monitoring_compose/`

Production monitoring is deployed via Ansible. Changes must be made
in the Ansible role directory and deployed via:
  `ansible-playbook deploy/ansible/playbooks/monitoring.yml`

Files found only here (not in Ansible role) are for local dev only.
