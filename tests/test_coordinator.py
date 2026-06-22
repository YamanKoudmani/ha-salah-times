"""Tests for the Salah Times coordinator."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from custom_components.salah_times.api import (
    SalahTimesAPI,
    SalahTimesAPIError,
    SalahTimesConnectionError,
    SalahTimesRateLimitError,
)
from custom_components.salah_times.coordinator import SalahTimesCoordinator
from custom_components.salah_times.models import PrayerName, PrayerTimes


class TestCoordinator:
    """Tests for SalahTimesCoordinator data fetching and failover."""

    async def test_aladhan_success(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_aladhan_client: AsyncMock,
    ) -> None:
        """Test that coordinator returns PrayerTimes when AlAdhan succeeds."""
        api = SalahTimesAPI(
            primary=mock_aladhan_client,
            fallback=None,
            enable_failover=False,
        )
        coordinator = SalahTimesCoordinator(
            hass, mock_config_entry, api, enable_midnight_refresh=False
        )
        result = await coordinator._async_update_data()

        assert isinstance(result, PrayerTimes)
        assert result.provider == "aladhan"

    async def test_failover_to_islamic_app(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_aladhan_client: AsyncMock,
        mock_islamic_app_client: AsyncMock,
    ) -> None:
        """Test that coordinator falls back to islamic.app on AlAdhan failure."""
        mock_aladhan_client.async_get_timings.side_effect = (
            SalahTimesConnectionError("AlAdhan connection failed")
        )

        api = SalahTimesAPI(
            primary=mock_aladhan_client,
            fallback=mock_islamic_app_client,
            enable_failover=True,
        )
        coordinator = SalahTimesCoordinator(
            hass, mock_config_entry, api, enable_midnight_refresh=False
        )
        result = await coordinator._async_update_data()

        assert isinstance(result, PrayerTimes)
        assert result.provider == "islamic_app"

    async def test_both_fail_update_failed(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_aladhan_client: AsyncMock,
        mock_islamic_app_client: AsyncMock,
    ) -> None:
        """Test that coordinator raises UpdateFailed when both providers fail."""
        mock_aladhan_client.async_get_timings.side_effect = (
            SalahTimesConnectionError("AlAdhan down")
        )
        mock_islamic_app_client.async_get_timings.side_effect = (
            SalahTimesConnectionError("Islamic.app down")
        )

        api = SalahTimesAPI(
            primary=mock_aladhan_client,
            fallback=mock_islamic_app_client,
            enable_failover=True,
        )
        coordinator = SalahTimesCoordinator(
            hass, mock_config_entry, api, enable_midnight_refresh=False
        )

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    async def test_rate_limit_handling(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_aladhan_client: AsyncMock,
        mock_islamic_app_client: AsyncMock,
    ) -> None:
        """Test that HTTP 429 triggers failover to islamic.app."""
        mock_aladhan_client.async_get_timings.side_effect = (
            SalahTimesRateLimitError("AlAdhan rate limited (429)")
        )

        api = SalahTimesAPI(
            primary=mock_aladhan_client,
            fallback=mock_islamic_app_client,
            enable_failover=True,
        )
        coordinator = SalahTimesCoordinator(
            hass, mock_config_entry, api, enable_midnight_refresh=False
        )
        result = await coordinator._async_update_data()

        assert result.provider == "islamic_app"

    async def test_month_rollover(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_aladhan_client: AsyncMock,
    ) -> None:
        """Test that month cache is refreshed on month rollover."""
        today = date.today()
        # Build a date from last month
        last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)

        api = SalahTimesAPI(
            primary=mock_aladhan_client,
            fallback=None,
            enable_failover=False,
        )
        coordinator = SalahTimesCoordinator(
            hass, mock_config_entry, api, enable_midnight_refresh=False
        )

        # Seed the cache with an entry from last month
        coordinator._month_cache = {
            last_month: PrayerTimes(date=last_month, timings={})
        }

        await coordinator._async_update_data()

        # After the update the month cache should have been refreshed and
        # now contain the current month (the mock returns today as the key).
        assert today in coordinator._month_cache

    async def test_aladhan_retry_succeeds(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_aladhan_client: AsyncMock,
    ) -> None:
        """Test that AlAdhan retry succeeds on the second attempt (no fallback)."""
        from datetime import datetime

        utc = dt_util.UTC
        today = date.today()
        prayer_times = PrayerTimes(
            date=today,
            timings={
                PrayerName(t): datetime(today.year, today.month, today.day, h, m, tzinfo=utc)
                for t, h, m in [
                    ("fajr", 5, 12), ("sunrise", 6, 45), ("dhuhr", 13, 10),
                    ("asr", 16, 50), ("maghrib", 19, 35), ("isha", 21, 0),
                    ("imsak", 5, 2), ("midnight", 0, 33),
                ]
            },
            provider="aladhan",
        )

        mock_aladhan_client.async_get_timings.side_effect = [
            SalahTimesConnectionError("first attempt fails"),
            prayer_times,
        ]

        api = SalahTimesAPI(
            primary=mock_aladhan_client,
            fallback=None,
            enable_failover=True,
        )
        coordinator = SalahTimesCoordinator(
            hass, mock_config_entry, api, enable_midnight_refresh=False
        )
        result = await coordinator._async_update_data()

        assert isinstance(result, PrayerTimes)
        assert result.provider == "aladhan"
        assert mock_aladhan_client.async_get_timings.call_count == 2

    async def test_non_retryable_error_no_fallback(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_aladhan_client: AsyncMock,
        mock_islamic_app_client: AsyncMock,
    ) -> None:
        """Test that non-retryable SalahTimesAPIError raises immediately without fallback."""
        mock_aladhan_client.async_get_timings.side_effect = (
            SalahTimesAPIError("non-retryable API error")
        )

        api = SalahTimesAPI(
            primary=mock_aladhan_client,
            fallback=mock_islamic_app_client,
            enable_failover=True,
        )
        coordinator = SalahTimesCoordinator(
            hass, mock_config_entry, api, enable_midnight_refresh=False
        )

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

        # Fallback must NOT have been called
        assert mock_islamic_app_client.async_get_timings.call_count == 0


class TestMidnightRefresh:
    """Tests for the daily midnight refresh listener.

    The listener is independent of ``update_interval`` and guarantees a
    coordinator refresh at 00:00:00 local time every night, so sensors
    never sit on yesterday's data when the regular poll would otherwise
    land hours after the day boundary.
    """

    async def test_midnight_listener_registered(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_aladhan_client: AsyncMock,
    ) -> None:
        """Coordinator registers a wall-clock listener on local 00:00:00."""
        with patch(
            "custom_components.salah_times.coordinator.async_track_time_change"
        ) as mock_track:
            mock_track.return_value = MagicMock()
            api = SalahTimesAPI(
                primary=mock_aladhan_client,
                fallback=None,
                enable_failover=False,
            )
            SalahTimesCoordinator(hass, mock_config_entry, api)

        # Listener must be registered for 00:00:00 local time
        mock_track.assert_called_once()
        args, kwargs = mock_track.call_args
        assert args[0] is hass
        assert kwargs.get("hour") == 0
        assert kwargs.get("minute") == 0
        assert kwargs.get("second") == 0

    async def test_midnight_listener_triggers_refresh(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_aladhan_client: AsyncMock,
    ) -> None:
        """Invoking the midnight callback requests a coordinator refresh."""
        api = SalahTimesAPI(
            primary=mock_aladhan_client,
            fallback=None,
            enable_failover=False,
        )
        # Default ``enable_midnight_refresh=True`` so the real listener is
        # registered — this test specifically exercises the callback path.
        coordinator = SalahTimesCoordinator(hass, mock_config_entry, api)

        # Replace async_request_refresh with an AsyncMock so we can
        # verify it was awaited when the midnight callback fires.
        coordinator.async_request_refresh = AsyncMock()

        await coordinator._handle_midnight_refresh(datetime.now())

        coordinator.async_request_refresh.assert_awaited_once()

        # Tear the listener down so the framework's lingering-timer
        # check stays happy.
        await coordinator.async_unload()

    async def test_midnight_listener_works_with_long_polling_interval(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_aladhan_client: AsyncMock,
    ) -> None:
        """Midnight refresh fires regardless of the configured polling interval.

        With a 24h polling interval, the regular poll could land far from
        midnight.  This guards against a regression where the midnight
        listener is silently disabled for long intervals.
        """
        # Simulate a user-configured 24h polling interval.  HA 2026.2
        # blocks direct mutation of ConfigEntry.options; use the
        # supported async_update_entry helper.
        hass.config_entries.async_update_entry(
            mock_config_entry,
            options={
                **mock_config_entry.options,
                "polling_interval_hours": 24,
            },
        )

        api = SalahTimesAPI(
            primary=mock_aladhan_client,
            fallback=None,
            enable_failover=False,
        )
        with patch(
            "custom_components.salah_times.coordinator.async_track_time_change"
        ) as mock_track:
            mock_track.return_value = MagicMock()
            coordinator = SalahTimesCoordinator(hass, mock_config_entry, api)

        # Listener must still be registered at 00:00:00
        mock_track.assert_called_once()
        _, kwargs = mock_track.call_args
        assert kwargs.get("hour") == 0
        assert kwargs.get("minute") == 0
        assert kwargs.get("second") == 0

        # And the callback still triggers a refresh
        coordinator.async_request_refresh = AsyncMock()
        await coordinator._handle_midnight_refresh(datetime.now())
        coordinator.async_request_refresh.assert_awaited_once()

    async def test_async_unload_cancels_midnight_listener(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_aladhan_client: AsyncMock,
    ) -> None:
        """``async_unload`` cancels the registered listener exactly once."""
        cancel = MagicMock()
        with patch(
            "custom_components.salah_times.coordinator.async_track_time_change"
        ) as mock_track:
            mock_track.return_value = cancel
            api = SalahTimesAPI(
                primary=mock_aladhan_client,
                fallback=None,
                enable_failover=False,
            )
            coordinator = SalahTimesCoordinator(hass, mock_config_entry, api)

        # Listener is held until unload
        assert coordinator._cancel_midnight_refresh is cancel

        await coordinator.async_unload()

        cancel.assert_called_once()
        assert coordinator._cancel_midnight_refresh is None

        # Second call must be a no-op
        await coordinator.async_unload()
        cancel.assert_called_once()
