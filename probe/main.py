"""
Connectivity probe for persona-service (consumer) and embedding-service (upstream).

Logs request/response summaries to stdout for verification via kubectl logs / Rancher.
Request shape for persona POST mirrors audience-manager-service AQSPersonasRequest defaults.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

import httpx

from probe.config import (
    EMBEDDING_SERVICE_BEARER_TOKEN,
    EMBEDDING_SERVICE_URL,
    PERSONA_API_PREFIX,
    PERSONA_SERVICE_URL,
    PROBE_HTTP_TIMEOUT_SECONDS,
    PROBE_INTERVAL_SECONDS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [persona-connectivity-probe] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(PROBE_HTTP_TIMEOUT_SECONDS)


def _embedding_headers() -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if EMBEDDING_SERVICE_BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {EMBEDDING_SERVICE_BEARER_TOKEN}"
    return headers


def _summarize_embedding_response(body: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "embedder_name": body.get("embedder_name"),
        "quantizer_name": body.get("quantizer_name"),
        "results_count": len(body.get("results") or []),
    }
    results = body.get("results") or []
    if results:
        first = results[0]
        embedding = first.get("embedding") if isinstance(first, dict) else None
        if isinstance(embedding, list):
            summary["first_embedding_dimensions"] = len(embedding)
            summary["first_embedding_preview"] = embedding[:5]
    return summary


def _summarize_persona_response(body: dict[str, Any]) -> dict[str, Any]:
    result = body.get("result") or []
    personas = result if isinstance(result, list) else []
    summary: dict[str, Any] = {"persona_count": len(personas)}
    if personas:
        first = personas[0]
        if isinstance(first, dict):
            summary["first_persona"] = {
                "id": first.get("id"),
                "persona_name": first.get("persona_name"),
                "has_embedding": first.get("embedding") is not None,
                "embedding_dimensions": (
                    len(first["embedding"])
                    if isinstance(first.get("embedding"), list)
                    else None
                ),
            }
    return summary


def probe_embedding_health(client: httpx.Client) -> None:
    url = f"{EMBEDDING_SERVICE_URL}/health"
    logger.info("[PROBE-EMBEDDING] GET %s", url)
    response = client.get(url, headers=_embedding_headers())
    logger.info(
        "[PROBE-EMBEDDING] health status=%s body=%s",
        response.status_code,
        response.text[:2000],
    )
    response.raise_for_status()


def probe_embedding_embed(client: httpx.Client) -> None:
    url = f"{EMBEDDING_SERVICE_URL}/embed"
    payload = {"texts": ["persona-connectivity-probe embedding check"]}
    params = {"include_reporting_id": "false"}
    logger.info("[PROBE-EMBEDDING] POST %s params=%s body=%s", url, params, payload)
    response = client.post(
        url,
        params=params,
        json=payload,
        headers=_embedding_headers(),
    )
    logger.info("[PROBE-EMBEDDING] embed status=%s", response.status_code)
    response.raise_for_status()
    body = response.json()
    logger.info(
        "[PROBE-EMBEDDING] embed response summary=%s",
        json.dumps(_summarize_embedding_response(body)),
    )
    logger.info("[PROBE-EMBEDDING] embed full response=%s", json.dumps(body)[:8000])


def probe_persona_health(client: httpx.Client) -> None:
    url = f"{PERSONA_SERVICE_URL}/health"
    logger.info("[PROBE-PERSONA] GET %s", url)
    response = client.get(url)
    logger.info(
        "[PROBE-PERSONA] health status=%s body=%s",
        response.status_code,
        response.text[:2000],
    )
    response.raise_for_status()


def _persona_path(suffix: str) -> str:
    prefix = f"/{PERSONA_API_PREFIX}" if PERSONA_API_PREFIX else ""
    return f"{PERSONA_SERVICE_URL}{prefix}{suffix}"


_PERSONA_V2_BASE_PAYLOAD: dict[str, Any] = {
    "prompt": "coffee lovers",
    "prompt_type": "TEXT",
    "country": "US",
    "language": "EN",
    "include_segments": False,
    "include_embedding": False,
    "num_segment_options": 10,
    "include_search_terms": True,
    "num_search_terms_options": 10,
    "min_search_terms_relevance_score": 0.25,
}

# Four persona v2 scenarios exercised each probe cycle.
_PERSONA_V2_TEST_CASES: list[dict[str, Any]] = [
    {
        "num_options": 1,
        "wait_for_image": False,
        "label": "testing num_options=1 wait_for_image=false",
    },
    {
        "num_options": 2,
        "wait_for_image": False,
        "label": "testing num_options=2 wait_for_image=false",
    },
    {
        "num_options": 3,
        "wait_for_image": False,
        "label": "testing num_options=3 wait_for_image=false",
    },
    {
        "num_options": 1,
        "wait_for_image": True,
        "label": "testing num_options=1 wait_for_image=true",
    },
]


def _post_persona_v2(
    client: httpx.Client,
    *,
    base_url: str,
    num_options: int,
    wait_for_image: bool,
    label: str,
) -> None:
    payload = {**_PERSONA_V2_BASE_PAYLOAD, "num_options": num_options}
    params = {"wait_for_image": str(wait_for_image).lower()}

    logger.info("[PROBE-PERSONA] %s — POST %s params=%s body=%s", label, base_url, params, json.dumps(payload))
    started = time.perf_counter()
    response = client.post(base_url, params=params, json=payload)
    elapsed_s = time.perf_counter() - started

    logger.info(
        "[PROBE-PERSONA] %s — status=%s duration_seconds=%.3f",
        label,
        response.status_code,
        elapsed_s,
    )
    if response.status_code >= 400:
        logger.error(
            "[PROBE-PERSONA] %s — error body=%s",
            label,
            response.text[:8000],
        )
        response.raise_for_status()

    body = response.json()
    logger.info(
        "[PROBE-PERSONA] %s — response summary=%s",
        label,
        json.dumps(_summarize_persona_response(body)),
    )
    logger.info(
        "[PROBE-PERSONA] %s — full response=%s",
        label,
        json.dumps(body)[:8000],
    )


def probe_persona_v2_create(client: httpx.Client) -> None:
    """POST /v2/personas/ for num_options 1/2/3 (async images) then num_options=1 with wait_for_image=true."""
    base_url = _persona_path("/v2/personas/")

    for index, case in enumerate(_PERSONA_V2_TEST_CASES, start=1):
        logger.info(
            "[PROBE-PERSONA] starting persona v2 test %s/%s: %s",
            index,
            len(_PERSONA_V2_TEST_CASES),
            case["label"],
        )
        _post_persona_v2(
            client,
            base_url=base_url,
            num_options=case["num_options"],
            wait_for_image=case["wait_for_image"],
            label=case["label"],
        )
        logger.info("[PROBE-PERSONA] completed persona v2 test %s/%s: %s", index, len(_PERSONA_V2_TEST_CASES), case["label"])


def run_probe_cycle() -> None:
    logger.info(
        "Starting probe cycle persona_url=%s embedding_url=%s interval_seconds=%s "
        "embedding_auth=%s",
        PERSONA_SERVICE_URL,
        EMBEDDING_SERVICE_URL,
        PROBE_INTERVAL_SECONDS,
        "configured" if EMBEDDING_SERVICE_BEARER_TOKEN else "missing",
    )
    with httpx.Client(timeout=TIMEOUT) as client:
        probe_embedding_health(client)
        probe_embedding_embed(client)
        probe_persona_health(client)
        probe_persona_v2_create(client)
    logger.info("[PROBE] cycle completed successfully")


def main() -> None:
    while True:
        try:
            run_probe_cycle()
        except Exception:
            logger.exception("[PROBE] cycle failed")
        logger.info("[PROBE] sleeping %s seconds until next cycle", PROBE_INTERVAL_SECONDS)
        time.sleep(PROBE_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
