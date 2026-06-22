"""Tests for the Salah Times sensors."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.salah_times.models import (
    PrayerName,
    PrayerTimes,
)
from custom_components.salah_times.sensor import (
    PRAYER_SENSORS,
    SalahTimesNextPrayerSensor,
    SalahTimesPrayerSensor,
    async_setup_entry,
)


class TestPrayerSensors:
    """Tests for individual prayer timestamp sensors."""

    @pytest.mark.parametrize(
        "prayer",
        [
            PrayerName.FAJR,
            PrayerName.SUNRISE,
            PrayerName.DHUHR,
            PrayerName.ASR,
            PrayerName.MAGHRIB,
            PrayerName.ISHA,
            PrayerName.IMSAK,
            PrayerName.MIDNIGHT,
        ],
    )
    async def test_prayer_sensor_native_value(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
        prayer: PrayerName,
    ) -> None:
        """Test that each prayer sensor returns the correct UTC timestamp.

        Parametrized over all 8 prayer names.
        """
        description = next(
            d for d in PRAYER_SENSORS if d.key == prayer.value
        )
        sensor = SalahTimesPrayerSensor(
            coordinator=mock_coordinator,
            entry_id=mock_config_entry.entry_id,
            name=mock_config_entry.title,
            description=description,
            prayer=prayer,
        )
        expected = mock_coordinator.data.timings[prayer]
        assert sensor.native_value == expected


class TestNextPrayerSensor:
    """Tests for the next prayer countdown sensor."""

    async def test_next_prayer_computation(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
    ) -> None:
        """Test that the next prayer sensor returns the correct upcoming prayer."""
        now = dt_util.utcnow()
        fajr_time = now - timedelta(hours=3)
        dhuhr_time = now + timedelta(hours=2)

        mock_coordinator.data = PrayerTimes(
            date=now.date(),
            timings={
                PrayerName.FAJR: fajr_time,
                PrayerName.DHUHR: dhuhr_time,
                PrayerName.ASR: now + timedelta(hours=6),
                PrayerName.MAGHRIB: now + timedelta(hours=9),
                PrayerName.ISHA: now + timedelta(hours=11),
            },
            hijri_date="05-01-1448",
            hijri_month="Muharram",
            hijri_year=1448,
            hijri_holidays=[],
            calculation_method="ISNA",
            provider="aladhan",
        )

        sensor = SalahTimesNextPrayerSensor(
            coordinator=mock_coordinator,
            entry_id=mock_config_entry.entry_id,
            name=mock_config_entry.title,
        )
        assert sensor.native_value == dhuhr_time
        assert sensor.extra_state_attributes["prayer"] == "dhuhr"

    async def test_provider_attribute_reflects_failover(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
    ) -> None:
        """Test that the provider attribute shows the correct source."""
        # Override the coordinator data to simulate failover provider
        now = dt_util.utcnow()
        mock_coordinator.data = PrayerTimes(
            date=now.date(),
            timings={
                PrayerName.FAJR: now + timedelta(hours=1),
                PrayerName.DHUHR: now + timedelta(hours=4),
                PrayerName.ASR: now + timedelta(hours=7),
                PrayerName.MAGHRIB: now + timedelta(hours=10),
                PrayerName.ISHA: now + timedelta(hours=13),
            },
            hijri_date="05-01-1448",
            hijri_month="Muharram",
            hijri_year=1448,
            hijri_holidays=["Islamic New Year"],
            calculation_method="ISNA",
            provider="islamic_app",
        )

        sensor = SalahTimesNextPrayerSensor(
            coordinator=mock_coordinator,
            entry_id=mock_config_entry.entry_id,
            name=mock_config_entry.title,
        )
        assert sensor.extra_state_attributes["provider"] == "islamic_app"

    async def test_entity_registry(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
    ) -> None:
        """Test that async_setup_entry creates 9 entities with correct unique_ids."""
        mock_config_entry.runtime_data = mock_coordinator

        async_add_entities = AsyncMock()
        await async_setup_entry(hass, mock_config_entry, async_add_entities)

        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 9

        # Verify each prayer sensor has the correct unique_id
        for description in PRAYER_SENSORS:
            prayer = PrayerName(description.key)
            expected_uid = f"{mock_config_entry.entry_id}-{prayer.value}"
            assert any(
                e.unique_id == expected_uid for e in entities
            ), f"Missing entity with unique_id {expected_uid}"

        # Verify the next-prayer sensor
        expected_uid = f"{mock_config_entry.entry_id}-next_prayer"
        assert any(
            e.unique_id == expected_uid for e in entities
        ), f"Missing entity with unique_id {expected_uid}"

    async def test_next_prayer_all_passed(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
    ) -> None:
        """Test that next-prayer sensor returns None when all prayers have passed."""
        now = dt_util.utcnow()
        yesterday = now - timedelta(days=1)

        # All 5 obligatory prayers are set to yesterday (all in the past)
        mock_coordinator.data = PrayerTimes(
            date=now.date(),
            timings={
                PrayerName.FAJR: yesterday,
                PrayerName.DHUHR: yesterday,
                PrayerName.ASR: yesterday,
                PrayerName.MAGHRIB: yesterday,
                PrayerName.ISHA: yesterday,
            },
            hijri_date="05-01-1448",
            hijri_month="Muharram",
            hijri_year=1448,
            hijri_holidays=[],
            calculation_method="ISNA",
            provider="aladhan",
        )

        sensor = SalahTimesNextPrayerSensor(
            coordinator=mock_coordinator,
            entry_id=mock_config_entry.entry_id,
            name=mock_config_entry.title,
        )

        assert sensor.native_value is None
        assert sensor.extra_state_attributes.get("prayer") is None
        assert sensor.extra_state_attributes.get("time_remaining") is None
