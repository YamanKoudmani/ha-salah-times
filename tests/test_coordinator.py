"""Tests for the Salah Times coordinator."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock

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
        coordinator = SalahTimesCoordinator(hass, mock_config_entry, api)
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
        coordinator = SalahTimesCoordinator(hass, mock_config_entry, api)
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
        coordinator = SalahTimesCoordinator(hass, mock_config_entry, api)

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
        coordinator = SalahTimesCoordinator(hass, mock_config_entry, api)
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
        coordinator = SalahTimesCoordinator(hass, mock_config_entry, api)

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
        coordinator = SalahTimesCoordinator(hass, mock_config_entry, api)
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
        coordinator = SalahTimesCoordinator(hass, mock_config_entry, api)

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

        # Fallback must NOT have been called
        assert mock_islamic_app_client.async_get_timings.call_count == 0
