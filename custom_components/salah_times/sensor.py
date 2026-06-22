"""Sensors for the Salah Times integration.

Provides one timestamp sensor per prayer name and one "next prayer" sensor
with countdown and hijri attributes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import SalahTimesCoordinator
from .entity import SalahTimesEntity
from .models import PRAYER_ORDER, PrayerName, PrayerTimes

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prayer timestamp sensor descriptions
# ---------------------------------------------------------------------------
PRAYER_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=PrayerName.FAJR.value,
        translation_key="fajr",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key=PrayerName.SUNRISE.value,
        translation_key="sunrise",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=PrayerName.DHUHR.value,
        translation_key="dhuhr",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key=PrayerName.ASR.value,
        translation_key="asr",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key=PrayerName.MAGHRIB.value,
        translation_key="maghrib",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key=PrayerName.ISHA.value,
        translation_key="isha",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key=PrayerName.IMSAK.value,
        translation_key="imsak",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=PrayerName.MIDNIGHT.value,
        translation_key="midnight",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
)


# ---------------------------------------------------------------------------
# Next-prayer sensor description
# ---------------------------------------------------------------------------


@dataclass
class NextPrayerSensorDescription(SensorEntityDescription):
    """Sensor description for the next-prayer sensor with extra attributes."""

    key: str = "next_prayer"
    translation_key: str = "next_prayer"
    device_class: SensorDeviceClass = SensorDeviceClass.TIMESTAMP


# ---------------------------------------------------------------------------
# Prayer timestamp sensor
# ---------------------------------------------------------------------------


class SalahTimesPrayerSensor(SalahTimesEntity, SensorEntity):
    """Represents a single prayer time as a timestamp sensor."""

    def __init__(
        self,
        coordinator: SalahTimesCoordinator,
        entry_id: str,
        name: str,
        description: SensorEntityDescription,
        prayer: PrayerName,
    ) -> None:
        """Initialise the prayer timestamp sensor."""
        super().__init__(coordinator, entry_id, name)
        self.entity_description = description
        self._prayer = prayer
        self._attr_unique_id = f"{entry_id}-{prayer.value}"
        # Seed the initial value from the already-populated coordinator so the
        # very first state write (in add_to_platform_finish) produces a valid
        # timestamp instead of "unknown".  This is a belt-and-suspenders guard
        # alongside async_added_to_hass: the coordinator's first refresh
        # completes before entities are created, so data is always available
        # here, and seeding it at creation time bypasses the platform-state
        # check that silently drops writes inside async_added_to_hass.
        if coordinator.data is not None:
            value = coordinator.data.timings.get(prayer)
            if value is not None:
                self._attr_native_value = value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data: PrayerTimes | None = self.coordinator.data
        if data is not None:
            value = data.timings.get(self._prayer)
            _LOGGER.debug(
                "Prayer sensor %s: value=%s type=%s",
                self._prayer,
                value,
                type(value).__name__ if value else "None",
            )
            self._attr_native_value = value
        else:
            self._attr_native_value = None
        self.async_write_ha_state()


# ---------------------------------------------------------------------------
# Next-prayer sensor
# ---------------------------------------------------------------------------


class SalahTimesNextPrayerSensor(SalahTimesEntity, SensorEntity):
    """Represents the next upcoming obligatory prayer with countdown attributes."""

    def __init__(
        self,
        coordinator: SalahTimesCoordinator,
        entry_id: str,
        name: str,
    ) -> None:
        """Initialise the next prayer sensor."""
        super().__init__(coordinator, entry_id, name)
        self.entity_description = NextPrayerSensorDescription()
        self._attr_unique_id = f"{entry_id}-next_prayer"
        # Seed initial state — same rationale as SalahTimesPrayerSensor;
        # the coordinator's first refresh completes before entities exist.
        next_time, _, _ = self._compute_next_prayer()
        if next_time is not None:
            self._attr_native_value = next_time

    def _compute_next_prayer(self) -> tuple[datetime | None, str | None, int | None]:
        """Compute the next upcoming obligatory prayer.

        Returns:
            Tuple of (next_time, prayer_name, time_remaining_seconds).
        """
        data: PrayerTimes | None = self.coordinator.data
        if data is None:
            return None, None, None

        now = dt_util.utcnow()
        for prayer in PRAYER_ORDER:
            prayer_time = data.timings.get(prayer)
            if prayer_time is not None and prayer_time > now:
                remaining = int((prayer_time - now).total_seconds())
                return prayer_time, prayer.value, remaining

        return None, None, None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        Sets ``_attr_native_value`` and ``_attr_extra_state_attributes``
        directly.  In HA 2026.6+ this is the preferred pattern — property
        overrides on ``native_value`` may not be called reliably.
        """
        data: PrayerTimes | None = self.coordinator.data
        if data is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = None
            self.async_write_ha_state()
            return

        now = dt_util.utcnow()
        next_time: datetime | None = None
        next_prayer_name: str | None = None

        for prayer in PRAYER_ORDER:
            prayer_time = data.timings.get(prayer)
            if prayer_time is not None and prayer_time > now:
                next_time = prayer_time
                next_prayer_name = prayer.value
                break

        time_remaining: int | None = None
        if next_time is not None:
            time_remaining = int((next_time - now).total_seconds())

        _LOGGER.debug(
            "Next prayer: name=%s time=%s remaining=%s",
            next_prayer_name,
            next_time,
            time_remaining,
        )

        self._attr_native_value = next_time
        self._attr_extra_state_attributes = {
            "prayer": next_prayer_name,
            "time_remaining": time_remaining,
            "hijri_date": data.hijri_date,
            "hijri_holidays": data.hijri_holidays,
            "calculation_method": data.calculation_method,
            "provider": data.provider,
        }
        self.async_write_ha_state()


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Salah Times sensors from a config entry.

    Creates 8 prayer timestamp sensors and 1 next-prayer sensor.
    """
    coordinator: SalahTimesCoordinator = entry.runtime_data

    sensors: list[SalahTimesEntity] = []
    for description in PRAYER_SENSORS:
        prayer = PrayerName(description.key)
        sensors.append(
            SalahTimesPrayerSensor(
                coordinator=coordinator,
                entry_id=entry.entry_id,
                name=entry.title,
                description=description,
                prayer=prayer,
            )
        )

    sensors.append(
        SalahTimesNextPrayerSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            name=entry.title,
        )
    )

    async_add_entities(sensors)
