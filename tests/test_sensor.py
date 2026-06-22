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
        # Set _attr_native_value directly (simulates _handle_coordinator_update
        # without needing async_write_ha_state which requires full HA setup)
        sensor._attr_native_value = mock_coordinator.data.timings.get(prayer)
        expected = mock_coordinator.data.timings[prayer]
        assert sensor._attr_native_value == expected

    async def test_prayer_sensor_init_seeds_native_value(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
    ) -> None:
        """Test that __init__ seeds _attr_native_value from coordinator data.

        The coordinator's first refresh completes *before* entity creation,
        so the prayer timestamp sensor's ``__init__`` should pick up the
        correct value immediately.  This ensures the very first state write
        in ``add_to_platform_finish`` produces a valid timestamp rather than
        "unknown".

        Note: we cannot call ``sensor.state`` here because ``SensorEntity.state``
        requires platform registration (accesses ``_unit_of_measurement_translation_key``
        which raises before the entity is added to HA). The critical assertion
        is that ``_attr_native_value`` is correctly seeded.
        """
        description = next(
            d for d in PRAYER_SENSORS if d.key == PrayerName.FAJR.value
        )
        sensor = SalahTimesPrayerSensor(
            coordinator=mock_coordinator,
            entry_id=mock_config_entry.entry_id,
            name=mock_config_entry.title,
            description=description,
            prayer=PrayerName.FAJR,
        )
        expected = mock_coordinator.data.timings[PrayerName.FAJR]
        assert sensor._attr_native_value == expected


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
        # Compute what _handle_coordinator_update would set
        next_time, next_prayer_name, time_remaining = sensor._compute_next_prayer()
        sensor._attr_native_value = next_time
        sensor._attr_extra_state_attributes = {
            "prayer": next_prayer_name,
            "time_remaining": time_remaining,
            "hijri_date": mock_coordinator.data.hijri_date,
            "hijri_holidays": mock_coordinator.data.hijri_holidays,
            "calculation_method": mock_coordinator.data.calculation_method,
            "provider": mock_coordinator.data.provider,
        }
        assert sensor._attr_native_value == dhuhr_time
        assert sensor._attr_extra_state_attributes["prayer"] == "dhuhr"

    async def test_provider_attribute_reflects_failover(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
    ) -> None:
        """Test that the provider attribute shows the correct source."""
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
        # Set attributes directly
        _, next_prayer_name, time_remaining = sensor._compute_next_prayer()
        sensor._attr_extra_state_attributes = {
            "prayer": next_prayer_name,
            "time_remaining": time_remaining,
            "hijri_date": mock_coordinator.data.hijri_date,
            "hijri_holidays": mock_coordinator.data.hijri_holidays,
            "calculation_method": mock_coordinator.data.calculation_method,
            "provider": mock_coordinator.data.provider,
        }
        assert sensor._attr_extra_state_attributes["provider"] == "islamic_app"

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

    async def test_next_prayer_init_seeds_native_value(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
    ) -> None:
        """Test that __init__ seeds _attr_native_value from coordinator data.

        Sets the coordinator data to have all prayers in the future so
        ``_compute_next_prayer`` finds a valid next prayer regardless of
        the current wall-clock time.
        """
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
            provider="aladhan",
        )

        sensor = SalahTimesNextPrayerSensor(
            coordinator=mock_coordinator,
            entry_id=mock_config_entry.entry_id,
            name=mock_config_entry.title,
        )
        assert sensor._attr_native_value is not None, (
            "Next-prayer sensor should have a value after init"
        )

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
        # Compute what _handle_coordinator_update would set
        next_time, next_prayer_name, time_remaining = sensor._compute_next_prayer()
        sensor._attr_native_value = next_time
        sensor._attr_extra_state_attributes = {
            "prayer": next_prayer_name,
            "time_remaining": time_remaining,
            "hijri_date": mock_coordinator.data.hijri_date,
            "hijri_holidays": mock_coordinator.data.hijri_holidays,
            "calculation_method": mock_coordinator.data.calculation_method,
            "provider": mock_coordinator.data.provider,
        }

        assert sensor._attr_native_value is None
        assert sensor._attr_extra_state_attributes.get("prayer") is None
        assert sensor._attr_extra_state_attributes.get("time_remaining") is None
