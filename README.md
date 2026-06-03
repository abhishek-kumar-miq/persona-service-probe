# Persona connectivity probe

Standalone service that verifies connectivity from the `ida-integration` cluster to the persona service.

Each cycle runs **five** requests in order:

| # | Method | Path | Purpose |
|---|--------|------|---------|
| 1 | `GET` | `/audience-query/api/health` | Fast liveness through the same API prefix as real traffic |
| 2 | `POST` | `/v2/personas/` | `num_options=1`, `wait_for_image=false` |
| 3 | `POST` | `/v2/personas/` | `num_options=2`, `wait_for_image=false` |
| 4 | `POST` | `/v2/personas/` | `num_options=3`, `wait_for_image=false` |
| 5 | `POST` | `/v2/personas/` | `num_options=1`, `wait_for_image=true` |

POST bodies mirror `audience-manager-service` `AQSPersonasRequest` defaults.

## Logs

Human-readable lines with structured `key=value` fields (not JSON):

```
2026-06-03 14:00:00 | INFO     | [persona-connectivity-probe] [PROBE-HEALTH] request 1/5: completed | duration_seconds=0.012 | status_code=200 | ...
2026-06-03 14:00:05 | INFO     | [persona-connectivity-probe] [PROBE-PERSONA] request 2/5: completed | duration_seconds=45.231 | label=num_options=1 wait_for_image=false | status_code=200
```

```bash
kubectl -n ida-integration logs -l app.kubernetes.io/name=persona-connectivity-probe -f
```

Filter: `[PROBE-HEALTH]`, `[PROBE-PERSONA]`, or `[PROBE]`.

See `../audience-query/docs/LOGGING.md` for the shared logging model across services.

## Default URL (integration)

| Target | URL |
|--------|-----|
| Health | `.../audience-query/api/health` |
| Persona v2 API | `.../audience-query/api/v2/personas/` |


## Local run

```bash
pip install -e .
export PERSONA_SERVICE_URL=http://localhost:7010
python -m probe.main
```

## Deploy

Jenkins pipeline in `.ci/Jenkinsfile` builds the image and deploys Helm release `persona-connectivity-probe-integration` to `ida-integration`. Pushes to GitHub trigger the job via `githubPush()`.

