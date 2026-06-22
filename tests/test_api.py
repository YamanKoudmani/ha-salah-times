"""Tests for the Salah Times API clients and helpers."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock
from zoneinfo import ZoneInfo

import pytest
from homeassistant.util import dt as dt_util

from custom_components.salah_times.api import (
    IslamicAppClient,
    _parse_timing_to_utc,
)
from custom_components.salah_times.const import PROVIDER_ISLAMIC_APP
from custom_components.salah_times.models import PrayerName


class TestParseTimingToUtc:
    """Tests for _parse_timing_to_utc conversion."""

    def test_parse_timing_basic(self) -> None:
        """Parse '05:12' with UTC timezone.

        Note: the implementation uses ``as_utc`` which produces
        ``datetime.timezone.utc`` rather than ``ZoneInfo("UTC")``.
        """
        result = _parse_timing_to_utc(
            "05:12", date(2026, 6, 21), tz_info=ZoneInfo("UTC")
        )
        expected = datetime(2026, 6, 21, 5, 12, tzinfo=timezone.utc)
        assert result == expected
        # The tzinfo object is timezone.utc (not ZoneInfo), but we verify by
        # comparing the UTC offset rather than identity.
        assert result.tzinfo is not None
        assert result.utcoffset().total_seconds() == 0

    def test_parse_timing_with_timezone(self) -> None:
        """Parse '05:12' with America/New_York in DST (EDT = UTC-4).

        5:12 AM EDT on June 21 should be 9:12 AM UTC.
        """
        result = _parse_timing_to_utc(
            "05:12", date(2026, 6, 21), tz_info=ZoneInfo("America/New_York")
        )
        expected = datetime(2026, 6, 21, 9, 12, tzinfo=timezone.utc)
        assert result == expected
        # Verify DST is in effect for this date: June 21 uses EDT = UTC-4
        ny_tz = ZoneInfo("America/New_York")
        local_dt = datetime(2026, 6, 21, 5, 12, tzinfo=ny_tz)
        assert local_dt.utcoffset().total_seconds() == -4 * 3600  # EDT

    def test_parse_timing_midnight(self) -> None:
        """Parse '00:00' — should be start of day in UTC."""
        result = _parse_timing_to_utc(
            "00:00", date(2026, 6, 21), tz_info=ZoneInfo("UTC")
        )
        expected = datetime(2026, 6, 21, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_parse_timing_none_tz_fallback(self) -> None:
        """Parse with tz_info=None should not crash (falls back to HA default)."""
        result = _parse_timing_to_utc("05:12", date(2026, 6, 21), tz_info=None)
        assert isinstance(result, datetime)
        assert result.tzinfo is not None
        # Should be timezone-aware and in UTC
        assert result.utcoffset() is not None
        assert result.utcoffset().total_seconds() == 0
        # Verify the local time in HA's configured timezone corresponds to 05:12
        ha_tz = dt_util.get_default_time_zone()
        local = result.astimezone(ha_tz)
        assert local.hour == 5
        assert local.minute == 12


class TestIslamicAppParseTimings:
    """Integration-style test for IslamicAppClient._parse_timings_response."""

    async def test_islamic_app_parse_timings(self) -> None:
        """Exercise the real _parse_timings_response against the fixture.

        Creates an IslamicAppClient with a mock aiohttp session,
        calls async_get_timings, and verifies the returned PrayerTimes.
        """
        fixture_path = Path(__file__).parent / "fixtures" / "islamic_app_timings.json"
        fixture_data = json.loads(fixture_path.read_text("utf-8"))

        # Build a mock HTTP response chain.
        # NOTE: mock_session must NOT be an AsyncMock because that would make
        # every method call return a coroutine, but `_request` uses
        # `async with self._session.request(...)` which expects the method
        # call to return an async context manager directly, not a coroutine.
        mock_resp = Mock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=fixture_data)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_resp

        mock_session = MagicMock()
        mock_session.request.return_value = mock_ctx

        client = IslamicAppClient(mock_session)

        result = await client.async_get_timings(
            latitude=40.7128,
            longitude=-74.0060,
            date=date(2026, 6, 21),
            method=2,
            school=0,
            latitude_adjustment_method=3,
            hijri_adjustment_days=0,
        )

        # Provider
        assert result.provider == PROVIDER_ISLAMIC_APP

        # All 8 timings should be present and not None
        for prayer in PrayerName:
            assert prayer in result.timings, f"Missing timing for {prayer}"
            assert result.timings[prayer] is not None

        # hijri_month tests the month_name vs month.en field path difference
        assert isinstance(result.hijri_month, str)
        assert len(result.hijri_month) > 0
        assert result.hijri_month == "Muharram"

        # calculation_method tests the method_name vs method.name difference
        assert isinstance(result.calculation_method, str)
        assert len(result.calculation_method) > 0
        assert "ISNA" in result.calculation_method

        # Verify timings are timezone-aware and in UTC
        for prayer_time in result.timings.values():
            assert prayer_time.tzinfo is not None
            assert prayer_time.utcoffset() is not None

        # Verify the mock session was actually called
        mock_session.request.assert_called_once()
