import os

PERSONA_SERVICE_URL = os.getenv(
    "PERSONA_SERVICE_URL",
    "http://miq-persona-service-integration.ida-integration.svc",
).rstrip("/")

PROBE_INTERVAL_SECONDS = int(os.getenv("PROBE_INTERVAL_SECONDS", "300"))
PROBE_HTTP_TIMEOUT_SECONDS = float(os.getenv("PROBE_HTTP_TIMEOUT_SECONDS", "300"))

PERSONA_API_PREFIX = os.getenv("PERSONA_API_PREFIX", "audience-query/api").rstrip("/")
