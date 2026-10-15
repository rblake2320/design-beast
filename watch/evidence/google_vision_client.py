"""Authenticated REST client shared by Google Cloud Vision extractors.

The client is event-schema neutral. Canonical raw extractors and Beast's
promotion-custody adapter can share it without creating two HTTP paths. A
request cannot run without an explicit per-call authorization flag.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any

import requests

from .contracts import EvidenceContractError, _require

VISION_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"
Requester = Callable[[str, bytes], dict[str, Any]]


class GoogleVisionClient:
    """Call one Cloud Vision feature against exact local bytes."""

    def __init__(
        self,
        *,
        api_key: str | None,
        requester: Requester | None = None,
        timeout_seconds: float = 30.0,
        max_results: int = 20,
    ) -> None:
        _require(1 <= max_results <= 50,
                 "Google Vision max_results must be 1..50")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_results = max_results
        self._requester = requester

    def request(
        self,
        feature: str,
        content: bytes,
        *,
        authorize_cloud_call: bool,
    ) -> dict[str, Any]:
        _require(authorize_cloud_call,
                 "explicit authorization is required for a Google Vision cloud call")
        if self._requester is not None:
            return self._check_result(self._requester(feature, content))
        _require(bool(self.api_key),
                 "Google Cloud Vision API key is required for a live call")
        payload = {
            "requests": [{
                "image": {"content": base64.b64encode(content).decode("ascii")},
                "features": [{"type": feature, "maxResults": self.max_results}],
            }],
        }
        try:
            response = requests.post(
                VISION_ENDPOINT,
                params={"key": self.api_key},
                headers={"Content-Type": "application/json; charset=utf-8"},
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise EvidenceContractError(
                f"Google Vision request failed: {type(exc).__name__}") from exc
        _require(isinstance(body, dict), "Google Vision response must be an object")
        responses = body.get("responses")
        _require(isinstance(responses, list) and len(responses) == 1,
                 "Google Vision response must contain exactly one image result")
        return self._check_result(responses[0])

    @staticmethod
    def _check_result(result: Any) -> dict[str, Any]:
        _require(isinstance(result, dict),
                 "Google Vision image result must be an object")
        if isinstance(result.get("error"), dict):
            raise EvidenceContractError(
                f"Google Vision error: {result['error'].get('message', 'unknown error')}")
        return result
