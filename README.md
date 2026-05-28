# Persona connectivity probe

Standalone service that verifies connectivity from the `ida-integration` cluster to:

1. **Embedding service** (in-cluster) — `GET /health` and `POST /embed`
2. **Persona service** (in-cluster) — `GET /health` and `POST /v2/personas/` (AMS-style mock request)

## Default URLs (integration)

| Target | URL |
|--------|-----|
| Embedding | `http://miq-persona-embedding-service-integration.ida-integration.svc.cluster.local/miq-persona-embedding-service` |
| Persona (base) | `http://miq-persona-service.ida-integration.svc.cluster.local` |
| Persona health | `http://miq-persona-service.ida-integration.svc.cluster.local/health` |
| Persona v2 API | `http://miq-persona-service.ida-integration.svc.cluster.local/audience-query/api/v2/personas/` |

## Logs

```bash
kubectl -n ida-integration logs -l app.kubernetes.io/name=persona-connectivity-probe -f
```

Filter: `[PROBE-EMBEDDING]` or `[PROBE-PERSONA]`.

## Local run

```bash
pip install -e .
export PERSONA_SERVICE_URL=http://localhost:8080
export EMBEDDING_SERVICE_URL=http://localhost:7001/miq-persona-embedding-service
python -m probe.main
```

## Deploy

Jenkins pipeline in `.ci/Jenkinsfile` builds the image and deploys Helm release `persona-connectivity-probe-integration` to `ida-integration`.
