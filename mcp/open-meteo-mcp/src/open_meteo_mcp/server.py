"""Open-Meteo MCP server.

Stdio-only MCP server exposing Open-Meteo weather APIs as 17 tools. Mirrors the
architecture of index.ts (TS version): a single Server instance with list_tools and
call_tool handlers, structured JSON logs to stderr.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from pydantic import BaseModel, ValidationError

from .client import OpenMeteoClient
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
from .tools import ALL_TOOLS

SERVER_NAME = "open-meteo-mcp"
SERVER_VERSION = "1.6.1"

# Maps tool name → (Pydantic param model, client getter method name).
# Single source of truth for the 17-tool dispatch; mirrors the switch/case in index.ts.
TOOL_HANDLERS: dict[str, tuple[type[BaseModel], str]] = {
    "weather_forecast": (ForecastParams, "get_forecast"),
    "weather_archive": (ArchiveParams, "get_archive"),
    "air_quality": (AirQualityParams, "get_air_quality"),
    "marine_weather": (MarineParams, "get_marine"),
    "elevation": (ElevationParams, "get_elevation"),
    "flood_forecast": (FloodParams, "get_flood"),
    "geocoding": (GeocodingParams, "get_geocoding"),
    "dwd_icon_forecast": (ForecastParams, "get_dwd_icon"),
    "gfs_forecast": (ForecastParams, "get_gfs"),
    "meteofrance_forecast": (ForecastParams, "get_meteo_france"),
    "ecmwf_forecast": (EcmwfParams, "get_ecmwf"),
    "jma_forecast": (ForecastParams, "get_jma"),
    "metno_forecast": (ForecastParams, "get_metno"),
    "gem_forecast": (ForecastParams, "get_gem"),
    "seasonal_forecast": (SeasonalParams, "get_seasonal"),
    "climate_projection": (ClimateParams, "get_climate"),
    "ensemble_forecast": (EnsembleParams, "get_ensemble"),
}


def _log(level: str, event: str, **data: Any) -> None:
    """Write a structured JSON log line to stderr to keep stdout clean for MCP stdio protocol."""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "event": event,
        **data,
    }
    sys.stderr.write(f"{json.dumps(payload, ensure_ascii=False)}\n")


async def serve() -> None:
    """Run the MCP server over stdio until the client disconnects."""
    server = Server(SERVER_NAME)
    server.version = SERVER_VERSION
    client = OpenMeteoClient(version=SERVER_VERSION)

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=tool["name"],
                description=tool["description"],
                inputSchema=tool["inputSchema"],
            )
            for tool in ALL_TOOLS
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
        start = datetime.now(timezone.utc)
        _log("info", "tool_call", tool=name, args=arguments)

        try:
            handler = TOOL_HANDLERS.get(name)
            if handler is None:
                raise ValueError(f"Unknown tool: {name}")

            schema, method_name = handler
            try:
                params = schema.model_validate(arguments or {})
            except ValidationError as exc:
                raise ValueError(f"Invalid arguments: {exc}") from exc

            method = getattr(client, method_name)
            result = await method(params)
        except Exception as exc:
            duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            message = str(exc) or exc.__class__.__name__
            _log("error", "tool_error", tool=name, error=message, duration_ms=duration_ms)
            return [types.TextContent(type="text", text=f"Error: {message}")]

        response_text = json.dumps(result, indent=2, ensure_ascii=False)
        duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        _log(
            "info",
            "tool_success",
            tool=name,
            response_size=len(response_text),
            duration_ms=duration_ms,
        )
        return [types.TextContent(type="text", text=response_text)]

    _log("info", "server_start", transport="stdio")
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        await client.aclose()
