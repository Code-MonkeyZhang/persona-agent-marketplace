"""HTTP client for Open-Meteo APIs.

Wraps a single httpx.AsyncClient that targets the appropriate Open-Meteo subdomain
per endpoint. Mirrors the structure of client.ts (TS version) while consolidating the
nine axios instances into one client (httpx shares its connection pool naturally).
"""

from __future__ import annotations

from typing import Any

import httpx

from .schemas import (
    AirQualityParams,
    ArchiveParams,
    ClimateParams,
    EcmwfParams,
    ElevationParams,
    EnsembleParams,
    FloodParams,
    ForecastParams,
    GeocodingParams,
    MarineParams,
    SeasonalParams,
)

BASE_URLS: dict[str, str] = {
    "main": "https://api.open-meteo.com",
    "air_quality": "https://air-quality-api.open-meteo.com",
    "marine": "https://marine-api.open-meteo.com",
    "archive": "https://archive-api.open-meteo.com",
    "seasonal": "https://seasonal-api.open-meteo.com",
    "ensemble": "https://ensemble-api.open-meteo.com",
    "geocoding": "https://geocoding-api.open-meteo.com",
    "flood": "https://flood-api.open-meteo.com",
    "climate": "https://climate-api.open-meteo.com",
}

# Per-request timeout in seconds; matches the TS axios timeout
REQUEST_TIMEOUT = 30.0


def _map_http_error(error: httpx.HTTPStatusError) -> None:
    """Translate an HTTP error response into a structured Python error.

    Reads the Open-Meteo `reason` or `error` field from the response body so callers
    see a meaningful message instead of a bare status code.
    """
    status = error.response.status_code
    data: dict[str, Any] = error.response.json() if error.response.content else {}
    api_message = data.get("reason") or data.get("error") or str(error)

    if status == 400:
        raise ValueError(f"Invalid request parameters: {api_message}") from error
    if status == 422:
        raise ValueError(f"Invalid parameter value: {api_message}") from error
    if status == 429:
        raise RuntimeError("Open-Meteo rate limit reached. Please retry later.") from error
    if status >= 500:
        raise RuntimeError(f"Open-Meteo server error ({status}): {api_message}") from error
    raise RuntimeError(f"Open-Meteo request failed ({status}): {api_message}") from error


def _build_params(params: dict[str, Any]) -> dict[str, str]:
    """Serialise a params dict for httpx query strings.

    - Drops None values
    - Joins arrays with commas (e.g. `['a', 'b']` → `'a,b'`)
    - Coerces everything else to str
    """
    result: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, list):
            result[key] = ",".join(str(v) for v in value)
        else:
            result[key] = str(value)
    return result


class OpenMeteoClient:
    """Async client exposing one getter per Open-Meteo API endpoint."""

    def __init__(self, version: str = "unknown") -> None:
        self._client = httpx.AsyncClient(
            headers={
                "Accept": "application/json",
                "User-Agent": f"Open-Meteo-MCP-Server/{version}",
            },
            timeout=REQUEST_TIMEOUT,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> OpenMeteoClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def _get(self, host: str, path: str, params: Any) -> dict[str, Any]:
        """Issue a GET request, map HTTP errors, return the parsed JSON body."""
        query = _build_params(params.model_dump(by_alias=True, exclude_none=True))
        url = f"{BASE_URLS[host]}{path}"
        try:
            response = await self._client.get(url, params=query)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _map_http_error(exc)
            raise
        return response.json()

    # Main forecast API (api.open-meteo.com)
    async def get_forecast(self, params: ForecastParams) -> dict[str, Any]:
        return await self._get("main", "/v1/forecast", params)

    async def get_dwd_icon(self, params: ForecastParams) -> dict[str, Any]:
        return await self._get("main", "/v1/dwd-icon", params)

    async def get_gfs(self, params: ForecastParams) -> dict[str, Any]:
        return await self._get("main", "/v1/gfs", params)

    async def get_meteo_france(self, params: ForecastParams) -> dict[str, Any]:
        return await self._get("main", "/v1/meteofrance", params)

    async def get_ecmwf(self, params: EcmwfParams) -> dict[str, Any]:
        return await self._get("main", "/v1/ecmwf", params)

    async def get_jma(self, params: ForecastParams) -> dict[str, Any]:
        return await self._get("main", "/v1/jma", params)

    async def get_metno(self, params: ForecastParams) -> dict[str, Any]:
        return await self._get("main", "/v1/metno", params)

    async def get_gem(self, params: ForecastParams) -> dict[str, Any]:
        return await self._get("main", "/v1/gem", params)

    async def get_elevation(self, params: ElevationParams) -> dict[str, Any]:
        return await self._get("main", "/v1/elevation", params)

    # Dedicated subdomain APIs
    async def get_archive(self, params: ArchiveParams) -> dict[str, Any]:
        return await self._get("archive", "/v1/archive", params)

    async def get_air_quality(self, params: AirQualityParams) -> dict[str, Any]:
        return await self._get("air_quality", "/v1/air-quality", params)

    async def get_marine(self, params: MarineParams) -> dict[str, Any]:
        return await self._get("marine", "/v1/marine", params)

    async def get_ensemble(self, params: EnsembleParams) -> dict[str, Any]:
        return await self._get("ensemble", "/v1/ensemble", params)

    async def get_flood(self, params: FloodParams) -> dict[str, Any]:
        return await self._get("flood", "/v1/flood", params)

    async def get_seasonal(self, params: SeasonalParams) -> dict[str, Any]:
        return await self._get("seasonal", "/v1/seasonal", params)

    async def get_climate(self, params: ClimateParams) -> dict[str, Any]:
        return await self._get("climate", "/v1/climate", params)

    async def get_geocoding(self, params: GeocodingParams) -> dict[str, Any]:
        return await self._get("geocoding", "/v1/search", params)
