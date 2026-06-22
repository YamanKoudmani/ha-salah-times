"""Shared pytest fixtures for the Salah Times integration tests."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Windows compat: prevent pytest-socket from blocking asyncio's event loop
#
# pytest-homeassistant-custom-component calls pytest_socket.disable_socket(
# allow_unix_socket=True) before every test.  On Linux, allow_unix_socket=True
# is sufficient because asyncio uses AF_UNIX socket pairs.  On Windows, the
# ProactorEventLoop uses AF_INET socket pairs, which are blocked.  We patch
# disable_socket to a no-op so the event loop can initialise on Windows.
# Real network calls are still prevented by the test mocks (no real HTTP).
# ---------------------------------------------------------------------------
import sys

if sys.platform == "win32":
    import pytest_socket

    pytest_socket.disable_socket = lambda *a, **kw: None
    pytest_socket.socket_allow_hosts = lambda *a, **kw: None

from datetime import date, datetime
from pathlib import Path
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.salah_times.api import (
    AlAdhanClient,
    IslamicAppClient,
    SalahTimesAPI,
)
from custom_components.salah_times.const import (
    CONF_CALCULATION_METHOD,
    CONF_ENABLE_FAILOVER,
    CONF_HIJRI_ADJUSTMENT_DAYS,
    CONF_LATITUDE,
    CONF_LATITUDE_ADJUSTMENT_METHOD,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_POLLING_INTERVAL_HOURS,
    CONF_SCHOOL,
    DEFAULT_CALCULATION_METHOD,
    DEFAULT_ENABLE_FAILOVER,
    DEFAULT_HIJRI_ADJUSTMENT_DAYS,
    DEFAULT_LATITUDE_ADJUSTMENT_METHOD,
    DEFAULT_NAME,
    DEFAULT_POLLING_INTERVAL_HOURS,
    DEFAULT_SCHOOL,
    DOMAIN,
)
from custom_components.salah_times.coordinator import SalahTimesCoordinator
from custom_components.salah_times.models import PrayerName, PrayerTimes

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_fixture(name: str) -> str:
    """Load a test fixture file from the fixtures directory."""
    return (Path(__file__).parent / "fixtures" / name).read_text("utf-8")


def _create_prayer_times(
    provider: str = "aladhan",
    target_date: date | None = None,
) -> PrayerTimes:
    """Build a PrayerTimes instance with known values matching aladhan_timings.json."""
    if target_date is None:
        target_date = date(2026, 6, 21)
    utc = dt_util.UTC
    return PrayerTimes(
        date=target_date,
        timings={
            PrayerName.FAJR: datetime(2026, 6, 21, 5, 12, tzinfo=utc),
            PrayerName.SUNRISE: datetime(2026, 6, 21, 6, 45, tzinfo=utc),
            PrayerName.DHUHR: datetime(2026, 6, 21, 13, 10, tzinfo=utc),
            PrayerName.ASR: datetime(2026, 6, 21, 16, 50, tzinfo=utc),
            PrayerName.MAGHRIB: datetime(2026, 6, 21, 19, 35, tzinfo=utc),
            PrayerName.ISHA: datetime(2026, 6, 21, 21, 0, tzinfo=utc),
            PrayerName.IMSAK: datetime(2026, 6, 21, 5, 2, tzinfo=utc),
            PrayerName.MIDNIGHT: datetime(2026, 6, 21, 0, 33, tzinfo=utc),
        },
        hijri_date="05-01-1448",
        hijri_month="Muharram",
        hijri_year=1448,
        hijri_holidays=["Islamic New Year"],
        calculation_method="Islamic Society of North America (ISNA)",
        provider=provider,
    )


# ---------------------------------------------------------------------------
# Autouse fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Automatically enable loading of custom integrations for all tests.

    This wraps the ``enable_custom_integrations`` fixture provided by
    ``pytest-homeassistant-custom-component`` so that every test can
    import from ``custom_components.salah_times`` without additional
    per-file markers.
    """
    return


# ---------------------------------------------------------------------------
# General fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry for Salah Times."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="40.7128--74.0060",
        data={
            CONF_NAME: "Test Location",
            CONF_LATITUDE: 40.7128,
            CONF_LONGITUDE: -74.0060,
        },
        options={
            CONF_CALCULATION_METHOD: DEFAULT_CALCULATION_METHOD,
            CONF_SCHOOL: DEFAULT_SCHOOL,
            CONF_LATITUDE_ADJUSTMENT_METHOD: DEFAULT_LATITUDE_ADJUSTMENT_METHOD,
            CONF_HIJRI_ADJUSTMENT_DAYS: DEFAULT_HIJRI_ADJUSTMENT_DAYS,
            CONF_POLLING_INTERVAL_HOURS: DEFAULT_POLLING_INTERVAL_HOURS,
            CONF_ENABLE_FAILOVER: DEFAULT_ENABLE_FAILOVER,
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def sample_aladhan_response() -> dict[str, Any]:
    """Return a sample AlAdhan /timings response dict."""
    import json

    return json.loads(load_fixture("aladhan_timings.json"))


@pytest.fixture
def sample_islamic_app_response() -> dict[str, Any]:
    """Return a sample islamic.app /timings response dict."""
    import json

    return json.loads(load_fixture("islamic_app_timings.json"))


# ---------------------------------------------------------------------------
# Mock API client fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config_entry_2(hass: HomeAssistant) -> MockConfigEntry:
    """Create a second mock config entry (different coordinates)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="34.0522--118.2437",
        data={
            CONF_NAME: "LA Office",
            CONF_LATITUDE: 34.0522,
            CONF_LONGITUDE: -118.2437,
        },
        options={
            CONF_CALCULATION_METHOD: DEFAULT_CALCULATION_METHOD,
            CONF_SCHOOL: DEFAULT_SCHOOL,
            CONF_LATITUDE_ADJUSTMENT_METHOD: DEFAULT_LATITUDE_ADJUSTMENT_METHOD,
            CONF_HIJRI_ADJUSTMENT_DAYS: DEFAULT_HIJRI_ADJUSTMENT_DAYS,
            CONF_POLLING_INTERVAL_HOURS: DEFAULT_POLLING_INTERVAL_HOURS,
            CONF_ENABLE_FAILOVER: DEFAULT_ENABLE_FAILOVER,
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_aladhan_client() -> AsyncMock:
    """Return a mock AlAdhanClient that returns sample data."""
    client = AsyncMock(spec=AlAdhanClient)
    prayer_times = _create_prayer_times("aladhan")
    client.async_get_timings.return_value = prayer_times
    client.async_get_month_calendar.return_value = {date.today(): prayer_times}
    return client


@pytest.fixture
def mock_islamic_app_client() -> AsyncMock:
    """Return a mock IslamicAppClient that returns sample data."""
    client = AsyncMock(spec=IslamicAppClient)
    prayer_times = _create_prayer_times("islamic_app")
    client.async_get_timings.return_value = prayer_times
    client.async_get_month_calendar.return_value = {date.today(): prayer_times}
    return client


# ---------------------------------------------------------------------------
# Mock coordinator fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def mock_coordinator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aladhan_client: AsyncMock,
    mock_islamic_app_client: AsyncMock,
) -> SalahTimesCoordinator:
    """Return a coordinator pre-loaded with sample data.

    The coordinator is wired with mocked API clients so no network calls
    are made.  Both ``coordinator.data`` and ``last_update_success`` are
    set manually for unit-test convenience.

    The midnight refresh listener is disabled here (``enable_midnight_refresh=False``)
    because this fixture backs tests that don't exercise the listener and
    pytest-homeassistant-custom-component's lingering-timer check would
    otherwise flag the test.  Tests that specifically cover the listener
    instantiate ``SalahTimesCoordinator`` directly with the default
    ``enable_midnight_refresh=True`` and call :meth:`async_unload` to
    clean up.
    """
    api = SalahTimesAPI(
        primary=mock_aladhan_client,
        fallback=mock_islamic_app_client,
        enable_failover=True,
    )
    coordinator = SalahTimesCoordinator(
        hass,
        mock_config_entry,
        api,
        enable_midnight_refresh=False,
    )
    coordinator.data = _create_prayer_times("aladhan")
    coordinator.last_update_success = True
    coordinator._month_cache = {
        date.today(): _create_prayer_times("aladhan"),
    }
    return coordinator


# ---------------------------------------------------------------------------
# Autouse cleanup: unload any still-LOADED config entries after each test
# ---------------------------------------------------------------------------
# Some tests (notably config-flow tests) drive HA through to a fully
# ``LOADED`` entry without explicitly unloading it.  The coordinator's
# midnight-refresh listener is wired to ``entry.async_on_unload`` in
# ``__init__.py``, so unloading the entry releases the listener — which
# is what ``pytest-homeassistant-custom-component``'s lingering-timer
# check requires.  This autouse fixture catches every test that forgets
# to unload, so we don't get a CI failure every time a new test is added
# that creates an entry via the config flow.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _auto_unload_loaded_entries(
    hass: HomeAssistant,
) -> AsyncGenerator[None, None]:
    """Unload any still-LOADED config entries after each test runs.

    Belt-and-suspenders: we both unload the entry (which fires
    ``entry.async_on_unload`` callbacks and should cancel the midnight
    listener) **and** call ``coordinator.async_unload()`` directly via
    ``entry.runtime_data``.  The direct call is needed because some
    test paths in newer ``pytest-homeassistant-custom-component``
    versions set up the entry through a code path that doesn't always
    trigger the ``async_on_unload`` callbacks the integration
    registered, leaving the wall-clock timer registered in the event
    loop and tripping the framework's lingering-timer check.

    ``coordinator.async_unload`` is idempotent, so calling it after a
    successful entry unload is a harmless no-op.

    A final ``async_block_till_done`` flushes any short-lived timers
    scheduled by helpers like ``DataUpdateCoordinator``'s debouncer
    (used in tests that call ``async_request_refresh`` directly, e.g.
    the debug-refresh button tests) before the framework's lingering
    timer check runs.

    As a last resort, scan the event loop for any
    ``_TrackPointUTCTime`` handles whose job targets
    ``SalahTimesCoordinator._handle_midnight_refresh`` and cancel
    them.  This catches timers whose owner we can't otherwise reach
    (e.g. the config-flow auto-setup path in newer plugin versions
    where ``entry.runtime_data`` isn't populated yet when this
    fixture runs).
    """
    yield
    for entry in hass.config_entries.async_entries(DOMAIN):
        # Direct cleanup first: the coordinator's runtime_data holds the
        # midnight-refresh cancel callback.  Cancelling it here is the
        # most reliable way to release the lingering _TrackPointUTCTime
        # timer regardless of how the entry was set up.
        coordinator = getattr(entry, "runtime_data", None)
        if coordinator is not None and hasattr(coordinator, "async_unload"):
            await coordinator.async_unload()

        # Then unload the entry itself so the framework releases any
        # other resources tied to it (forwarded platforms, runtime data,
        # etc.).
        if entry.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()

    # Flush any short-lived timers (e.g. DataUpdateCoordinator's
    # internal debouncer used by async_request_refresh) so they don't
    # trip the framework's lingering-timer check on tests that don't
    # go through the entry lifecycle.
    await hass.async_block_till_done()

    # Last-resort sweep: cancel any _TrackPointUTCTime handles still
    # scheduled in the event loop that belong to
    # SalahTimesCoordinator._handle_midnight_refresh.  This handles
    # the config-flow tests where the auto-setup path in newer
    # pytest-homeassistant-custom-component doesn't expose the
    # coordinator to us via entry.runtime_data.
    try:
        loop = hass.loop
        # asyncio handles aren't easily iterable; iterate the
        # scheduled list via the private _scheduled attribute if
        # available, otherwise fall back to cancelling the whole
        # default executor.  We try the safe path first.
        handles = getattr(loop, "_scheduled", None) or []
        for handle in list(handles):
            callback = getattr(handle, "_callback", None) or getattr(
                handle, "callback", None
            )
            if callback is None:
                continue
            # The handle's callback may be wrapped; unwrap one level
            # to look at the underlying call.
            inner = getattr(callback, "__self__", None) or getattr(
                callback, "func", None
            )
            method_name = getattr(callback, "__name__", "") or ""
            if (
                method_name == "_handle_midnight_refresh"
                or (inner is not None and getattr(inner, "__name__", "") == "_handle_midnight_refresh")
            ):
                handle.cancel()
    except Exception:  # noqa: BLE001 - best-effort cleanup, never fail the test
        pass
