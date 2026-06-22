"""Tests for the Salah Times calendar entity."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.salah_times.models import PrayerName, PrayerTimes
from custom_components.salah_times.calendar import SalahCalendarEntity


class TestCalendarEntity:
    """Tests for SalahCalendarEntity."""

    async def test_get_events(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
    ) -> None:
        """Test that async_get_events returns the correct CalendarEvents.

        Populate the month cache with 3 days of prayer times, query
        the range, and verify 5 events per day (one per obligatory prayer).
        """
        utc = dt_util.UTC
        today = date(2026, 6, 21)

        # Build 3 days of prayer times
        month_cache = {}
        for offset in range(3):
            day = date(2026, 6, 21 + offset)
            month_cache[day] = PrayerTimes(
                date=day,
                timings={
                    PrayerName.FAJR: datetime(day.year, day.month, day.day, 5, 12, tzinfo=utc),
                    PrayerName.DHUHR: datetime(day.year, day.month, day.day, 13, 10, tzinfo=utc),
                    PrayerName.ASR: datetime(day.year, day.month, day.day, 16, 50, tzinfo=utc),
                    PrayerName.MAGHRIB: datetime(day.year, day.month, day.day, 19, 35, tzinfo=utc),
                    PrayerName.ISHA: datetime(day.year, day.month, day.day, 21, 0, tzinfo=utc),
                },
            )

        mock_coordinator._month_cache = month_cache

        entity = SalahCalendarEntity(
            coordinator=mock_coordinator,
            entry_id=mock_config_entry.entry_id,
            name=mock_config_entry.title,
        )

        start = datetime(2026, 6, 21, 0, 0, tzinfo=utc)
        end = datetime(2026, 6, 23, 23, 59, tzinfo=utc)
        events = await entity.async_get_events(hass, start, end)

        # 3 days × 5 obligatory prayers = 15 events
        assert len(events) == 15

        # Verify each day has the right number of events
        events_by_date: dict[date, list] = {}
        for ev in events:
            ev_date = ev.start.date()
            events_by_date.setdefault(ev_date, []).append(ev)

        assert len(events_by_date) == 3
        for day_events in events_by_date.values():
            assert len(day_events) == 5

        # Verify the first event on day 1 is Fajr
        day1_events = sorted(events_by_date[today], key=lambda e: e.start)
        assert day1_events[0].summary == "Fajr"
        assert day1_events[0].end - day1_events[0].start == timedelta(minutes=10)

    async def test_current_event(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
    ) -> None:
        """Test that the event property returns the currently ongoing prayer."""
        now = dt_util.utcnow()
        prayer_time = now - timedelta(minutes=1)  # started 1 min ago
        # Window: [prayer_time, prayer_time + 10 min) = [now-1min, now+9min)
        # now is within this window.

        mock_coordinator.data = PrayerTimes(
            date=now.date(),
            timings={
                PrayerName.FAJR: prayer_time,
                PrayerName.DHUHR: now + timedelta(hours=4),
                PrayerName.ASR: now + timedelta(hours=7),
                PrayerName.MAGHRIB: now + timedelta(hours=10),
                PrayerName.ISHA: now + timedelta(hours=13),
            },
            hijri_date="05-01-1448",
            hijri_month="Muharram",
            hijri_year=1448,
            hijri_holidays=[],
            calculation_method="ISNA",
            provider="aladhan",
        )

        entity = SalahCalendarEntity(
            coordinator=mock_coordinator,
            entry_id=mock_config_entry.entry_id,
            name=mock_config_entry.title,
        )

        event = entity.event
        assert event is not None
        assert event.summary == "Fajr"
        assert event.start == prayer_time
        assert event.end == prayer_time + timedelta(minutes=10)

    async def test_no_current_event(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
    ) -> None:
        """Test that no event is returned when no prayer is currently active."""
        now = dt_util.utcnow()

        # All obligatory prayers are either well in the past (>10 min ago)
        # or well in the future, so no event should be "ongoing".
        mock_coordinator.data = PrayerTimes(
            date=now.date(),
            timings={
                PrayerName.FAJR: now - timedelta(hours=4),    # ended ~3h50m ago
                PrayerName.DHUHR: now - timedelta(hours=2),   # ended ~1h50m ago
                PrayerName.ASR: now - timedelta(minutes=30),  # ended ~20m ago
                PrayerName.MAGHRIB: now + timedelta(hours=2), # starts in 2h
                PrayerName.ISHA: now + timedelta(hours=4),    # starts in 4h
            },
            hijri_date="05-01-1448",
            hijri_month="Muharram",
            hijri_year=1448,
            hijri_holidays=[],
            calculation_method="ISNA",
            provider="aladhan",
        )

        entity = SalahCalendarEntity(
            coordinator=mock_coordinator,
            entry_id=mock_config_entry.entry_id,
            name=mock_config_entry.title,
        )

        assert entity.event is None

    async def test_get_events_empty_cache(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
    ) -> None:
        """Test that async_get_events returns an empty list when month cache is empty."""
        utc = dt_util.UTC

        # Empty the cache
        mock_coordinator._month_cache = {}

        entity = SalahCalendarEntity(
            coordinator=mock_coordinator,
            entry_id=mock_config_entry.entry_id,
            name=mock_config_entry.title,
        )

        start = datetime(2026, 6, 21, 0, 0, tzinfo=utc)
        end = datetime(2026, 6, 23, 23, 59, tzinfo=utc)
        events = await entity.async_get_events(hass, start, end)

        assert events == []
