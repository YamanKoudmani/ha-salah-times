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

    The integration's only async resource that survives a test is the
    midnight-refresh wall-clock listener on the coordinator.  Cancelling
    that listener is enough to keep the framework's lingering-timer
    check happy, and avoids the executor-shutdown side effects that
    calling ``hass.config_entries.async_unload`` can trigger (a
    ``_run_safe_shutdown_loop`` daemon thread is flagged as a leak
    by the framework's thread check).

    We walk ``SalahTimesCoordinator._all_instances`` and call
    ``async_unload`` on every coordinator created during the test.
    This is the most reliable way to reach the midnight-refresh
    listener on coordinators the test never bound to a config entry
    (e.g. those auto-created by the config-flow framework in newer
    ``pytest-homeassistant-custom-component``, where
    ``entry.runtime_data`` isn't populated yet at cleanup time).
    """
    yield

    # Drain any pending tasks first so the executor is idle when the
    # test framework's verify_cleanup shuts it down (avoids the
    # _run_safe_shutdown_loop daemon thread being flagged as lingering).
    await hass.async_block_till_done()

    # Walk the class-level registry and cancel every coordinator's
    # midnight-refresh listener.  This is sufficient to satisfy the
    # lingering-timer check without triggering the entry-unload path
    # that spawns the _run_safe_shutdown_loop thread.
    instances = list(SalahTimesCoordinator._all_instances)
    for coordinator in instances:
        await coordinator.async_unload()
    # Drop them so the next test starts with a clean registry.
    SalahTimesCoordinator._all_instances.clear()

    # Flush any remaining short-lived timers (e.g. DataUpdateCoordinator's
    # internal debouncer) so they don't trip the framework's
    # lingering-timer check.
    await hass.async_block_till_done()

    # Pre-shutdown the default executor so the test framework's
    # verify_cleanup shutdown is effectively a no-op.  Without this,
    # ``shutdown_default_executor`` spawns a ``_run_safe_shutdown_loop``
    # daemon thread that the framework's thread-leak check flags as
    # lingering.
    try:
        await hass.loop.shutdown_default_executor()
    except Exception:  # noqa: BLE001 - best-effort, never fail the test
        pass

    # Give the shutdown thread a moment to exit before the test
    # framework's thread-leak check runs.
    import asyncio
    await asyncio.sleep(0)
