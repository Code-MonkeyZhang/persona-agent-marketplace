"""JSON Schema definitions for the 17 Open-Meteo MCP tools.

Mirrors tools.ts (TS version). Enum lists are pulled from the Pydantic Literal types in
schemas.py to avoid duplication. The 7 provider-specific forecast tools share the
weather_forecast input schema (with ECMWF overriding the `models` enum).
"""

from __future__ import annotations

from typing import Any, get_args

from .schemas import (
    AirQualityVariable,
    ArchiveDailyVariable,
    ArchiveHourlyVariable,
    ClimateDailyVariable,
    ClimateModel,
    DailyVariable,
    EcmwfModel,
    EnsembleDailyVariable,
    EnsembleHourlyVariable,
    EnsembleModel,
    FloodDailyVariable,
    ForecastModel,
    HourlyVariable,
    MarineDailyVariable,
    MarineHourlyVariable,
    SeasonalDailyVariable,
    SeasonalHourlyVariable,
)

# Extract enum values from Literal type aliases — single source of truth.
_HOURLY = list(get_args(HourlyVariable))
_DAILY = list(get_args(DailyVariable))
_ARCHIVE_HOURLY = list(get_args(ArchiveHourlyVariable))
_ARCHIVE_DAILY = list(get_args(ArchiveDailyVariable))
_AIR_QUALITY = list(get_args(AirQualityVariable))
_MARINE_HOURLY = list(get_args(MarineHourlyVariable))
_MARINE_DAILY = list(get_args(MarineDailyVariable))
_FLOOD_DAILY = list(get_args(FloodDailyVariable))
_SEASONAL_HOURLY = list(get_args(SeasonalHourlyVariable))
_SEASONAL_DAILY = list(get_args(SeasonalDailyVariable))
_CLIMATE_DAILY = list(get_args(ClimateDailyVariable))
_CLIMATE_MODELS = list(get_args(ClimateModel))
_ENSEMBLE_HOURLY = list(get_args(EnsembleHourlyVariable))
_ENSEMBLE_DAILY = list(get_args(EnsembleDailyVariable))
_ENSEMBLE_MODELS = list(get_args(EnsembleModel))
_FORECAST_MODELS = list(get_args(ForecastModel))
_ECMWF_MODELS = list(get_args(EcmwfModel))

# Shared JSON Schema fragments
_LATITUDE = {
    "type": "number",
    "minimum": -90,
    "maximum": 90,
    "description": "Latitude in WGS84 coordinate system",
}
_LONGITUDE = {
    "type": "number",
    "minimum": -180,
    "maximum": 180,
    "description": "Longitude in WGS84 coordinate system",
}
_COORD_PROPS: dict[str, Any] = {"latitude": _LATITUDE, "longitude": _LONGITUDE}

_TEMP_UNIT = {
    "type": "string",
    "enum": ["celsius", "fahrenheit"],
    "default": "celsius",
    "description": "Temperature unit",
}
_WIND_UNIT = {
    "type": "string",
    "enum": ["kmh", "ms", "mph", "kn"],
    "default": "kmh",
    "description": "Wind speed unit",
}
_PRECIP_UNIT = {
    "type": "string",
    "enum": ["mm", "inch"],
    "default": "mm",
    "description": "Precipitation unit",
}
_DATE_FIELD = {
    "type": "string",
    "pattern": r"^\d{4}-\d{2}-\d{2}$",
    "description": "Date in YYYY-MM-DD format",
}


def _enum_array(values: list[str], description: str) -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string", "enum": values},
        "description": description,
    }


# Forecast input schema (used by weather_forecast and 6 of 7 provider-specific tools).
# ECMWF reuses this with the `models` enum overridden below.
def _forecast_properties(models_enum: list[str], models_description: str) -> dict[str, Any]:
    return {
        **_COORD_PROPS,
        "hourly": _enum_array(_HOURLY, "Hourly weather variables to retrieve"),
        "daily": _enum_array(_DAILY, "Daily weather variables to retrieve"),
        "current_weather": {"type": "boolean", "description": "Include current weather conditions"},
        "current": _enum_array(
            _HOURLY,
            (
                "Current conditions variables to retrieve. Preferred over the deprecated "
                "current_weather boolean."
            ),
        ),
        "temperature_unit": _TEMP_UNIT,
        "wind_speed_unit": _WIND_UNIT,
        "precipitation_unit": _PRECIP_UNIT,
        "timezone": {
            "type": "string",
            "description": "Timezone for timestamps (e.g., Europe/Paris, America/New_York)",
        },
        "past_days": {
            "type": "integer",
            "minimum": 1,
            "maximum": 92,
            "description": "Include past days data (1-92)",
        },
        "forecast_days": {
            "type": "integer",
            "minimum": 1,
            "maximum": 16,
            "default": 7,
            "description": "Number of forecast days",
        },
        "start_date": _DATE_FIELD,
        "end_date": _DATE_FIELD,
        "start_hour": {
            "type": "string",
            "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$",
            "description": "Start hour in YYYY-MM-DDTHH:MM format",
        },
        "end_hour": {
            "type": "string",
            "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$",
            "description": "End hour in YYYY-MM-DDTHH:MM format",
        },
        "models": {
            "type": "string",
            "enum": models_enum,
            "description": models_description,
        },
    }


_FORECAST_DEFAULT_MODELS_DESC = (
    "Weather model to use. Only one model per request — multi-value arrays are not supported "
    "by the API. Omit this parameter to let the API automatically select the best model for "
    "the location (recommended). For multi-model comparison, make one parallel tool call per "
    "model using the appropriate provider-specific tool."
)

_FORECAST_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": _forecast_properties(_FORECAST_MODELS, _FORECAST_DEFAULT_MODELS_DESC),
    "required": ["latitude", "longitude"],
}

_ECMWF_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": _forecast_properties(
        _ECMWF_MODELS,
        'ECMWF model to use on the /v1/ecmwf endpoint. Valid values: "ecmwf_ifs" (IFS HRES '
        'high-resolution), "ecmwf_ifs025" (IFS open-data 0.25°), "best_match". Omit to use '
        "the endpoint default.",
    ),
    "required": ["latitude", "longitude"],
}


WEATHER_FORECAST_TOOL: dict[str, Any] = {
    "name": "weather_forecast",
    "description": (
        "Get weather forecast data for coordinates using Open-Meteo API. Supports hourly and "
        "daily data with various weather variables. When no `models` parameter is provided, "
        "the API automatically selects the best model for the given location (recommended). "
        "Only one model per request is supported — for multi-model comparison, use "
        "provider-specific tools with parallel calls."
    ),
    "inputSchema": _FORECAST_INPUT_SCHEMA,
}

WEATHER_ARCHIVE_TOOL: dict[str, Any] = {
    "name": "weather_archive",
    "description": (
        "Get historical weather data from ERA5 reanalysis (1940-present) for specific "
        "coordinates and date range."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            **_COORD_PROPS,
            "start_date": _DATE_FIELD,
            "end_date": _DATE_FIELD,
            "hourly": _enum_array(_ARCHIVE_HOURLY, "Hourly weather variables to retrieve"),
            "daily": _enum_array(_ARCHIVE_DAILY, "Daily weather variables to retrieve"),
            "temperature_unit": _TEMP_UNIT,
            "timezone": {"type": "string", "description": "Timezone for timestamps"},
        },
        "required": ["latitude", "longitude", "start_date", "end_date"],
    },
}

AIR_QUALITY_TOOL: dict[str, Any] = {
    "name": "air_quality",
    "description": (
        "Get air quality forecast data including PM2.5, PM10, ozone, nitrogen dioxide, "
        "pollen, European/US AQI indices, UV index and other pollutants."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            **_COORD_PROPS,
            "hourly": _enum_array(_AIR_QUALITY, "Air quality variables to retrieve"),
            "timezone": {"type": "string", "description": "Timezone for timestamps"},
            "past_days": {
                "type": "integer",
                "minimum": 1,
                "maximum": 7,
                "description": "Include past days data",
            },
            "forecast_days": {
                "type": "integer",
                "minimum": 1,
                "maximum": 16,
                "default": 7,
                "description": "Number of forecast days",
            },
        },
        "required": ["latitude", "longitude"],
    },
}

MARINE_WEATHER_TOOL: dict[str, Any] = {
    "name": "marine_weather",
    "description": (
        "Get marine weather forecast including wave height, wave period, wave direction "
        "and sea surface temperature."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            **_COORD_PROPS,
            "hourly": _enum_array(_MARINE_HOURLY, "Marine weather variables to retrieve"),
            "daily": _enum_array(_MARINE_DAILY, "Daily marine weather variables to retrieve"),
            "timezone": {"type": "string", "description": "Timezone for timestamps"},
            "past_days": {
                "type": "integer",
                "minimum": 1,
                "maximum": 7,
                "description": "Include past days data",
            },
            "forecast_days": {
                "type": "integer",
                "minimum": 1,
                "maximum": 16,
                "default": 7,
                "description": "Number of forecast days",
            },
        },
        "required": ["latitude", "longitude"],
    },
}

ELEVATION_TOOL: dict[str, Any] = {
    "name": "elevation",
    "description": "Get elevation data for given coordinates using digital elevation models.",
    "inputSchema": {
        "type": "object",
        "properties": {**_COORD_PROPS},
        "required": ["latitude", "longitude"],
    },
}

FLOOD_FORECAST_TOOL: dict[str, Any] = {
    "name": "flood_forecast",
    "description": (
        "Get river discharge and flood forecasts from GloFAS (Global Flood Awareness System)."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            **_COORD_PROPS,
            "daily": _enum_array(_FLOOD_DAILY, "River discharge variables to retrieve"),
            "timezone": {"type": "string", "description": "Timezone for timestamps"},
            "past_days": {
                "type": "integer",
                "minimum": 1,
                "maximum": 7,
                "description": "Include past days data",
            },
            "forecast_days": {
                "type": "integer",
                "minimum": 1,
                "maximum": 210,
                "default": 92,
                "description": "Number of forecast days (up to 210 days possible)",
            },
            "ensemble": {
                "type": "boolean",
                "description": "If true, all forecast ensemble members will be returned",
            },
        },
        "required": ["latitude", "longitude"],
    },
}

SEASONAL_FORECAST_TOOL: dict[str, Any] = {
    "name": "seasonal_forecast",
    "description": (
        "Get long-range seasonal forecasts for temperature and precipitation up to 9 "
        "months ahead."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            **_COORD_PROPS,
            "hourly": _enum_array(_SEASONAL_HOURLY, "6-hourly weather variables to retrieve"),
            "daily": _enum_array(_SEASONAL_DAILY, "Daily weather variables to retrieve"),
            "forecast_days": {
                "type": "integer",
                "enum": [45, 92, 183, 274],
                "default": 92,
                "description": (
                    "Number of forecast days: 45 days, 3 months (default), 6 months, or 9 "
                    "months"
                ),
            },
            "past_days": {
                "type": "integer",
                "minimum": 0,
                "maximum": 92,
                "description": "Include past days data",
            },
            "start_date": _DATE_FIELD,
            "end_date": _DATE_FIELD,
            "temperature_unit": _TEMP_UNIT,
            "wind_speed_unit": _WIND_UNIT,
            "precipitation_unit": _PRECIP_UNIT,
            "timezone": {"type": "string", "description": "Timezone for timestamps"},
        },
        "required": ["latitude", "longitude"],
    },
}

CLIMATE_PROJECTION_TOOL: dict[str, Any] = {
    "name": "climate_projection",
    "description": (
        "Get climate change projections from CMIP6 models for different warming scenarios."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            **_COORD_PROPS,
            "daily": _enum_array(_CLIMATE_DAILY, "Climate projection variables to retrieve"),
            "start_date": _DATE_FIELD,
            "end_date": _DATE_FIELD,
            "models": _enum_array(_CLIMATE_MODELS, "CMIP6 climate models to use"),
            "temperature_unit": _TEMP_UNIT,
            "wind_speed_unit": _WIND_UNIT,
            "precipitation_unit": _PRECIP_UNIT,
            "disable_bias_correction": {
                "type": "boolean",
                "default": False,
                "description": "Disable statistical downscaling and bias correction",
            },
        },
        "required": ["latitude", "longitude", "start_date", "end_date", "models", "daily"],
    },
}

ENSEMBLE_FORECAST_TOOL: dict[str, Any] = {
    "name": "ensemble_forecast",
    "description": "Get ensemble forecasts showing forecast uncertainty with multiple model runs.",
    "inputSchema": {
        "type": "object",
        "properties": {
            **_COORD_PROPS,
            "models": {
                "type": "string",
                "enum": _ENSEMBLE_MODELS,
                "description": "Ensemble model to use. Only one model per request is supported.",
            },
            "hourly": _enum_array(_ENSEMBLE_HOURLY, "Hourly weather variables to retrieve"),
            "daily": _enum_array(_ENSEMBLE_DAILY, "Daily weather variables to retrieve"),
            "forecast_days": {
                "type": "integer",
                "minimum": 1,
                "maximum": 35,
                "default": 7,
                "description": "Number of forecast days",
            },
            "temperature_unit": _TEMP_UNIT,
            "wind_speed_unit": _WIND_UNIT,
            "precipitation_unit": _PRECIP_UNIT,
            "timezone": {"type": "string", "description": "Timezone for timestamps"},
        },
        "required": ["latitude", "longitude", "models"],
    },
}

GEOCODING_TOOL: dict[str, Any] = {
    "name": "geocoding",
    "description": (
        "Search for locations worldwide by place name or postal code. Returns geographic "
        "coordinates (latitude and longitude) and detailed location information. Use this "
        'tool when you need to convert a location name (e.g., "Paris", "New York") into '
        "precise coordinates (latitude/longitude) that are required by other tools. This is "
        "essential when you have a location name but need coordinates for data fetching tools."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "minLength": 2,
                "description": (
                    'Place name or postal code to search for. Minimum 2 characters required. '
                    'Examples: "Paris", "Berlin", "75001", "10967"'
                ),
            },
            "count": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "default": 10,
                "description": "Number of search results to return (maximum 100)",
            },
            "language": {
                "type": "string",
                "description": (
                    'Language code for translated results (e.g., "fr", "en", "de"). Returns '
                    "translated results if available, otherwise in English or native language."
                ),
            },
            "countryCode": {
                "type": "string",
                "pattern": r"^[A-Z]{2}$",
                "description": (
                    'ISO-3166-1 alpha2 country code to filter results (e.g., "FR", "DE", '
                    '"US"). Limits search to a specific country.'
                ),
            },
            "format": {
                "type": "string",
                "enum": ["json", "protobuf"],
                "default": "json",
                "description": "Return format for results",
            },
        },
        "required": ["name"],
    },
}


def _make_provider_tool(name: str, description: str) -> dict[str, Any]:
    """Build a provider-specific forecast tool that reuses the forecast input schema."""
    return {"name": name, "description": description, "inputSchema": _FORECAST_INPUT_SCHEMA}


# Provider-specific forecast tools. All share the weather_forecast input schema (which
# exposes the full ForecastModel enum) — only the description guides the LLM to the right
# model id. ECMWF is the exception: it lives on /v1/ecmwf with a different model namespace.
WEATHER_MODEL_TOOLS: list[dict[str, Any]] = [
    _make_provider_tool(
        "dwd_icon_forecast",
        "Get weather forecast from German DWD ICON model. IMPORTANT: Specify exactly one "
        'DWD model in the `models` parameter (e.g., "dwd_icon_global") — only one model per '
        "request is supported. For multi-model comparison, make one parallel tool call per "
        "model using the appropriate provider-specific tool.",
    ),
    _make_provider_tool(
        "gfs_forecast",
        "Get weather forecast from US NOAA GFS model. IMPORTANT: Specify exactly one GFS "
        'model in the `models` parameter (e.g., "ncep_gfs_global") — only one model per '
        "request is supported. For multi-model comparison, make one parallel tool call per "
        "model using the appropriate provider-specific tool.",
    ),
    _make_provider_tool(
        "meteofrance_forecast",
        "Get weather forecast from French Météo-France models. IMPORTANT: Specify exactly "
        "one Météo-France model in the `models` parameter (e.g., "
        '"meteofrance_arome_france" or "meteofrance_arpege_europe") — only one model per '
        "request is supported. For multi-model comparison, make one parallel tool call per "
        "model using the appropriate provider-specific tool.",
    ),
    {
        "name": "ecmwf_forecast",
        "description": (
            "Get weather forecast from ECMWF models via the dedicated /v1/ecmwf endpoint. "
            "IMPORTANT: Specify exactly one model in the `models` parameter — only one model "
            'per request is supported. Valid model IDs for this endpoint are: "ecmwf_ifs" '
            '(IFS HRES, high-resolution), "ecmwf_ifs025" (IFS open-data at 0.25°), '
            '"best_match". Note: "ecmwf_ifs_025", "ecmwf_ifs_hres_9km", and '
            '"ecmwf_aifs_025_single" are NOT valid on this endpoint and will return 400. '
            "For multi-model comparison, make one parallel tool call per model using the "
            "appropriate provider-specific tool."
        ),
        "inputSchema": _ECMWF_INPUT_SCHEMA,
    },
    _make_provider_tool(
        "jma_forecast",
        "Get weather forecast from Japan Meteorological Agency (JMA) models. IMPORTANT: "
        'Specify exactly one JMA model in the `models` parameter (e.g., "jma_msm" or '
        '"jma_gsm") — only one model per request is supported. For multi-model comparison, '
        "make one parallel tool call per model using the appropriate provider-specific tool.",
    ),
    _make_provider_tool(
        "metno_forecast",
        "Get weather forecast from Norwegian Meteorological Institute models. The `models` "
        "parameter is optional for this tool — omit it to use the default Met.no model. If "
        'specified, use canonical names such as "metno_nordic" or "metno_seamless". Only '
        "one model per request is supported. For multi-model comparison, make one parallel "
        "tool call per model using the appropriate provider-specific tool.",
    ),
    _make_provider_tool(
        "gem_forecast",
        "Get weather forecast from Canadian Meteorological Centre (GEM) models. IMPORTANT: "
        'Specify exactly one GEM model in the `models` parameter (e.g., "gem_global" or '
        '"gem_regional") — only one model per request is supported. For multi-model '
        "comparison, make one parallel tool call per model using the appropriate "
        "provider-specific tool.",
    ),
]

ALL_TOOLS: list[dict[str, Any]] = [
    WEATHER_FORECAST_TOOL,
    WEATHER_ARCHIVE_TOOL,
    AIR_QUALITY_TOOL,
    MARINE_WEATHER_TOOL,
    ELEVATION_TOOL,
    FLOOD_FORECAST_TOOL,
    SEASONAL_FORECAST_TOOL,
    CLIMATE_PROJECTION_TOOL,
    ENSEMBLE_FORECAST_TOOL,
    GEOCODING_TOOL,
    *WEATHER_MODEL_TOOLS,
]
