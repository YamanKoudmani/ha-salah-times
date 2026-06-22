"""Calendar entity for the Salah Times integration.

Provides a CalendarEntity that shows daily prayer times in the HA Calendar UI
and supports calendar-based automations (e.g. trigger 5 min before Fajr).
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_EVENT_DURATION, DOMAIN
from .coordinator import SalahTimesCoordinator
from .entity import SalahTimesEntity
from .models import PRAYER_ORDER

_LOGGER = logging.getLogger(__name__)

class SalahCalendarEntity(SalahTimesEntity, CalendarEntity):
    """Calendar entity showing daily prayer times.

    Backed by the coordinator's month cache. Extends to multi-month
    by fetching additional calendar pages on demand (capped at 12 months).
    """

    _attr_order = 100
    _attr_translation_key = "prayer_schedule"
    _attr_name = "Prayer Schedule"
    _attr_icon = "mdi:calendar-text"

    def __init__(
        self,
        coordinator: SalahTimesCoordinator,
        entry_id: str,
        name: str,
    ) -> None:
        """Initialise the calendar entity.

        Args:
            coordinator: The data coordinator with month cache.
            entry_id: Config entry ID for unique_id prefix.
            name: Location name (also used as entity name).
        """
        super().__init__(coordinator, entry_id, name)
        self._attr_unique_id = f"{entry_id}-calendar"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the currently ongoing prayer event, if any.

        A prayer is considered "ongoing" from its start time until
        start + 10 minutes (the default duration).

        Returns the CalendarEvent for whichever prayer is currently active,
        or None if no obligatory prayer is in progress.
        """
        if self.coordinator.data is None:
            return None

        now = dt_util.utcnow()
        timings = self.coordinator.data.timings

        for prayer in PRAYER_ORDER:
            prayer_time = timings.get(prayer)
            if prayer_time is None:
                continue
            end_time = prayer_time + DEFAULT_EVENT_DURATION
            if prayer_time <= now < end_time:
                return CalendarEvent(
                    summary=prayer.value.title(),
                    start=prayer_time,
                    end=end_time,
                )

        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return a list of CalendarEvents within the given date range.

        Creates one event per prayer per day. Each event has:
        - summary: Prayer name (title-cased).
        - start: Prayer time.
        - end: Prayer time + 10 minutes (default duration).

        For v1 this serves from the coordinator's month cache and logs a
        warning if the requested range exceeds the cached data.

        Args:
            hass: The HomeAssistant instance.
            start_date: Start of the query range (timezone-aware UTC).
            end_date: End of the query range (timezone-aware UTC).

        Returns:
            A list of CalendarEvent objects.
        """
        events: list[CalendarEvent] = []
        cache = self.coordinator.month_cache

        if not cache:
            _LOGGER.warning(
                "Month cache is empty; calendar events will be empty for range %s – %s",
                start_date,
                end_date,
            )
            return events

        # Determine the date range covered by the cache
        cached_dates = set(cache.keys())
        if cached_dates:
            min_cached = min(cached_dates)
            max_cached = max(cached_dates)
            req_start = start_date.date()
            req_end = end_date.date()

            if req_start < min_cached or req_end > max_cached:
                _LOGGER.warning(
                    "Requested calendar range %s – %s extends beyond cached month data "
                    "(%s – %s). Returning events from cache only. "
                    "Multi-month fetch will be added in a future version.",
                    req_start,
                    req_end,
                    min_cached,
                    max_cached,
                )

        for cache_date, pt in cache.items():
            if start_date.date() <= cache_date <= end_date.date():
                for prayer in PRAYER_ORDER:
                    prayer_time = pt.timings.get(prayer)
                    if prayer_time is None:
                        continue
                    events.append(
                        CalendarEvent(
                            summary=prayer.value.title(),
                            start=prayer_time,
                            end=prayer_time + DEFAULT_EVENT_DURATION,
                        )
                    )

        return events


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Salah Calendar entity from a config entry.

    Args:
        hass: The HomeAssistant instance.
        entry: The config entry for this location.
        async_add_entities: Callback to add entities.
    """
    coordinator: SalahTimesCoordinator = entry.runtime_data
    async_add_entities(
        [SalahCalendarEntity(coordinator, entry.entry_id, entry.title)]
    )
