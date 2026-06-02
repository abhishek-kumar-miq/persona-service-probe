"""
Connectivity probe for persona-service.

Each cycle sends four POST /v2/personas/ requests sequentially and logs duration per request.
Request shape mirrors audience-manager-service AQSPersonasRequest defaults.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

import httpx

from probe.config import (
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


def _summarize_persona_response(body: dict[str, Any]) -> dict[str, Any]:
    result = body.get("result") or []
    personas = result if isinstance(result, list) else []
    summary: dict[str, Any] = {"persona_count": len(personas)}
    if personas:
        first = personas[0]
        if isinstance(first, dict):
            summary["first_persona"] = {
                "id": first.get("id"),
                "name": first.get("name"),
                "image_status": (first.get("image") or {}).get("status")
                if isinstance(first.get("image"), dict)
                else None,
            }
    return summary


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

_PERSONA_V2_TEST_CASES: list[dict[str, Any]] = [
    {"num_options": 1, "wait_for_image": False},
    {"num_options": 2, "wait_for_image": False},
    {"num_options": 3, "wait_for_image": False},
    {"num_options": 1, "wait_for_image": True},
]


def _post_persona_v2(
    client: httpx.Client,
    *,
    base_url: str,
    num_options: int,
    wait_for_image: bool,
    request_index: int,
) -> tuple[float, int]:
    payload = {**_PERSONA_V2_BASE_PAYLOAD, "num_options": num_options}
    params = {"wait_for_image": str(wait_for_image).lower()}
    label = f"num_options={num_options} wait_for_image={str(wait_for_image).lower()}"

    logger.info(
        "[PROBE-PERSONA] request %s/4: POST %s params=%s",
        request_index,
        base_url,
        params,
    )
    started = time.perf_counter()
    response = client.post(base_url, params=params, json=payload)
    elapsed_s = time.perf_counter() - started

    logger.info(
        "[PROBE-PERSONA] request %s/4: %s status=%s duration_seconds=%.3f",
        request_index,
        label,
        response.status_code,
        elapsed_s,
    )
    if response.status_code >= 400:
        logger.error(
            "[PROBE-PERSONA] request %s/4: %s error body=%s",
            request_index,
            label,
            response.text[:2000],
        )
        response.raise_for_status()

    body = response.json()
    logger.info(
        "[PROBE-PERSONA] request %s/4: %s response summary=%s",
        request_index,
        label,
        json.dumps(_summarize_persona_response(body)),
    )
    return elapsed_s, response.status_code


def run_probe_cycle() -> None:
    logger.info(
        "Starting probe cycle persona_url=%s interval_seconds=%s",
        PERSONA_SERVICE_URL,
        PROBE_INTERVAL_SECONDS,
    )
    base_url = _persona_path("/v2/personas/")
    timings: list[tuple[str, int, float]] = []

    with httpx.Client(timeout=TIMEOUT) as client:
        for index, case in enumerate(_PERSONA_V2_TEST_CASES, start=1):
            elapsed_s, status = _post_persona_v2(
                client,
                base_url=base_url,
                num_options=case["num_options"],
                wait_for_image=case["wait_for_image"],
                request_index=index,
            )
            label = (
                f"num_options={case['num_options']} "
                f"wait_for_image={str(case['wait_for_image']).lower()}"
            )
            timings.append((label, status, elapsed_s))

    logger.info("[PROBE] cycle timing summary:")
    for label, status, elapsed_s in timings:
        logger.info(
            "[PROBE]   %s status=%s duration_seconds=%.3f",
            label,
            status,
            elapsed_s,
        )
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
