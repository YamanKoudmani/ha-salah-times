"""API clients for the Salah Times integration.

Provides two API client classes (AlAdhanClient, IslamicAppClient) and a
failover-wrapping SalahTimesAPI that tries the primary provider first and
falls back to the secondary on failure.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
import logging
from typing import Any
import zoneinfo

import aiohttp
import async_timeout

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.dt import as_utc, get_default_time_zone

from .const import MAX_RETRIES, PROVIDER_ALADHAN, PROVIDER_ISLAMIC_APP
from .models import PrayerName, PrayerTimes

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Date parsing helper — AlAdhan returns DD-MM-YYYY, not ISO format
# ---------------------------------------------------------------------------


def _parse_api_date(date_str: str) -> date:
    """Parse a date string from the prayer times API.

    AlAdhan returns Gregorian dates in ``DD-MM-YYYY`` format (e.g.
    ``"01-06-2026"`` for June 1st).  This helper handles that format
    and falls back to ISO ``YYYY-MM-DD`` for robustness.

    Args:
        date_str: The date string from the API response.

    Returns:
        The parsed ``date`` object.

    Raises:
        ValueError: If the string cannot be parsed in either format.
    """
    # Try DD-MM-YYYY first (AlAdhan's actual format)
    parts = date_str.split("-")
    if len(parts) == 3:
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        if day > 12 or (day <= 12 and month > 12):
            # First number is definitely the day (DD-MM-YYYY)
            return date(year, month, day)
        # Ambiguous case (both <= 12): AlAdhan uses DD-MM-YYYY, so prefer that
        return date(year, month, day)
    # Fallback: try ISO format
    return date.fromisoformat(date_str)

# ---------------------------------------------------------------------------
# Prayer timing key mapping (shared across providers)
# ---------------------------------------------------------------------------
_API_PRAYER_MAP: dict[str, PrayerName] = {
    "Fajr": PrayerName.FAJR,
    "Sunrise": PrayerName.SUNRISE,
    "Dhuhr": PrayerName.DHUHR,
    "Asr": PrayerName.ASR,
    "Maghrib": PrayerName.MAGHRIB,
    "Isha": PrayerName.ISHA,
    "Imsak": PrayerName.IMSAK,
    "Midnight": PrayerName.MIDNIGHT,
}

_PRAYER_TIMING_KEYS: frozenset = frozenset(_API_PRAYER_MAP.keys())

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SalahTimesAPIError(HomeAssistantError):
    """Base exception for all Salah Times API errors."""


class SalahTimesConnectionError(SalahTimesAPIError):
    """Raised when a network-level failure occurs (timeout, DNS, connection refused)."""


class SalahTimesRateLimitError(SalahTimesAPIError):
    """Raised when the API responds with HTTP 429 (rate limited)."""


# ---------------------------------------------------------------------------
# Retryable exceptions (recoverable — triggers failover)
# ---------------------------------------------------------------------------

_RETRYABLE_ERRORS: tuple[type[Exception], ...] = (
    SalahTimesConnectionError,
    SalahTimesRateLimitError,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _parse_timing_to_utc(
    time_str: str,
    gregorian_date: date,
    tz_info: datetime.tzinfo | None = None,
) -> datetime:
    """Convert an ``HH:MM`` timing string to a timezone-aware UTC datetime.

    The time is interpreted in the timezone given by *tz_info* (or, if
    ``None``, in Home Assistant's configured timezone), then converted to
    UTC for consistent storage.
    """
    hour_str, minute_str = time_str.split(":", 1)
    hour = int(hour_str)
    minute = int(minute_str)
    if tz_info is None:
        tz_info = get_default_time_zone()
    local_dt = datetime(
        gregorian_date.year,
        gregorian_date.month,
        gregorian_date.day,
        hour,
        minute,
        tzinfo=tz_info,
    )
    return as_utc(local_dt)


def _parse_timings_dict(
    timings_json: dict[str, str],
    gregorian_date: date,
    tz_info: datetime.tzinfo | None = None,
) -> dict[PrayerName, datetime]:
    """Parse the raw timings JSON dict into PrayerName → UTC datetime."""
    result: dict[PrayerName, datetime] = {}
    for key, time_str in timings_json.items():
        if key in _PRAYER_TIMING_KEYS:
            result[_API_PRAYER_MAP[key]] = _parse_timing_to_utc(
                time_str, gregorian_date, tz_info
            )
    return result


# ---------------------------------------------------------------------------
# AlAdhan client
# ---------------------------------------------------------------------------


class AlAdhanClient:
    """Client for the AlAdhan prayer times REST API (https://api.aladhan.com/v1).

    Free, keyless, ~14 req/s per IP.
    """

    BASE_URL = "https://api.aladhan.com/v1"

    def __init__(self, session: aiohttp.ClientSession, timeout: float = 10.0) -> None:
        """Initialise the AlAdhan API client.

        Args:
            session: An ``aiohttp.ClientSession`` (obtained via
                ``async_get_clientsession`` in ``__init__.py``).
            timeout: Maximum seconds to wait for a response.
        """
        self._session = session
        self._timeout = timeout

    async def _request(
        self, method: str, path: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Make an HTTP request and return the parsed JSON body.

        Raises:
            SalahTimesConnectionError: On ``asyncio.TimeoutError`` or
                ``aiohttp.ClientError``.
            SalahTimesRateLimitError: On HTTP 429.
            SalahTimesAPIError: On any other non-2xx status.
        """
        url = f"{self.BASE_URL}{path}"
        try:
            async with async_timeout.timeout(self._timeout):
                async with self._session.request(method, url, params=params) as resp:
                    if resp.status == 429:
                        raise SalahTimesRateLimitError(
                            f"AlAdhan rate limited (429): {url}"
                        )
                    if resp.status >= 400:
                        body = await resp.text()
                        raise SalahTimesAPIError(
                            f"AlAdhan HTTP {resp.status}: {url} - {body}"
                        )
                    return await resp.json()
        except asyncio.TimeoutError as err:
            raise SalahTimesConnectionError(
                f"AlAdhan request timed out: {url}"
            ) from err
        except aiohttp.ClientError as err:
            raise SalahTimesConnectionError(
                f"AlAdhan connection error: {url} - {err}"
            ) from err

    async def async_get_timings(
        self,
        *,
        latitude: float,
        longitude: float,
        date: date,
        method: int,
        school: int,
        latitude_adjustment_method: int,
        hijri_adjustment_days: int,
    ) -> PrayerTimes:
        """Fetch daily prayer timings from the ``/timings/{date}`` endpoint.

        Returns:
            A ``PrayerTimes`` instance parsed from the API response.

        Raises:
            SalahTimesConnectionError: On network failure.
            SalahTimesRateLimitError: On HTTP 429.
            SalahTimesAPIError: On other API errors.
        """
        date_str = date.strftime("%d-%m-%Y")
        params: dict[str, str] = {
            "latitude": str(latitude),
            "longitude": str(longitude),
            "method": str(method),
            "school": str(school),
            "latitudeAdjustmentMethod": str(latitude_adjustment_method),
            "adjustment": str(hijri_adjustment_days),
        }
        json_data = await self._request("GET", f"/timings/{date_str}", params)
        return self._parse_timings_response(json_data, PROVIDER_ALADHAN)

    async def async_get_month_calendar(
        self,
        *,
        latitude: float,
        longitude: float,
        method: int,
        school: int,
        latitude_adjustment_method: int,
        hijri_adjustment_days: int,
        month: int,
        year: int,
    ) -> dict[date, PrayerTimes]:
        """Fetch a full month of prayer times from the ``/calendar`` endpoint.

        Returns:
            A ``dict`` keyed by Gregorian ``date`` with ``PrayerTimes`` values.

        Raises:
            SalahTimesConnectionError: On network failure.
            SalahTimesRateLimitError: On HTTP 429.
            SalahTimesAPIError: On other API errors.
        """
        params: dict[str, str] = {
            "latitude": str(latitude),
            "longitude": str(longitude),
            "method": str(method),
            "school": str(school),
            "latitudeAdjustmentMethod": str(latitude_adjustment_method),
            "adjustment": str(hijri_adjustment_days),
            "month": str(month),
            "year": str(year),
        }
        json_data = await self._request("GET", "/calendar", params)
        data_list = json_data.get("data", [])
        result: dict[date, PrayerTimes] = {}
        for entry in data_list:
            pt = self._parse_timings_response({"data": entry}, PROVIDER_ALADHAN)
            result[pt.date] = pt
        return result

    @staticmethod
    def _parse_timings_response(
        json_data: dict[str, Any], provider: str
    ) -> PrayerTimes:
        """Parse a single-day AlAdhan API response into a ``PrayerTimes``.

        Expected JSON field paths (from ``tests/fixtures/aladhan_timings.json``):

        * timings:  ``data.timings.{Fajr,Sunrise,…}`` — ``"HH:MM"``
        * greg date: ``data.date.gregorian.date`` — ``"2026-06-21"``
        * hijri date: ``data.date.hijri.date`` — ``"05-01-1448"``
        * hijri month: ``data.date.hijri.month.en``
        * hijri year: ``data.date.hijri.year`` (string → int)
        * holidays: ``data.date.hijri.holidays`` (list)
        * method name: ``data.meta.method.name``
        """
        data = json_data["data"]
        timings_json: dict[str, str] = data["timings"]

        greg_json = data["date"]["gregorian"]
        greg_date = _parse_api_date(greg_json["date"])

        hijri_json = data["date"]["hijri"]
        hijri_date_str: str = hijri_json["date"]
        hijri_month: str = hijri_json["month"]["en"]
        hijri_year = int(hijri_json["year"])
        hijri_holidays: list[str] = hijri_json.get("holidays", [])

        calc_method: str = data.get("meta", {}).get("method", {}).get("name", "")

        # Extract timezone from API response meta
        tz_name: str | None = data.get("meta", {}).get("timezone")
        tz_info: datetime.tzinfo | None = None
        if tz_name:
            try:
                tz_info = zoneinfo.ZoneInfo(tz_name)
            except (TypeError, zoneinfo.ZoneInfoNotFoundError):
                pass

        timings = _parse_timings_dict(timings_json, greg_date, tz_info)

        return PrayerTimes(
            date=greg_date,
            timings=timings,
            hijri_date=hijri_date_str,
            hijri_month=hijri_month,
            hijri_year=hijri_year,
            hijri_holidays=hijri_holidays,
            calculation_method=calc_method,
            provider=provider,
        )


# ---------------------------------------------------------------------------
# Islamic.app client
# ---------------------------------------------------------------------------


class IslamicAppClient:
    """Client for the islamic.app prayer times REST API (https://api.islamic.app/v1).

    Free, keyless, 600 req/min, Cloudflare-backed.
    """

    BASE_URL = "https://api.islamic.app/v1"

    def __init__(self, session: aiohttp.ClientSession, timeout: float = 10.0) -> None:
        """Initialise the islamic.app API client.

        Args:
            session: An ``aiohttp.ClientSession``.
            timeout: Maximum seconds to wait for a response.
        """
        self._session = session
        self._timeout = timeout

    async def _request(
        self, method: str, path: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Make an HTTP request and return the parsed JSON body.

        Raises:
            SalahTimesConnectionError: On ``asyncio.TimeoutError`` or
                ``aiohttp.ClientError``.
            SalahTimesRateLimitError: On HTTP 429.
            SalahTimesAPIError: On any other non-2xx status.
        """
        url = f"{self.BASE_URL}{path}"
        try:
            async with async_timeout.timeout(self._timeout):
                async with self._session.request(method, url, params=params) as resp:
                    if resp.status == 429:
                        raise SalahTimesRateLimitError(
                            f"islamic.app rate limited (429): {url}"
                        )
                    if resp.status >= 400:
                        body = await resp.text()
                        raise SalahTimesAPIError(
                            f"islamic.app HTTP {resp.status}: {url} - {body}"
                        )
                    return await resp.json()
        except asyncio.TimeoutError as err:
            raise SalahTimesConnectionError(
                f"islamic.app request timed out: {url}"
            ) from err
        except aiohttp.ClientError as err:
            raise SalahTimesConnectionError(
                f"islamic.app connection error: {url} - {err}"
            ) from err

    async def async_get_timings(
        self,
        *,
        latitude: float,
        longitude: float,
        date: date,
        method: int,
        school: int,
        latitude_adjustment_method: int,
        hijri_adjustment_days: int,
    ) -> PrayerTimes:
        """Fetch daily prayer timings from islamic.app.

        Returns:
            A ``PrayerTimes`` instance.

        Raises:
            SalahTimesConnectionError: On network failure.
            SalahTimesRateLimitError: On HTTP 429.
            SalahTimesAPIError: On other API errors.
        """
        date_str = date.strftime("%d-%m-%Y")
        params: dict[str, str] = {
            "latitude": str(latitude),
            "longitude": str(longitude),
            "method": str(method),
            "school": str(school),
            "latitudeAdjustmentMethod": str(latitude_adjustment_method),
            "adjustment": str(hijri_adjustment_days),
        }
        json_data = await self._request("GET", f"/timings/{date_str}", params)
        return self._parse_timings_response(json_data, PROVIDER_ISLAMIC_APP)

    async def async_get_month_calendar(
        self,
        *,
        latitude: float,
        longitude: float,
        method: int,
        school: int,
        latitude_adjustment_method: int,
        hijri_adjustment_days: int,
        month: int,
        year: int,
    ) -> dict[date, PrayerTimes]:
        """Fetch a full month of prayer times from islamic.app.

        Returns:
            A ``dict`` keyed by Gregorian ``date`` with ``PrayerTimes`` values.

        Raises:
            SalahTimesConnectionError: On network failure.
            SalahTimesRateLimitError: On HTTP 429.
            SalahTimesAPIError: On other API errors.
        """
        params: dict[str, str] = {
            "latitude": str(latitude),
            "longitude": str(longitude),
            "method": str(method),
            "school": str(school),
            "latitudeAdjustmentMethod": str(latitude_adjustment_method),
            "adjustment": str(hijri_adjustment_days),
            "month": str(month),
            "year": str(year),
        }
        json_data = await self._request("GET", "/calendar", params)
        data_list = json_data.get("data", [])
        result: dict[date, PrayerTimes] = {}
        for entry in data_list:
            pt = self._parse_timings_response({"data": entry}, PROVIDER_ISLAMIC_APP)
            result[pt.date] = pt
        return result

    @staticmethod
    def _parse_timings_response(
        json_data: dict[str, Any], provider: str
    ) -> PrayerTimes:
        """Parse a single-day islamic.app API response into a ``PrayerTimes``.

        **Field-path differences from AlAdhan** (documented from fixture
        ``tests/fixtures/islamic_app_timings.json``):

        +---------------------------+-----------------------------+-------------------------------+
        | Field                     | AlAdhan path                | Islamic.app path              |
        +---------------------------+-----------------------------+-------------------------------+
        | Hijri month               | ``data.date.hijri.month.en``| ``data.date.hijri.month_name``|
        | Hijri year type           | string (→ ``int()``)        | int                           |
        | Method name               | ``data.meta.method.name``   | ``data.meta.method_name``     |
        | Gregorian weekday         | nested ``weekday.en``       | flat string                   |
        | Gregorian year/month/day  | strings / nested objects    | flat ints                     |
        +---------------------------+-----------------------------+-------------------------------+

        The timings dict, Gregorian ``date`` string, Hijri ``date`` string,
        and holidays list share the same structure as AlAdhan.
        """
        data = json_data["data"]
        timings_json: dict[str, str] = data["timings"]

        greg_json = data["date"]["gregorian"]
        greg_date = _parse_api_date(greg_json["date"])

        hijri_json = data["date"]["hijri"]
        hijri_date_str: str = hijri_json["date"]
        hijri_month: str = hijri_json["month_name"]
        hijri_year = int(hijri_json["year"])
        hijri_holidays: list[str] = hijri_json.get("holidays", [])

        calc_method: str = data.get("meta", {}).get("method_name", "")

        # Extract timezone from API response meta
        tz_name: str | None = data.get("meta", {}).get("timezone")
        tz_info: datetime.tzinfo | None = None
        if tz_name:
            try:
                tz_info = zoneinfo.ZoneInfo(tz_name)
            except (TypeError, zoneinfo.ZoneInfoNotFoundError):
                pass

        timings = _parse_timings_dict(timings_json, greg_date, tz_info)

        return PrayerTimes(
            date=greg_date,
            timings=timings,
            hijri_date=hijri_date_str,
            hijri_month=hijri_month,
            hijri_year=hijri_year,
            hijri_holidays=hijri_holidays,
            calculation_method=calc_method,
            provider=provider,
        )


# ---------------------------------------------------------------------------
# Failover wrapper
# ---------------------------------------------------------------------------


class SalahTimesAPI:
    """Failover-wrapping API client.

    Tries AlAdhan first. On failure (connection error, timeout, 429, 5xx)
    retries AlAdhan once, then falls through to islamic.app if failover is
    enabled.
    """

    def __init__(
        self,
        primary: AlAdhanClient,
        fallback: IslamicAppClient | None = None,
        enable_failover: bool = True,
    ) -> None:
        """Initialise the failover wrapper.

        Args:
            primary: The primary ``AlAdhanClient``.
            fallback: An optional ``IslamicAppClient`` for failover.
            enable_failover: Whether to attempt the fallback provider when
                the primary fails twice.
        """
        self._primary = primary
        self._fallback = fallback
        self._enable_failover = enable_failover

    def set_failover_enabled(self, enabled: bool) -> None:
        """Enable or disable provider failover at runtime."""
        self._enable_failover = enabled

    async def async_get_timings(self, **kwargs: Any) -> PrayerTimes:
        """Fetch daily prayer timings with failover.

        Tries the primary provider, retries once on connection/rate-limit
        errors, then falls through to the fallback provider if configured.

        Returns:
            A ``PrayerTimes`` instance with ``provider`` set to the
            succeeding provider's label.

        Raises:
            SalahTimesAPIError: If all providers fail.
        """
        # Remove any call-site flags that are not passed to the underlying clients
        kwargs.pop("enable_failover", None)

        last_error: Exception | None = None

        # Retry primary (AlAdhan) up to MAX_RETRIES times on retryable errors
        for attempt in range(MAX_RETRIES):
            try:
                result = await self._primary.async_get_timings(**kwargs)
                result.provider = PROVIDER_ALADHAN
                return result
            except _RETRYABLE_ERRORS as err:
                _LOGGER.warning(
                    "AlAdhan attempt %d failed: %s", attempt + 1, err
                )
                last_error = err
            except SalahTimesAPIError:
                # Non-retryable API error (e.g. client error other than 429)
                raise

        # Fallback
        if self._enable_failover and self._fallback is not None:
            _LOGGER.info("Falling back to islamic.app for timings")
            try:
                result = await self._fallback.async_get_timings(**kwargs)
                result.provider = PROVIDER_ISLAMIC_APP
                return result
            except _RETRYABLE_ERRORS as err:
                _LOGGER.error("Fallback (islamic.app) also failed: %s", err)
                last_error = err
            except SalahTimesAPIError as err:
                _LOGGER.error("Fallback (islamic.app) non-retryable error: %s", err)
                raise

        raise SalahTimesAPIError(
            "All providers failed to fetch prayer times"
        ) from last_error

    async def async_get_month_calendar(self, **kwargs: Any) -> dict[date, PrayerTimes]:
        """Fetch a full month calendar with failover.

        Same retry / fallback policy as :meth:`async_get_timings`.

        Returns:
            A ``dict`` keyed by Gregorian ``date`` with ``PrayerTimes``
            values.  Each value's ``provider`` reflects the succeeding API.

        Raises:
            SalahTimesAPIError: If all providers fail.
        """
        kwargs.pop("enable_failover", None)

        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                result = await self._primary.async_get_month_calendar(**kwargs)
                for pt in result.values():
                    pt.provider = PROVIDER_ALADHAN
                return result
            except _RETRYABLE_ERRORS as err:
                _LOGGER.warning(
                    "AlAdhan month calendar attempt %d failed: %s",
                    attempt + 1,
                    err,
                )
                last_error = err
            except SalahTimesAPIError:
                raise

        if self._enable_failover and self._fallback is not None:
            _LOGGER.info("Falling back to islamic.app for month calendar")
            try:
                result = await self._fallback.async_get_month_calendar(**kwargs)
                for pt in result.values():
                    pt.provider = PROVIDER_ISLAMIC_APP
                return result
            except _RETRYABLE_ERRORS as err:
                _LOGGER.error(
                    "Fallback (islamic.app) month calendar also failed: %s", err
                )
                last_error = err
            except SalahTimesAPIError as err:
                _LOGGER.error(
                    "Fallback (islamic.app) month calendar non-retryable error: %s",
                    err,
                )
                raise

        raise SalahTimesAPIError(
            "All providers failed to fetch month calendar"
        ) from last_error
