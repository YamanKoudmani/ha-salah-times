"""Data update coordinator for the Salah Times integration.

Fetches prayer times on a configurable interval and caches the current
month's calendar data for the calendar entity.
"""

from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import SalahTimesAPI, SalahTimesAPIError
from .const import (
    CONF_CALCULATION_METHOD,
    CONF_HIJRI_ADJUSTMENT_DAYS,
    CONF_LATITUDE,
    CONF_LATITUDE_ADJUSTMENT_METHOD,
    CONF_LONGITUDE,
    CONF_POLLING_INTERVAL_HOURS,
    CONF_SCHOOL,
    DEFAULT_CALCULATION_METHOD,
    DEFAULT_HIJRI_ADJUSTMENT_DAYS,
    DEFAULT_LATITUDE_ADJUSTMENT_METHOD,
    DEFAULT_POLLING_INTERVAL_HOURS,
    DEFAULT_SCHOOL,
    DOMAIN,
)
from .models import PrayerTimes

_LOGGER = logging.getLogger(__name__)


class SalahTimesCoordinator(DataUpdateCoordinator[PrayerTimes]):
    """Coordinator that fetches prayer times on a configurable interval.

    Backed by SalahTimesAPI with optional provider failover.
    Caches the current month's daily prayer data for the calendar entity.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: SalahTimesAPI,
    ) -> None:
        """Initialise the coordinator.

        Sets ``update_interval`` from the config entry's polling interval
        option, and stores references to the API and config entry.

        ``always_update=True`` (the default) guarantees that every refresh
        notifies entity listeners, which ensures sensors always recompute
        their state from the latest coordinator data.  This is important
        because sensor state is read from ``native_value`` through the
        ``state`` property; without the listener firing, stale "unknown"
        state persists.

        Args:
            hass: The Home Assistant instance.
            config_entry: The config entry for this location.
            api: The ``SalahTimesAPI`` wrapper (with failover) to use.
        """
        update_interval = timedelta(
            hours=int(
                config_entry.options.get(
                    CONF_POLLING_INTERVAL_HOURS,
                    DEFAULT_POLLING_INTERVAL_HOURS,
                )
            )
        )
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=update_interval,
            always_update=True,
        )
        self._api = api
        self._config_entry = config_entry
        self._month_cache: dict[date, PrayerTimes] = {}

        # ------------------------------------------------------------------
        # Daily midnight refresh (independent of polling interval)
        # ------------------------------------------------------------------
        # ``update_interval`` alone cannot guarantee a refresh right at the
        # day boundary: with a 6h interval the next poll may land hours
        # after midnight, leaving sensors showing yesterday's data until
        # then.  Registering a wall-clock listener on local 00:00:00 ensures
        # a fresh fetch every night regardless of the configured interval.
        # ``async_track_time_change`` returns a callable that cancels the
        # listener when invoked; it is stored so :meth:`async_unload` can
        # release it on entry teardown.
        self._cancel_midnight_refresh: Callable[[], None] | None = (
            async_track_time_change(
                hass,
                self._handle_midnight_refresh,
                hour=0,
                minute=0,
                second=0,
            )
        )

    # ------------------------------------------------------------------
    # Public property
    # ------------------------------------------------------------------

    @property
    def month_cache(self) -> dict[date, PrayerTimes]:
        """Return the cached month calendar data."""
        return self._month_cache

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_kwargs(self, target_date: date | None = None) -> dict[str, Any]:
        """Build keyword arguments for API calls from config entry data/options.

        Reads the immutable location fields from ``config_entry.data`` and
        the editable calculation fields from ``config_entry.options``.

        Args:
            target_date: Optional date to pass as the ``date`` kwarg for
                daily timings (not used for month-calendar calls).

        Returns:
            A ``dict`` suitable for ``**kwargs`` expansion into
            ``SalahTimesAPI.async_get_timings`` or
            ``SalahTimesAPI.async_get_month_calendar``.
        """
        kwargs: dict[str, Any] = {
            "latitude": float(self._config_entry.data[CONF_LATITUDE]),
            "longitude": float(self._config_entry.data[CONF_LONGITUDE]),
            "method": int(
                self._config_entry.options.get(
                    CONF_CALCULATION_METHOD, DEFAULT_CALCULATION_METHOD
                )
            ),
            "school": int(
                self._config_entry.options.get(CONF_SCHOOL, DEFAULT_SCHOOL)
            ),
            "latitude_adjustment_method": int(
                self._config_entry.options.get(
                    CONF_LATITUDE_ADJUSTMENT_METHOD,
                    DEFAULT_LATITUDE_ADJUSTMENT_METHOD,
                )
            ),
            "hijri_adjustment_days": int(
                self._config_entry.options.get(
                    CONF_HIJRI_ADJUSTMENT_DAYS, DEFAULT_HIJRI_ADJUSTMENT_DAYS
                )
            ),
        }
        if target_date is not None:
            kwargs["date"] = target_date
        return kwargs

    # ------------------------------------------------------------------
    # Coordinator lifecycle
    # ------------------------------------------------------------------

    async def _async_setup(self) -> None:
        """Perform initial data fetch during entry setup.

        Fetches the current month's calendar cache for the calendar entity.
        Daily timings are fetched by ``_async_update_data`` via the
        ``async_config_entry_first_refresh`` call that follows ``_async_setup``.

        If the month cache fetch fails, a warning is logged but setup
        continues — the calendar entity will be empty until the next poll.
        """
        await self._async_refresh_month_cache()

    async def _async_update_data(self) -> PrayerTimes:
        """Fetch the latest prayer times.

        1. Fetches today's timings via the failover-wrapped API.
        2. On month rollover, also refreshes the month calendar cache.

        Returns:
            A fresh ``PrayerTimes`` instance.

        Raises:
            UpdateFailed: If all providers fail.
        """
        try:
            today = date.today()
            kwargs = self._build_kwargs(target_date=today)
            timings = await self._api.async_get_timings(**kwargs)

            # Refresh month cache if the Gregorian month has rolled over
            if self._month_cache:
                # The cache dict is keyed by date; peek at any key to
                # determine which month is currently cached.
                cached_key = next(iter(self._month_cache.keys()))
                if cached_key.month != today.month or cached_key.year != today.year:
                    await self._async_refresh_month_cache()

            return timings
        except SalahTimesAPIError as err:
            raise UpdateFailed(
                f"Failed to update prayer times: {err}"
            ) from err

    async def _async_refresh_month_cache(self, force: bool = False) -> None:
        """Fetch the current month's calendar and populate ``_month_cache``.

        Called on initial setup and on month rollover.  Skips refresh if
        the cache already contains the current month (unless ``force`` is
        ``True``).

        Failures are logged but do **not** propagate — the coordinator can
        still serve daily timings without a complete calendar.
        """
        if not force and self._month_cache:
            today = date.today()
            cached_key = next(iter(self._month_cache.keys()))
            if cached_key.month == today.month and cached_key.year == today.year:
                return

        try:
            today = date.today()
            kwargs = self._build_kwargs()
            kwargs["month"] = today.month
            kwargs["year"] = today.year
            self._month_cache = await self._api.async_get_month_calendar(**kwargs)
        except SalahTimesAPIError as err:
            _LOGGER.warning("Failed to refresh month cache: %s", err)

    async def _handle_midnight_refresh(self, now: Any) -> None:
        """Trigger a refresh at local midnight each day.

        Wired to ``async_track_time_change`` in :meth:`__init__`.  Fires
        at 00:00:00 local time, independent of ``update_interval``, so
        sensors never sit on yesterday's data when the regular poll would
        otherwise land hours after the day boundary.

        ``now`` is the ``datetime`` injected by the time-change helper
        (unused, but required by the callback signature).
        """
        _LOGGER.debug("Midnight refresh triggered for %s", DOMAIN)
        await self.async_request_refresh()

    async def async_unload(self) -> None:
        """Cancel the midnight refresh listener.

        Intended to be wired to ``ConfigEntry.async_on_unload`` by the
        integration's ``__init__.py`` so the listener is released on
        config-entry teardown.  Safe to call multiple times.
        """
        if self._cancel_midnight_refresh is not None:
            self._cancel_midnight_refresh()
            self._cancel_midnight_refresh = None
