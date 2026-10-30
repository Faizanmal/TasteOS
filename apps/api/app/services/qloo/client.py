"""HTTP client for the Qloo Search + Insights APIs.

Verified against official docs (rechecked for Phase 2):
- https://docs.qloo.com/reference/qloo-llm-hackathon-developer-guide
- https://docs.qloo.com/reference/api-onboarding
- https://docs.qloo.com/reference/api-information  (ApiKey header name: X-Api-Key)
- https://docs.qloo.com/reference/get-search
- https://docs.qloo.com/reference/basic-insights-use-case
- https://docs.qloo.com/reference/insights-api
- https://docs.qloo.com/reference/available-parameters-by-entity-type
- https://github.com/qloo/docs-public/blob/main/recipes/recipes.md

Hackathon base URL: https://hackathon.api.qloo.com
Auth: request header X-Api-Key (not Bearer, not query param)
Insights: GET /v2/insights with query-string params (not POST JSON body)
Do NOT use legacy /recommendations or /recs.
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import Settings, get_settings
from app.core.logging import get_logger, redact
from app.services.qloo.models import InsightsResponse, QlooEntity, SearchResponse

logger = get_logger(__name__)

HACKATHON_BASE_URL = "https://hackathon.api.qloo.com"

# Entity types documented for Insights filter.type (hackathon developer guide).
INSIGHTS_ENTITY_TYPES = frozenset(
    {
        "urn:entity:artist",
        "urn:entity:book",
        "urn:entity:brand",
        "urn:entity:destination",
        "urn:entity:movie",
        "urn:entity:person",
        "urn:entity:place",
        "urn:entity:podcast",
        "urn:entity:tv_show",
        "urn:entity:video_game",
    }
)

# Types that support documented location filters (place recipe uses filter.location.query).
LOCATION_FILTER_TYPES = frozenset(
    {
        "urn:entity:place",
        "urn:entity:destination",
    }
)

# Search OpenAPI also lists these; Insights types above are the hackathon Insights allow-list.
# Search `types` is not identical to Insights filter.type — keep caller-controlled.


class QlooError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class QlooRateLimitError(QlooError):
    def __init__(self, message: str = "Qloo rate limit exceeded (HTTP 429)") -> None:
        super().__init__(message, status_code=429, retryable=True)


class QlooTransientError(QlooError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message, status_code=status_code, retryable=True)


class QlooClient:
    """Server-side Qloo client. Never expose the API key to browsers or logs."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> QlooClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.settings.qloo_base_url,
                timeout=httpx.Timeout(self.settings.qloo_timeout_seconds),
                headers=self._auth_headers(),
            )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _auth_headers(self) -> dict[str, str]:
        if not self.settings.qloo_configured:
            raise QlooError(
                "QLOO_API_KEY is not configured. "
                "Request a hackathon key from "
                "https://docs.qloo.com/reference/qloo-llm-hackathon-developer-guide#getting-your-api-key "
                "or use TASTEOS_MODE=demo.",
                status_code=None,
            )
        return {
            "Accept": "application/json",
            "X-Api-Key": self.settings.qloo_api_key.strip(),
        }

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.settings.qloo_base_url,
                timeout=httpx.Timeout(self.settings.qloo_timeout_seconds),
                headers=self._auth_headers(),
            )
            self._owns_client = True
        return self._client

    @staticmethod
    def _safe_params_for_log(params: dict[str, Any] | None) -> dict[str, Any]:
        if not params:
            return {}
        safe: dict[str, Any] = {}
        for key, value in params.items():
            if key.lower() in {"x-api-key", "authorization", "api_key"}:
                safe[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 120:
                safe[key] = value[:117] + "..."
            else:
                safe[key] = value
        return safe

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | list[Any], int, float]:
        client = self._ensure_client()
        # Rebuild headers in case settings changed after construction (never log them).
        client.headers.update(self._auth_headers())

        attempts = max(1, self.settings.qloo_max_retries + 1)

        @retry(
            reraise=True,
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            retry=retry_if_exception_type((QlooRateLimitError, QlooTransientError)),
        )
        async def _do() -> tuple[dict[str, Any] | list[Any], int, float]:
            started = time.perf_counter()
            try:
                response = await client.request(method, path, params=params)
            except httpx.TimeoutException as exc:
                raise QlooTransientError(f"Qloo request timed out: {path}") from exc
            except httpx.TransportError as exc:
                raise QlooTransientError(
                    f"Qloo transport error: {type(exc).__name__}"
                ) from exc

            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "qloo_request method=%s path=%s status=%s elapsed_ms=%.1f params=%s",
                method,
                path,
                response.status_code,
                elapsed_ms,
                self._safe_params_for_log(params),
            )

            if response.status_code == 429:
                raise QlooRateLimitError()
            if response.status_code in {502, 503, 504}:
                raise QlooTransientError(
                    f"Qloo upstream unavailable ({response.status_code})",
                    status_code=response.status_code,
                )
            if response.status_code == 401:
                raise QlooError(
                    "Qloo authentication failed (401). Confirm QLOO_API_KEY and that "
                    f"QLOO_BASE_URL is {HACKATHON_BASE_URL} for hackathon keys "
                    "(not staging/production hosts).",
                    status_code=401,
                )
            if response.status_code == 403:
                body = redact(response.text[:400])
                raise QlooError(
                    "Qloo forbidden (403). Often an unsupported filter.type or "
                    f"permission issue. Body: {body}",
                    status_code=403,
                )
            if response.status_code == 404 and path.rstrip("/").endswith("search"):
                # Search OpenAPI documents 404 as no results.
                return {"success": False, "results": []}, 404, elapsed_ms
            if response.status_code >= 400:
                body = redact(response.text[:500])
                raise QlooError(
                    f"Qloo error {response.status_code}: {body}",
                    status_code=response.status_code,
                )

            try:
                data = response.json()
            except json.JSONDecodeError as exc:
                raise QlooError(
                    "Qloo returned non-JSON success body",
                    status_code=response.status_code,
                ) from exc

            if not isinstance(data, (dict, list)):
                raise QlooError(
                    f"Unexpected Qloo JSON root type: {type(data).__name__}",
                    status_code=response.status_code,
                )
            return data, response.status_code, elapsed_ms

        return await _do()

    def build_search_params(
        self,
        query: str,
        *,
        types: list[str] | None = None,
        take: int = 10,
    ) -> dict[str, Any]:
        """Construct documented GET /search query params (for tests + callers)."""
        cleaned = query.strip()
        if not cleaned:
            raise QlooError("search query must be a non-empty string")
        params: dict[str, Any] = {
            "query": cleaned,
            "take": min(max(int(take), 1), 50),
        }
        if types:
            params["types"] = ",".join(t.strip() for t in types if t.strip())
        return params

    def build_insights_params(
        self,
        *,
        filter_type: str,
        entity_ids: list[str] | None = None,
        tag_ids: list[str] | None = None,
        location_query: str | None = None,
        take: int = 10,
        explainability: bool = False,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Construct documented GET /v2/insights query params."""
        if filter_type not in INSIGHTS_ENTITY_TYPES:
            raise QlooError(
                f"Unsupported filter.type '{filter_type}'. "
                f"Supported (hackathon guide): {sorted(INSIGHTS_ENTITY_TYPES)}"
            )

        params: dict[str, Any] = {
            "filter.type": filter_type,
            "take": min(max(int(take), 1), 50),
        }
        if explainability:
            # Optional; unsupported params may be silently ignored by Qloo.
            params["feature.explainability"] = "true"

        ids = [eid.strip() for eid in (entity_ids or []) if eid and eid.strip()]
        if ids:
            params["signal.interests.entities"] = ",".join(ids)

        tags = [tid.strip() for tid in (tag_ids or []) if tid and tid.strip()]
        if tags:
            params["signal.interests.tags"] = ",".join(tags)

        if location_query and location_query.strip():
            loc = location_query.strip()
            if filter_type in LOCATION_FILTER_TYPES:
                # Official place recipe uses filter.location.query.
                params["filter.location.query"] = loc
            else:
                # Documented signal for non-place contexts (e.g. basic insights guides).
                params["signal.location.query"] = loc

        if extra_params:
            # Caller-supplied documented params only — still never log secrets.
            for key, value in extra_params.items():
                if key.lower() in {"x-api-key", "authorization", "api_key"}:
                    continue
                params[key] = value

        has_signal = any(
            k.startswith("signal.") or k.startswith("filter.")
            for k in params
            if k != "filter.type"
        )
        if not has_signal:
            raise QlooError(
                "Insights requires at least one documented signal or filter besides "
                "filter.type (e.g. signal.interests.entities, signal.interests.tags, "
                "filter.location.query)."
            )
        return params

    async def search(
        self,
        query: str,
        *,
        types: list[str] | None = None,
        take: int = 10,
    ) -> tuple[list[QlooEntity], dict[str, Any]]:
        params = self.build_search_params(query, types=types, take=take)
        raw, status, elapsed_ms = await self._request("GET", "/search", params=params)

        try:
            if isinstance(raw, list):
                entities = _entities_from_list(raw)
            else:
                entities = SearchResponse.model_validate(raw).entities()
        except ValidationError as exc:
            raise QlooError(
                f"Qloo search response failed validation: {exc.error_count()} issue(s)",
                status_code=status,
            ) from exc

        meta = {
            "status_code": status,
            "elapsed_ms": elapsed_ms,
            "source": "qloo",
            "endpoint": "/search",
            "entity_count": len(entities),
        }
        return entities, meta

    async def insights(
        self,
        *,
        filter_type: str,
        entity_ids: list[str] | None = None,
        tag_ids: list[str] | None = None,
        location_query: str | None = None,
        take: int = 10,
        explainability: bool = False,
        extra_params: dict[str, Any] | None = None,
    ) -> tuple[list[QlooEntity], dict[str, Any]]:
        params = self.build_insights_params(
            filter_type=filter_type,
            entity_ids=entity_ids,
            tag_ids=tag_ids,
            location_query=location_query,
            take=take,
            explainability=explainability,
            extra_params=extra_params,
        )
        raw, status, elapsed_ms = await self._request(
            "GET", "/v2/insights", params=params
        )
        if isinstance(raw, list):
            raise QlooError(
                "Unexpected list JSON root from /v2/insights", status_code=status
            )

        try:
            parsed = InsightsResponse.model_validate(raw)
            entities = parsed.entities()
        except ValidationError as exc:
            raise QlooError(
                f"Qloo insights response failed validation: {exc.error_count()} issue(s)",
                status_code=status,
            ) from exc

        meta = {
            "status_code": status,
            "elapsed_ms": elapsed_ms,
            "source": "qloo",
            "endpoint": "/v2/insights",
            "success": parsed.success,
            "filter_type": filter_type,
            "signal_entity_count": len(entity_ids or []),
            "location_query": location_query,
            "entity_count": len(entities),
            # Application ranking is NOT included here — callers must label separately.
            "ranking_source": "qloo_affinity_when_present",
        }
        return entities, meta

    async def health_probe(self) -> dict[str, Any]:
        """Documented search → insights path for `python -m app.cli check-qloo`.

        Returns a sanitized summary. Never includes the API key.
        """
        started = time.perf_counter()
        host = urlparse(self.settings.qloo_base_url).netloc

        search_entities, search_meta = await self.search(
            "Radiohead",
            types=["urn:entity:artist"],
            take=3,
        )
        if not search_entities:
            return {
                "ok": False,
                "key_configured": True,
                "base_url_host": host,
                "http_status": search_meta.get("status_code"),
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                "stage": "search",
                "entity_count": 0,
                "sample": [],
                "note": "Search returned no entities for probe query 'Radiohead'.",
            }

        seed = search_entities[0]
        insight_entities, insight_meta = await self.insights(
            filter_type="urn:entity:place",
            entity_ids=[seed.entity_id],
            location_query="New York",
            take=3,
            explainability=False,
        )
        sample = [
            {
                "name": e.name,
                "entity_id": e.entity_id,
                "subtype": e.subtype,
                "affinity": e.affinity_from_query(),
            }
            for e in insight_entities[:3]
        ]
        return {
            "ok": True,
            "key_configured": True,
            "base_url_host": host,
            "http_status": insight_meta.get("status_code"),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "stage": "insights",
            "seed": {
                "name": seed.name,
                "entity_id": seed.entity_id,
                "subtype": seed.subtype,
            },
            "entity_count": len(insight_entities),
            "sample": sample,
            "provenance": {
                "search": "qloo:/search",
                "insights": "qloo:/v2/insights",
                "affinity": "copied from entity.query when present; never fabricated",
            },
        }


def _entities_from_list(raw: list[Any]) -> list[QlooEntity]:
    entities: list[QlooEntity] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            entities.append(QlooEntity.model_validate(item))
        except ValidationError:
            continue
    return entities
