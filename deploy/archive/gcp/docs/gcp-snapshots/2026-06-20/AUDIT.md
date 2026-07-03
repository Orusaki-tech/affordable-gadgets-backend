# GCP Audit — 2026-06-20T15:24:27Z

## Billing status: DISABLED (account closed)
billingEnabled: false on project-07850c05-c54d-486b-80a
API currently returning 503 — production at risk

## Single GCP project
project-07850c05-c54d-486b-80a (My First Project)

## KEEP — Affordable Gadgets (production, all RUNNING)
WARNING: Some requests did not succeed.
 - This API method requires billing to be enabled. Please enable billing on project #project-07850c05-c54d-486b-80a by visiting https://console.developers.google.com/billing/enable?project=project-07850c05-c54d-486b-80a then retry. If you enabled billing for this project recently, wait a few minutes for the action to propagate to our systems and retry.


NAME                              REGION    STATUS    settings.tier
affordable-gadgets-production-pg  us-east1  RUNNABLE

ERROR: (gcloud.redis.instances.list) PERMISSION_DENIED: This API method requires billing to be enabled. Please enable billing on project #project-07850c05-c54d-486b-80a by visiting https://console.developers.google.com/billing/enable?project=project-07850c05-c54d-486b-80a then retry. If you enabled billing for this project recently, wait a few minutes for the action to propagate to our systems and retry. This command is authenticated as petermadasana@gmail.com which is the active account specified by the [core/account] property.
This API method requires billing to be enabled. Please enable billing on project #project-07850c05-c54d-486b-80a by visiting https://console.developers.google.com/billing/enable?project=project-07850c05-c54d-486b-80a then retry. If you enabled billing for this project recently, wait a few minutes for the action to propagate to our systems and retry.
Google developers console billing
https://console.developers.google.com/billing/enable?project=project-07850c05-c54d-486b-80a
- '@type': type.googleapis.com/google.rpc.ErrorInfo
  domain: googleapis.com
  metadata:
    consoleUrl: https://console.developers.google.com/billing/enable?project=project-07850c05-c54d-486b-80a
    consumer: projects/project-07850c05-c54d-486b-80a
    containerInfo: project-07850c05-c54d-486b-80a
    service: redis.googleapis.com
  reason: BILLING_DISABLED
