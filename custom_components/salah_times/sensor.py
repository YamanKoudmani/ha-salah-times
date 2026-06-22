"""Sensors for the Salah Times integration.

Provides one timestamp sensor per prayer name and one "next prayer" sensor
with countdown and hijri attributes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SalahTimesCoordinator
from .entity import SalahTimesEntity
from .models import PRAYER_ORDER, PrayerName

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


class SalahTimesPrayerSensor(SalahTimesEntity):
    """Represents a single prayer time as a timestamp sensor."""

    def __init__(
        self,
        coordinator: SalahTimesCoordinator,
        entry_id: str,
        name: str,
        description: SensorEntityDescription,
        prayer: PrayerName,
    ) -> None:
        """Initialise the prayer timestamp sensor.

        Args:
            coordinator: The data coordinator.
            entry_id: Config entry ID for unique_id prefix.
            name: Location name for device info.
            description: Sensor entity description.
            prayer: Which prayer this sensor tracks.
        """
        super().__init__(coordinator, entry_id, name)
        self.entity_description = description
        self._prayer = prayer
        self._attr_unique_id = f"{entry_id}-{prayer.value}"

    @property
    def native_value(self) -> datetime | None:
        """Return the UTC datetime of this prayer time.

        Returns the timezone-aware UTC datetime from coordinator.data.timings.
        Returns None if the coordinator has not yet fetched data.
        """
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.timings.get(self._prayer)


# ---------------------------------------------------------------------------
# Next-prayer sensor
# ---------------------------------------------------------------------------


class SalahTimesNextPrayerSensor(SalahTimesEntity):
    """Represents the next upcoming obligatory prayer with countdown attributes."""

    def __init__(
        self,
        coordinator: SalahTimesCoordinator,
        entry_id: str,
        name: str,
    ) -> None:
        """Initialise the next prayer sensor.

        Args:
            coordinator: The data coordinator.
            entry_id: Config entry ID for unique_id prefix.
            name: Location name for device info.
        """
        super().__init__(coordinator, entry_id, name)
        self.entity_description = NextPrayerSensorDescription()
        self._attr_unique_id = f"{entry_id}-next_prayer"

    @property
    def native_value(self) -> datetime | None:
        """Return the UTC datetime of the next upcoming obligatory prayer.

        Only considers the 5 obligatory prayers (Fajr, Dhuhr, Asr, Maghrib, Isha).
        Returns None if all today's prayers have passed (the next poll will pick
        up the following day's times).
        """
        if self.coordinator.data is None:
            return None
        now = dt_util.utcnow()
        timings = self.coordinator.data.timings
        for prayer in PRAYER_ORDER:
            prayer_time = timings.get(prayer)
            if prayer_time is not None and prayer_time > now:
                return prayer_time
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes.

        Attributes:
            prayer: Name of the next prayer (e.g. "maghrib").
            time_remaining: Seconds until that prayer.
            hijri_date: Hijri date string.
            hijri_holidays: List of Islamic holidays.
            calculation_method: Name of the calculation method used.
            provider: "aladhan" or "islamic_app".
        """
        if self.coordinator.data is None:
            return {}

        data = self.coordinator.data
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

        return {
            "prayer": next_prayer_name,
            "time_remaining": time_remaining,
            "hijri_date": data.hijri_date,
            "hijri_holidays": data.hijri_holidays,
            "calculation_method": data.calculation_method,
            "provider": data.provider,
        }


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

    Args:
        hass: The HomeAssistant instance.
        entry: The config entry for this location.
        async_add_entities: Callback to add entities.
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
