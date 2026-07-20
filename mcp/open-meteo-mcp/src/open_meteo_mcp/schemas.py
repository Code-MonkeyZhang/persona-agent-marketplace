"""Pydantic schemas for Open-Meteo API request parameters.

Mirrors the Zod schemas in types.ts (TS version). All request schemas inherit from
Coordinate to enforce latitude/longitude bounds. API response bodies are forwarded to
the LLM as raw JSON and not validated here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

# Coordinate bounds in WGS84
DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
DATETIME_HOUR_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$"
COUNTRY_CODE_PATTERN = r"^[A-Z]{2}$"


class Coordinate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


TemperatureUnit = Literal["celsius", "fahrenheit"]
WindSpeedUnit = Literal["kmh", "ms", "mph", "kn"]
PrecipitationUnit = Literal["mm", "inch"]
TimeFormat = Literal["iso8601", "unixtime"]


class GeocodingParams(BaseModel):
    model_config = {"populate_by_name": True}

    name: str = Field(min_length=2)
    count: int | None = Field(default=10, ge=1, le=100)
    language: str | None = None
    country_code: str | None = Field(
        default=None, alias="countryCode", pattern=COUNTRY_CODE_PATTERN
    )
    format: Literal["json", "protobuf"] | None = "json"


# Forecast weather variables (hourly and daily)
HourlyVariable = Literal[
    "temperature_2m",
    "relative_humidity_2m",
    "dewpoint_2m",
    "apparent_temperature",
    "precipitation_probability",
    "precipitation",
    "rain",
    "showers",
    "snowfall",
    "snow_depth",
    "weather_code",
    "pressure_msl",
    "surface_pressure",
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "visibility",
    "evapotranspiration",
    "et0_fao_evapotranspiration",
    "vapour_pressure_deficit",
    "wind_speed_10m",
    "wind_speed_80m",
    "wind_speed_120m",
    "wind_speed_180m",
    "wind_direction_10m",
    "wind_direction_80m",
    "wind_direction_120m",
    "wind_direction_180m",
    "wind_gusts_10m",
    "temperature_80m",
    "temperature_120m",
    "temperature_180m",
    "soil_temperature_0cm",
    "soil_temperature_6cm",
    "soil_temperature_18cm",
    "soil_temperature_54cm",
    "soil_moisture_0_to_1cm",
    "soil_moisture_1_to_3cm",
    "soil_moisture_3_to_9cm",
    "soil_moisture_9_to_27cm",
    "soil_moisture_27_to_81cm",
    "uv_index",
    "uv_index_clear_sky",
    "is_day",
    "sunshine_duration",
    "wet_bulb_temperature_2m",
    "total_column_integrated_water_vapour",
    "cape",
    "lifted_index",
    "convective_inhibition",
    "freezing_level_height",
    "boundary_layer_height_pbl",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "direct_normal_irradiance",
    "global_tilted_irradiance",
    "terrestrial_radiation",
    "shortwave_radiation_instant",
    "direct_radiation_instant",
    "diffuse_radiation_instant",
    "direct_normal_irradiance_instant",
    "global_tilted_irradiance_instant",
    "terrestrial_radiation_instant",
]

DailyVariable = Literal[
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "sunrise",
    "sunset",
    "daylight_duration",
    "sunshine_duration",
    "uv_index_max",
    "uv_index_clear_sky_max",
    "rain_sum",
    "showers_sum",
    "snowfall_sum",
    "precipitation_sum",
    "precipitation_hours",
    "precipitation_probability_max",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
    "shortwave_radiation_sum",
    "et0_fao_evapotranspiration",
    "temperature_2m_mean",
    "apparent_temperature_mean",
    "cape_mean",
    "cape_max",
    "cape_min",
    "cloud_cover_mean",
    "cloud_cover_max",
    "cloud_cover_min",
    "dewpoint_2m_mean",
    "dewpoint_2m_max",
    "dewpoint_2m_min",
    "et0_fao_evapotranspiration_sum",
    "growing_degree_days_base_0_limit_50",
    "leaf_wetness_probability_mean",
    "leaf_wetness_probability_max",
    "leaf_wetness_probability_min",
    "precipitation_probability_mean",
    "precipitation_probability_min",
    "relative_humidity_2m_mean",
    "relative_humidity_2m_max",
    "relative_humidity_2m_min",
    "snowfall_water_equivalent_sum",
    "pressure_msl_mean",
    "pressure_msl_max",
    "pressure_msl_min",
    "surface_pressure_mean",
    "surface_pressure_max",
    "surface_pressure_min",
    "updraft_max",
    "visibility_mean",
    "visibility_max",
    "visibility_min",
    "wind_gusts_10m_mean",
    "wind_gusts_10m_min",
    "wind_speed_10m_mean",
    "wind_speed_10m_min",
    "wet_bulb_temperature_2m_mean",
    "wet_bulb_temperature_2m_max",
    "wet_bulb_temperature_2m_min",
    "vapour_pressure_deficit_max",
]

# Model IDs accepted by /v1/forecast (general-purpose multi-model endpoint)
ForecastModel = Literal[
    "ecmwf_ifs04",
    "ecmwf_ifs025",
    "ecmwf_aifs025_single",
    "cma_grapes_global",
    "bom_access_global",
    "gfs_seamless",
    "ncep_gfs_global",
    "ncep_hrrr_conus",
    "ncep_nbm_conus",
    "ncep_nam_conus",
    "ncep_gfs_graphcast025",
    "ncep_aigfs025",
    "ncep_hgefs025_ensemble_mean",
    "jma_seamless",
    "jma_msm",
    "jma_gsm",
    "kma_seamless",
    "kma_ldps",
    "kma_gdps",
    "dwd_icon_seamless",
    "dwd_icon_global",
    "dwd_icon_eu",
    "dwd_icon_d2",
    "gem_seamless",
    "gem_global",
    "gem_regional",
    "gem_hrdps_continental",
    "gem_hrdps_west",
    "meteofrance_seamless",
    "meteofrance_arpege_world",
    "meteofrance_arpege_europe",
    "meteofrance_arome_france",
    "meteofrance_arome_france_hd",
    "italia_meteo_arpae_icon_2i",
    "metno_seamless",
    "metno_nordic",
    "knmi_seamless",
    "knmi_harmonie_arome_europe",
    "knmi_harmonie_arome_netherlands",
    "dmi_seamless",
    "dmi_harmonie_arome_europe",
    "ukmo_seamless",
    "ukmo_global_deterministic_10km",
    "ukmo_uk_deterministic_2km",
    "meteoswiss_icon_seamless",
    "meteoswiss_icon_ch1",
    "meteoswiss_icon_ch2",
]

# Valid model IDs for the dedicated /v1/ecmwf endpoint (different from /v1/forecast)
EcmwfModel = Literal["ecmwf_ifs", "ecmwf_ifs025", "best_match"]

EnsembleModel = Literal[
    "icon_seamless_eps",
    "icon_global_eps",
    "icon_eu_eps",
    "icon_d2_eps",
    "gfs_seamless",
    "ncep_gefs025",
    "ncep_gefs05",
    "ncep_aigefs025",
    "ecmwf_ifs025_ensemble",
    "ecmwf_aifs025_ensemble",
    "gem_global",
    "bom_access_global",
    "ukmo_global_ensemble_20km",
    "ukmo_uk_ensemble_2km",
    "meteoswiss_icon_ch1",
    "meteoswiss_icon_ch2",
]


class ForecastParams(Coordinate):
    hourly: list[HourlyVariable] | None = None
    daily: list[DailyVariable] | None = None
    current_weather: bool | None = None
    current: list[HourlyVariable] | None = None
    temperature_unit: TemperatureUnit = "celsius"
    wind_speed_unit: WindSpeedUnit = "kmh"
    precipitation_unit: PrecipitationUnit = "mm"
    timeformat: TimeFormat = "iso8601"
    timezone: str | None = None
    past_days: int | None = Field(default=None, ge=1, le=92)
    forecast_days: int | None = Field(default=None, ge=1, le=16)
    start_date: str | None = Field(default=None, pattern=DATE_PATTERN)
    end_date: str | None = Field(default=None, pattern=DATE_PATTERN)
    start_hour: str | None = Field(default=None, pattern=DATETIME_HOUR_PATTERN)
    end_hour: str | None = Field(default=None, pattern=DATETIME_HOUR_PATTERN)
    models: ForecastModel | None = None


class EcmwfParams(Coordinate):
    hourly: list[HourlyVariable] | None = None
    daily: list[DailyVariable] | None = None
    current_weather: bool | None = None
    current: list[HourlyVariable] | None = None
    temperature_unit: TemperatureUnit = "celsius"
    wind_speed_unit: WindSpeedUnit = "kmh"
    precipitation_unit: PrecipitationUnit = "mm"
    timeformat: TimeFormat = "iso8601"
    timezone: str | None = None
    past_days: int | None = Field(default=None, ge=1, le=92)
    forecast_days: int | None = Field(default=None, ge=1, le=16)
    start_date: str | None = Field(default=None, pattern=DATE_PATTERN)
    end_date: str | None = Field(default=None, pattern=DATE_PATTERN)
    start_hour: str | None = Field(default=None, pattern=DATETIME_HOUR_PATTERN)
    end_hour: str | None = Field(default=None, pattern=DATETIME_HOUR_PATTERN)
    models: EcmwfModel | None = None


# ERA5 archive-specific variable schemas (different from forecast API)
ArchiveHourlyVariable = Literal[
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "snowfall",
    "snow_depth",
    "weather_code",
    "pressure_msl",
    "surface_pressure",
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "et0_fao_evapotranspiration",
    "vapour_pressure_deficit",
    "wind_speed_10m",
    "wind_speed_100m",
    "wind_direction_10m",
    "wind_direction_100m",
    "wind_gusts_10m",
    "soil_temperature_0_to_7cm",
    "soil_temperature_7_to_28cm",
    "soil_temperature_28_to_100cm",
    "soil_temperature_100_to_255cm",
    "soil_moisture_0_to_7cm",
    "soil_moisture_7_to_28cm",
    "soil_moisture_28_to_100cm",
    "soil_moisture_100_to_255cm",
    "surface_temperature",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "direct_normal_irradiance",
    "terrestrial_radiation",
    "shortwave_radiation_instant",
    "direct_radiation_instant",
    "diffuse_radiation_instant",
    "direct_normal_irradiance_instant",
    "terrestrial_radiation_instant",
    "sunshine_duration",
    "is_day",
]

ArchiveDailyVariable = Literal[
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "apparent_temperature_mean",
    "sunrise",
    "sunset",
    "daylight_duration",
    "sunshine_duration",
    "precipitation_sum",
    "rain_sum",
    "snowfall_sum",
    "precipitation_hours",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
    "shortwave_radiation_sum",
    "et0_fao_evapotranspiration",
]


class ArchiveParams(Coordinate):
    hourly: list[ArchiveHourlyVariable] | None = None
    daily: list[ArchiveDailyVariable] | None = None
    start_date: str = Field(pattern=DATE_PATTERN)
    end_date: str = Field(pattern=DATE_PATTERN)
    temperature_unit: TemperatureUnit = "celsius"
    wind_speed_unit: WindSpeedUnit = "kmh"
    precipitation_unit: PrecipitationUnit = "mm"
    timeformat: TimeFormat = "iso8601"
    timezone: str | None = None

    @model_validator(mode="after")
    def check_date_range(self) -> ArchiveParams:
        if self.start_date > self.end_date:
            raise ValueError("start_date must be before or equal to end_date")
        return self


AirQualityVariable = Literal[
    "pm10",
    "pm2_5",
    "carbon_monoxide",
    "nitrogen_dioxide",
    "ozone",
    "sulphur_dioxide",
    "ammonia",
    "dust",
    "aerosol_optical_depth",
    "carbon_dioxide",
    "methane",
    "alder_pollen",
    "birch_pollen",
    "grass_pollen",
    "mugwort_pollen",
    "olive_pollen",
    "ragweed_pollen",
    "european_aqi",
    "european_aqi_pm2_5",
    "european_aqi_pm10",
    "european_aqi_nitrogen_dioxide",
    "european_aqi_ozone",
    "european_aqi_sulphur_dioxide",
    "us_aqi",
    "us_aqi_pm2_5",
    "us_aqi_pm10",
    "us_aqi_nitrogen_dioxide",
    "us_aqi_ozone",
    "us_aqi_sulphur_dioxide",
    "us_aqi_carbon_monoxide",
    "uv_index",
    "uv_index_clear_sky",
]


class AirQualityParams(Coordinate):
    hourly: list[AirQualityVariable] | None = None
    timezone: str | None = None
    timeformat: TimeFormat = "iso8601"
    past_days: int | None = Field(default=None, ge=1, le=7)
    forecast_days: int | None = Field(default=None, ge=1, le=16)


MarineHourlyVariable = Literal[
    "wave_height",
    "wave_direction",
    "wave_period",
    "wave_peak_period",
    "wind_wave_height",
    "wind_wave_direction",
    "wind_wave_period",
    "wind_wave_peak_period",
    "swell_wave_height",
    "swell_wave_direction",
    "swell_wave_period",
    "swell_wave_peak_period",
    "secondary_swell_wave_height",
    "secondary_swell_wave_period",
    "secondary_swell_wave_direction",
    "tertiary_swell_wave_height",
    "tertiary_swell_wave_period",
    "tertiary_swell_wave_direction",
    "sea_level_height_msl",
    "sea_surface_temperature",
    "ocean_current_velocity",
    "ocean_current_direction",
    "invert_barometer_height",
]

MarineDailyVariable = Literal[
    "wave_height_max",
    "wave_direction_dominant",
    "wave_period_max",
    "wind_wave_height_max",
    "wind_wave_direction_dominant",
    "wind_wave_period_max",
    "wind_wave_peak_period_max",
    "swell_wave_height_max",
    "swell_wave_direction_dominant",
    "swell_wave_period_max",
    "swell_wave_peak_period_max",
]


class MarineParams(Coordinate):
    hourly: list[MarineHourlyVariable] | None = None
    daily: list[MarineDailyVariable] | None = None
    timezone: str | None = None
    timeformat: TimeFormat = "iso8601"
    past_days: int | None = Field(default=None, ge=1, le=7)
    forecast_days: int | None = Field(default=None, ge=1, le=16)


FloodDailyVariable = Literal[
    "river_discharge",
    "river_discharge_mean",
    "river_discharge_median",
    "river_discharge_max",
    "river_discharge_min",
    "river_discharge_p25",
    "river_discharge_p75",
]


class FloodParams(Coordinate):
    daily: list[FloodDailyVariable] | None = None
    timezone: str | None = None
    timeformat: TimeFormat = "iso8601"
    past_days: int | None = Field(default=None, ge=1, le=7)
    forecast_days: int | None = Field(default=None, ge=1, le=210)
    start_date: str | None = Field(default=None, pattern=DATE_PATTERN)
    end_date: str | None = Field(default=None, pattern=DATE_PATTERN)
    ensemble: bool | None = None
    cell_selection: Literal["land", "sea", "nearest"] | None = "nearest"


SeasonalHourlyVariable = Literal[
    "pressure_msl",
    "temperature_2m",
    "temperature_2m_max",
    "temperature_2m_min",
    "shortwave_radiation",
    "cloud_cover",
    "precipitation",
    "showers",
    "wind_speed_10m",
    "wind_direction_10m",
    "relative_humidity_2m",
    "soil_temperature_0_to_10cm",
    "soil_moisture_0_to_10cm",
    "soil_moisture_10_to_40cm",
    "soil_moisture_40_to_100cm",
    "soil_moisture_100_to_200cm",
]

SeasonalDailyVariable = Literal[
    "temperature_2m_max",
    "temperature_2m_min",
    "shortwave_radiation_sum",
    "precipitation_sum",
    "rain_sum",
    "precipitation_hours",
    "wind_speed_10m_max",
    "wind_direction_10m_dominant",
]


class SeasonalParams(Coordinate):
    hourly: list[SeasonalHourlyVariable] | None = None
    daily: list[SeasonalDailyVariable] | None = None
    forecast_days: Literal[45, 92, 183, 274] | None = None
    past_days: int | None = Field(default=None, ge=0, le=92)
    start_date: str | None = Field(default=None, pattern=DATE_PATTERN)
    end_date: str | None = Field(default=None, pattern=DATE_PATTERN)
    temperature_unit: TemperatureUnit = "celsius"
    wind_speed_unit: WindSpeedUnit = "kmh"
    precipitation_unit: PrecipitationUnit = "mm"
    timezone: str | None = None


ClimateModel = Literal[
    "CMCC_CM2_VHR4",
    "FGOALS_f3_H",
    "HiRAM_SIT_HR",
    "MRI_AGCM3_2_S",
    "EC_Earth3P_HR",
    "MPI_ESM1_2_XR",
    "NICAM16_8S",
]

ClimateDailyVariable = Literal[
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "cloud_cover_mean",
    "relative_humidity_2m_max",
    "relative_humidity_2m_min",
    "relative_humidity_2m_mean",
    "soil_moisture_0_to_10cm_mean",
    "precipitation_sum",
    "rain_sum",
    "snowfall_sum",
    "wind_speed_10m_mean",
    "wind_speed_10m_max",
    "pressure_msl_mean",
    "shortwave_radiation_sum",
]


class ClimateParams(Coordinate):
    daily: list[ClimateDailyVariable]
    start_date: str = Field(pattern=DATE_PATTERN)
    end_date: str = Field(pattern=DATE_PATTERN)
    models: list[ClimateModel] | None = None
    temperature_unit: TemperatureUnit = "celsius"
    wind_speed_unit: WindSpeedUnit = "kmh"
    precipitation_unit: PrecipitationUnit = "mm"
    disable_bias_correction: bool | None = None

    @model_validator(mode="after")
    def check_date_range(self) -> ClimateParams:
        if self.start_date > self.end_date:
            raise ValueError("start_date must be before or equal to end_date")
        return self


EnsembleHourlyVariable = Literal[
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "snowfall",
    "snow_depth",
    "weather_code",
    "pressure_msl",
    "surface_pressure",
    "cloud_cover",
    "visibility",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "wind_speed_80m",
    "wind_direction_80m",
    "wind_speed_100m",
    "wind_direction_100m",
    "surface_temperature",
    "soil_temperature_0_to_10cm",
    "cape",
    "et0_fao_evapotranspiration",
    "vapour_pressure_deficit",
    "shortwave_radiation",
    "uv_index",
    "uv_index_clear_sky",
    "temperature_3h_min_2m",
    "temperature_3h_max_2m",
    "wet_bulb_temperature_2m",
    "convective_inhibition",
    "freezing_level_height",
    "snowfall_height",
    "sunshine_duration",
    "snowfall_water_equivalent",
    "snow_depth_water_equivalent",
]

EnsembleDailyVariable = Literal[
    "temperature_2m_mean",
    "temperature_2m_min",
    "temperature_2m_max",
    "apparent_temperature_mean",
    "apparent_temperature_min",
    "apparent_temperature_max",
    "wind_speed_10m_mean",
    "wind_speed_10m_min",
    "wind_speed_10m_max",
    "wind_direction_10m_dominant",
    "wind_gusts_10m_mean",
    "wind_gusts_10m_min",
    "wind_gusts_10m_max",
    "wind_speed_100m_mean",
    "wind_speed_100m_min",
    "wind_speed_100m_max",
    "wind_direction_100m_dominant",
    "precipitation_sum",
    "precipitation_hours",
    "rain_sum",
    "snowfall_sum",
    "pressure_msl_mean",
    "pressure_msl_min",
    "pressure_msl_max",
    "surface_pressure_mean",
    "surface_pressure_min",
    "surface_pressure_max",
    "cloud_cover_mean",
    "cloud_cover_min",
    "cloud_cover_max",
    "relative_humidity_2m_mean",
    "relative_humidity_2m_min",
    "relative_humidity_2m_max",
    "dew_point_2m_mean",
    "dew_point_2m_min",
    "dew_point_2m_max",
    "cape_mean",
    "cape_min",
    "cape_max",
    "shortwave_radiation_sum",
]


class EnsembleParams(Coordinate):
    models: EnsembleModel | None = None
    hourly: list[EnsembleHourlyVariable] | None = None
    daily: list[EnsembleDailyVariable] | None = None
    forecast_days: int | None = Field(default=None, ge=1, le=35)
    temperature_unit: TemperatureUnit = "celsius"
    wind_speed_unit: WindSpeedUnit = "kmh"
    precipitation_unit: PrecipitationUnit = "mm"
    timezone: str | None = None


class ElevationParams(Coordinate):
    pass
