"""Typed models for documented Qloo response shapes.

Sources (verify against live docs when changing):
- https://docs.qloo.com/reference/qloo-llm-hackathon-developer-guide
- https://docs.qloo.com/reference/get-search
- https://docs.qloo.com/reference/basic-insights-use-case
- https://docs.qloo.com/reference/insights-api
- https://github.com/qloo/docs-public

Fields are intentionally permissive where official docs show variable nesting.
Only fields we consume are modeled; unknown keys are ignored (never invented).
"""

from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


class QlooImage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str | None = None


class QlooProperties(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str | None = None
    short_description: str | None = None
    release_year: int | None = None
    image: QlooImage | None = None
    address: str | None = None
    business_rating: float | None = None


class QlooTag(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    name: str | None = None
    type: str | None = None


class QlooEntity(BaseModel):
    """Normalized entity used by TasteOS after Qloo Search/Insights."""

    model_config = ConfigDict(extra="ignore")

    name: str
    entity_id: str
    type: str | None = None
    subtype: str | None = None
    properties: QlooProperties | None = None
    popularity: float | None = None
    tags: list[QlooTag] = Field(default_factory=list)
    query: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_id_alias(cls, data: Any) -> Any:
        """Some payloads use `id` instead of `entity_id` (defensive; prefer entity_id)."""
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if not out.get("entity_id") and out.get("id"):
            out["entity_id"] = out["id"]
        return out

    @field_validator("name", "entity_id")
    @classmethod
    def non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("entity fields must be non-empty strings")
        return cleaned

    def description_text(self) -> str | None:
        if not self.properties:
            return None
        return self.properties.description or self.properties.short_description

    def image_url(self) -> str | None:
        if self.properties and self.properties.image:
            return self.properties.image.url
        return None

    def affinity_from_query(self) -> float | None:
        """Return Qloo affinity only when present under entity.query (never fabricate)."""
        if not self.query:
            return None
        affinity = self.query.get("affinity")
        if isinstance(affinity, (int, float)):
            return float(affinity)
        measurements = self.query.get("measurements")
        if isinstance(measurements, dict):
            nested = measurements.get("affinity")
            if isinstance(nested, (int, float)):
                return float(nested)
        return None


def _parse_entity_list(items: list[Any]) -> list[QlooEntity]:
    entities: list[QlooEntity] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            entities.append(QlooEntity.model_validate(item))
        except ValidationError:
            # Skip malformed rows rather than inventing fields.
            continue
    return entities


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Documented OpenAPI shape uses results as an entity array; tolerate nested variants.
    results: list[Any] | dict[str, Any] | None = None
    success: bool | None = None
    duration: float | int | None = None

    def entities(self) -> list[QlooEntity]:
        if self.results is None:
            return []
        if isinstance(self.results, list):
            return _parse_entity_list(self.results)
        nested = self.results.get("entities")
        if isinstance(nested, list):
            return _parse_entity_list(nested)
        return []


class InsightsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool | None = None
    results: dict[str, Any] | None = None
    duration: float | int | None = None
    query: dict[str, Any] | None = None

    def entities(self) -> list[QlooEntity]:
        if not self.results:
            return []
        nested = self.results.get("entities")
        if not isinstance(nested, list):
            return []
        return _parse_entity_list(nested)
