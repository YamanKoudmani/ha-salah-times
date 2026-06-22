"""Tests for the Salah Times data models."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from homeassistant.util import dt as dt_util

from custom_components.salah_times.models import PrayerName, PrayerTimes


class TestPrayerTimesEq:
    """Tests for PrayerTimes.__eq__ equality comparison."""

    def _make_pt(
        self,
        provider: str = "aladhan",
        day: int = 21,
    ) -> PrayerTimes:
        """Helper to build a PrayerTimes with deterministic values."""
        utc = dt_util.UTC
        return PrayerTimes(
            date=date(2026, 6, day),
            timings={
                PrayerName.FAJR: datetime(2026, 6, day, 5, 12, tzinfo=utc),
                PrayerName.DHUHR: datetime(2026, 6, day, 13, 10, tzinfo=utc),
                PrayerName.ASR: datetime(2026, 6, day, 16, 50, tzinfo=utc),
                PrayerName.MAGHRIB: datetime(2026, 6, day, 19, 35, tzinfo=utc),
                PrayerName.ISHA: datetime(2026, 6, day, 21, 0, tzinfo=utc),
                PrayerName.IMSAK: datetime(2026, 6, day, 5, 2, tzinfo=utc),
                PrayerName.MIDNIGHT: datetime(2026, 6, day, 0, 33, tzinfo=utc),
            },
            hijri_date="05-01-1448",
            hijri_month="Muharram",
            hijri_year=1448,
            hijri_holidays=["Islamic New Year"],
            calculation_method="Islamic Society of North America (ISNA)",
            provider=provider,
        )

    def test_eq_identical(self) -> None:
        """Two identical PrayerTimes instances should be equal."""
        a = self._make_pt()
        b = self._make_pt()
        assert a == b
        assert not (a != b)

    def test_eq_same_data_different_provider(self) -> None:
        """Same data but different provider should NOT be equal."""
        a = self._make_pt(provider="aladhan")
        b = self._make_pt(provider="islamic_app")
        assert a != b
        assert not (a == b)

    def test_eq_different_data_same_provider(self) -> None:
        """Different timings but same provider should NOT be equal."""
        a = self._make_pt(provider="aladhan", day=21)
        b = self._make_pt(provider="aladhan", day=22)
        assert a != b
        assert not (a == b)

    def test_eq_different_type(self) -> None:
        """PrayerTimes compared to a non-PrayerTimes should return False."""
        pt = self._make_pt()
        assert (pt == "some string") is False
        assert (pt == 42) is False
        assert (pt == None) is False  # noqa: E711
