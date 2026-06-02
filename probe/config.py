import os

MOCK_PERSONA_PROMPT = "PERSONAS_PROMPT_TO_RETURN_MOCK_VALUES"

# In-cluster ClusterIP for miq-persona-service (same namespace: ida-integration).
PERSONA_SERVICE_URL = os.getenv(
    "PERSONA_SERVICE_URL",
    "http://miq-persona-service-integration.ida-integration.svc",
).rstrip("/")

EMBEDDING_SERVICE_URL = os.getenv(
    "EMBEDDING_SERVICE_URL",
    "http://miq-persona-embedding-service-integration.ida-integration.svc/miq-persona-embedding-service",
).rstrip("/")

EMBEDDING_SERVICE_BEARER_TOKEN = os.getenv("EMBEDDING_SERVICE_BEARER_TOKEN", "")

PROBE_INTERVAL_SECONDS = int(os.getenv("PROBE_INTERVAL_SECONDS", "300"))
PROBE_HTTP_TIMEOUT_SECONDS = float(os.getenv("PROBE_HTTP_TIMEOUT_SECONDS", "300"))

# FastAPI routes for personas live under /audience-query/api (see audience-query app.main SERVICE_ROOT).
PERSONA_API_PREFIX = os.getenv("PERSONA_API_PREFIX", "audience-query/api").rstrip("/")
