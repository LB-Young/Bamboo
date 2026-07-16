"""BKN dynamic attribute loading."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urljoin

import httpx

from bamboo.bkn.models import BknAttrFetch, BKNDefinition, BKNEntity, BKNSource
from bamboo.bkn.source_readers import load_dynamic_data
from bamboo.security.url_safety import is_url_allowed


class HttpApiAdapter:
    """Read attributes from a configured HTTP API endpoint."""

    def __init__(self, *, base_url: str, timeout: float = 5.0, client: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.client = client

    def fetch(self, source: BKNSource, entity: BKNEntity) -> dict[str, object]:
        """Fetch one entity payload from an HTTP endpoint."""
        if not self.base_url.strip("/"):
            raise ValueError("HTTP source base_url is required")
        endpoint = str(source.config.get("path", source.config.get("endpoint", source.config.get("url", ""))))
        if not endpoint:
            endpoint = str(entity.properties.get("endpoint", entity.id))
        url = urljoin(self.base_url, endpoint.format(id=entity.id, **entity.properties).lstrip("/"))
        if not url.startswith(self.base_url):
            raise ValueError("HTTP source URL escapes manifest base_url")
        allowed, reason = is_url_allowed(url)
        if not allowed:
            raise ValueError(reason)
        client = self.client or httpx.Client(timeout=self.timeout)
        close_client = self.client is None
        try:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
        finally:
            if close_client:
                client.close()
        if not isinstance(payload, dict):
            raise ValueError("HTTP source response must be a JSON object")
        return _redact_mapping(payload)


class BknAttrsStore:
    """Read dynamic attributes for entities using configured sources."""

    def __init__(self, definition: BKNDefinition, *, http_client: httpx.Client | None = None) -> None:
        self.definition = definition
        self.http_client = http_client

    def get_attrs(self, entity: BKNEntity, *, keys: tuple[str, ...] | None = None) -> BknAttrFetch:
        """Fetch attributes for an entity without failing the caller."""
        warnings: list[str] = []
        try:
            values = self._load_attrs(entity)
        except (OSError, ValueError, httpx.HTTPError) as exc:
            values = dict(entity.properties)
            warnings.append(str(exc))
        if keys:
            values = {key: value for key, value in values.items() if key in keys}
        return BknAttrFetch(
            node_id=entity.id,
            values=values,
            source=str(entity.properties.get("source", entity.source_path)),
            fetched_at=datetime.now(UTC),
            warnings=tuple(warnings),
        )

    def _load_attrs(self, entity: BKNEntity) -> dict[str, object]:
        source_name = entity.properties.get("source")
        if isinstance(source_name, str) and source_name in self.definition.sources:
            source = self.definition.sources[source_name]
            if source.source_type in {"api_endpoint", "http"}:
                base_url = str(
                    source.config.get("base_url") or (self.definition.manifest.base_url if self.definition.manifest else "")
                )
                return {**entity.properties, **HttpApiAdapter(base_url=base_url, client=self.http_client).fetch(source, entity)}
        if self.definition.manifest and self.definition.manifest.data_source_kind == "api_endpoint":
            source = BKNSource(
                name="manifest_api",
                source_type="api_endpoint",
                config={"path": entity.properties.get("endpoint", entity.id)},
                source_path=self.definition.manifest.source_path,
            )
            return {
                **entity.properties,
                **HttpApiAdapter(base_url=self.definition.manifest.base_url, client=self.http_client).fetch(source, entity),
            }
        return load_dynamic_data(
            root=self.definition.root,
            entity=entity,
            sources=self.definition.sources,
            suppress_errors=False,
        )


def _redact_mapping(payload: dict[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, value in payload.items():
        if any(secret in key.lower() for secret in ("token", "secret", "password", "authorization", "api_key")):
            redacted[key] = "[redacted]"
        else:
            redacted[key] = value
    return redacted
