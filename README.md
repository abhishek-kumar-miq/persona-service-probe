# Persona connectivity probe

Standalone service that verifies connectivity from the `ida-integration` cluster to the persona service by sending four sequential `POST /v2/personas/` requests and logging how long each takes.

## Requests per cycle

| # | `num_options` | `wait_for_image` |
|---|---------------|------------------|
| 1 | 1 | false |
| 2 | 2 | false |
| 3 | 3 | false |
| 4 | 1 | true |

Each request logs `duration_seconds` immediately, and the cycle ends with a timing summary.

## Default URL (integration)

| Target | URL |
|--------|-----|
| Persona (base) | `http://miq-persona-service-integration.ida-integration.svc` |
| Persona v2 API | `http://miq-persona-service-integration.ida-integration.svc/audience-query/api/v2/personas/` |

## Logs

```bash
kubectl -n ida-integration logs -l app.kubernetes.io/name=persona-connectivity-probe -f
```

Filter: `[PROBE-PERSONA]` or `[PROBE]`.

## Local run

```bash
pip install -e .
export PERSONA_SERVICE_URL=http://localhost:8080
python -m probe.main
```

## Deploy

Jenkins pipeline in `.ci/Jenkinsfile` builds the image and deploys Helm release `persona-connectivity-probe-integration` to `ida-integration`.

Configuration comes from the Helm ConfigMap only — no Vault integration.
