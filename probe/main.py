"""
Connectivity probe for persona-service.

Each cycle runs GET /health then four POST /v2/personas/ requests sequentially.
Logs use structured key=value fields (same data as JSON) in human-readable lines.
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
    format="%(asctime)s | %(levelname)-8s | [persona-connectivity-probe] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(PROBE_HTTP_TIMEOUT_SECONDS)


def _format_fields(**fields: Any) -> str:
    parts: list[str] = []
    for key, value in sorted(fields.items()):
        if value is None:
            continue
        if isinstance(value, bool):
            parts.append(f"{key}={str(value).lower()}")
        elif isinstance(value, (int, float, str)):
            parts.append(f"{key}={value}")
        else:
            parts.append(f"{key}={json.dumps(value, default=str)}")
    return " | ".join(parts)


def _log_probe(tag: str, message: str, **fields: Any) -> None:
    suffix = _format_fields(**fields)
    if suffix:
        logger.info("[%s] %s | %s", tag, message, suffix)
    else:
        logger.info("[%s] %s", tag, message)


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


def _format_response_for_log(body: dict[str, Any]) -> str:
    """Serialize response for logging, replacing large image payloads with a size hint."""
    log_body = json.loads(json.dumps(body))
    for persona in log_body.get("result") or []:
        if not isinstance(persona, dict):
            continue
        image = persona.get("image")
        if not isinstance(image, dict):
            continue
        b64 = image.get("b64_json")
        if isinstance(b64, str) and b64:
            image["b64_json"] = f"<redacted {len(b64)} chars>"
    return json.dumps(log_body)


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

_TOTAL_REQUESTS = 1 + len(_PERSONA_V2_TEST_CASES)


def _get_health(
    client: httpx.Client,
    *,
    health_url: str,
    request_index: int,
) -> tuple[float, int]:
    _log_probe(
        "PROBE-HEALTH",
        f"request {request_index}/{_TOTAL_REQUESTS}: GET",
        method="GET",
        url=health_url,
    )
    started = time.perf_counter()
    response = client.get(health_url)
    elapsed_s = time.perf_counter() - started

    body_preview = response.text[:500] if response.text else ""
    _log_probe(
        "PROBE-HEALTH",
        f"request {request_index}/{_TOTAL_REQUESTS}: completed",
        status_code=response.status_code,
        duration_seconds=round(elapsed_s, 3),
        response_body=body_preview,
    )
    if response.status_code >= 400:
        response.raise_for_status()
    return elapsed_s, response.status_code


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

    _log_probe(
        "PROBE-PERSONA",
        f"request {request_index}/{_TOTAL_REQUESTS}: POST",
        method="POST",
        url=base_url,
        params=params,
        num_options=num_options,
        wait_for_image=wait_for_image,
        prompt=payload.get("prompt"),
    )
    started = time.perf_counter()
    response = client.post(base_url, params=params, json=payload)
    elapsed_s = time.perf_counter() - started

    _log_probe(
        "PROBE-PERSONA",
        f"request {request_index}/{_TOTAL_REQUESTS}: completed",
        label=label,
        status_code=response.status_code,
        duration_seconds=round(elapsed_s, 3),
    )
    if response.status_code >= 400:
        _log_probe(
            "PROBE-PERSONA",
            f"request {request_index}/{_TOTAL_REQUESTS}: error",
            label=label,
            status_code=response.status_code,
            error_body=response.text[:2000],
        )
        response.raise_for_status()

    body = response.json()
    _log_probe(
        "PROBE-PERSONA",
        f"request {request_index}/{_TOTAL_REQUESTS}: response summary",
        label=label,
        **_summarize_persona_response(body),
    )
    _log_probe(
        "PROBE-PERSONA",
        f"request {request_index}/{_TOTAL_REQUESTS}: response detail",
        label=label,
        response_body=_format_response_for_log(body),
    )
    return elapsed_s, response.status_code


def run_probe_cycle() -> None:
    _log_probe(
        "PROBE",
        "starting cycle",
        persona_url=PERSONA_SERVICE_URL,
        interval_seconds=PROBE_INTERVAL_SECONDS,
        total_requests=_TOTAL_REQUESTS,
    )
    health_url = _persona_path("/health")
    persona_url = _persona_path("/v2/personas/")
    timings: list[tuple[str, int, float]] = []

    with httpx.Client(timeout=TIMEOUT) as client:
        elapsed_s, status = _get_health(
            client,
            health_url=health_url,
            request_index=1,
        )
        timings.append(("GET /health", status, elapsed_s))

        for offset, case in enumerate(_PERSONA_V2_TEST_CASES, start=2):
            elapsed_s, status = _post_persona_v2(
                client,
                base_url=persona_url,
                num_options=case["num_options"],
                wait_for_image=case["wait_for_image"],
                request_index=offset,
            )
            label = (
                f"POST num_options={case['num_options']} "
                f"wait_for_image={str(case['wait_for_image']).lower()}"
            )
            timings.append((label, status, elapsed_s))

    _log_probe("PROBE", "cycle timing summary")
    for label, status, elapsed_s in timings:
        _log_probe(
            "PROBE",
            "timing",
            request=label,
            status_code=status,
            duration_seconds=round(elapsed_s, 3),
        )
    _log_probe("PROBE", "cycle completed successfully")


def main() -> None:
    while True:
        try:
            run_probe_cycle()
        except Exception:
            logger.exception("[PROBE] cycle failed")
        _log_probe(
            "PROBE",
            "sleeping until next cycle",
            interval_seconds=PROBE_INTERVAL_SECONDS,
        )
        time.sleep(PROBE_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
