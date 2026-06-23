"""Salah Times integration for Home Assistant.

Fetches Islamic prayer times from a public REST API and exposes them
as timestamp sensors, a next-prayer sensor, and a calendar entity.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AlAdhanClient, IslamicAppClient, SalahTimesAPI
from .const import (
    CONF_ENABLE_FAILOVER,
    CONF_POLLING_INTERVAL_HOURS,
    DEFAULT_ENABLE_FAILOVER,
    DEFAULT_POLLING_INTERVAL_HOURS,
    DOMAIN,
    ICON,
    SERVICE_REFRESH,
)
from .coordinator import SalahTimesCoordinator

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------
type SalahTimesConfigEntry = ConfigEntry[SalahTimesCoordinator]

# ---------------------------------------------------------------------------
# Platforms
# ---------------------------------------------------------------------------
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.CALENDAR,
    Platform.BUTTON,
]

# Card file URL — served by the static path registered in async_setup_entry
_CARD_BASE_URL = "/salah_times/frontend"
_CARD_URL = f"{_CARD_BASE_URL}/salah-times-card.js"


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Salah Times integration.

    Registers the ``salah_times.refresh`` service once for all config entries.
    Individual entries are stored in ``hass.data[DOMAIN]`` keyed by entry_id
    so the service handler can resolve the correct coordinator(s) to refresh.

    Args:
        hass: The HomeAssistant instance.
        config: The YAML configuration (unused — config flow only).

    Returns:
        True.
    """
    hass.data.setdefault(DOMAIN, {})

    async def _async_handle_refresh_service(call: ServiceCall) -> None:
        """Force an immediate coordinator refresh for targeted or all entries.

        If ``entity_id`` is provided in the service call, only the coordinator(s)
        owning those entities are refreshed.  Otherwise, all Salah Times
        coordinators are refreshed.
        """
        coordinators: list[SalahTimesCoordinator] = list(
            hass.data[DOMAIN].values()
        )
        for coordinator in coordinators:
            await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, _async_handle_refresh_service)

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SalahTimesConfigEntry,
) -> bool:
    """Set up Salah Times from a config entry.

    1. Create the SalahTimesAPI and SalahTimesCoordinator.
    2. Store coordinator on entry.runtime_data and in hass.data[DOMAIN].
    3. Call coordinator.async_config_entry_first_refresh().
    4. Forward setup to platforms (sensor, calendar).
    5. Listen for options updates.

    Args:
        hass: The HomeAssistant instance.
        entry: The config entry.

    Returns:
        True on success.
    """
    session = async_get_clientsession(hass)

    aladhan = AlAdhanClient(session)
    fallback = IslamicAppClient(session)
    enable_failover = entry.options.get(
        CONF_ENABLE_FAILOVER, DEFAULT_ENABLE_FAILOVER
    )
    api = SalahTimesAPI(
        primary=aladhan,
        fallback=fallback,
        enable_failover=enable_failover,
    )

    coordinator = SalahTimesCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Store coordinator for service handler resolution (multi-entry support)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # ------------------------------------------------------------------
    # Release the daily midnight refresh listener on entry teardown
    # ------------------------------------------------------------------
    # The coordinator registers a wall-clock listener on local 00:00:00
    # so a refresh always happens at the day boundary regardless of the
    # configured polling interval.  Wire its cancellation to the entry
    # lifecycle so reloading/unloading the entry releases the listener.
    entry.async_on_unload(coordinator.async_unload)

    # ------------------------------------------------------------------
    # Listen for options updates
    # ------------------------------------------------------------------
    entry.async_on_unload(
        entry.add_update_listener(async_options_updated)
    )

    # ------------------------------------------------------------------
    # Forward to sensor and calendar platforms
    # ------------------------------------------------------------------
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ------------------------------------------------------------------
    # Register the built frontend card (one time only)
    # ------------------------------------------------------------------
    # 1. Serve the card file at a known URL via the static-path config.
    # 2. Register the URL as a Lovelace resource so the card appears in
    #    the card picker. ResourceStorageCollection persists across HA
    #    restarts in storage-mode dashboards; add_extra_js_url is the
    #    fallback for YAML-mode dashboards.
    if "salah_times_card_registered" not in hass.data.get(DOMAIN, {}):
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                url_path=_CARD_BASE_URL,
                path=str(Path(__file__).parent / "frontend" / "dist"),
                cache_headers=False,
            )
        ])
        await _async_register_card_resource(hass, _CARD_URL)
        hass.data.setdefault(DOMAIN, {})["salah_times_card_registered"] = True

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: SalahTimesConfigEntry,
) -> bool:
    """Unload a config entry.

    Unloads all platforms for this entry and removes the coordinator
    from hass.data[DOMAIN].  The refresh service is registered once in
    async_setup and is NOT unregistered here (it serves all entries).

    Args:
        hass: The HomeAssistant instance.
        entry: The config entry.

    Returns:
        True if all platforms unloaded successfully.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_options_updated(
    hass: HomeAssistant,
    entry: SalahTimesConfigEntry,
) -> None:
    """Handle options update.

    Triggered when the user changes options via the options flow.
    Updates the coordinator's update_interval and failover setting,
    then forces an immediate refresh so the new settings take effect.

    Args:
        hass: The HomeAssistant instance.
        entry: The config entry with updated options.
    """
    coordinator = entry.runtime_data

    # Update polling interval
    polling_interval_hours = int(
        entry.options.get(
            CONF_POLLING_INTERVAL_HOURS, DEFAULT_POLLING_INTERVAL_HOURS
        )
    )
    coordinator.update_interval = timedelta(hours=polling_interval_hours)

    # Update failover setting
    enable_failover = entry.options.get(
        CONF_ENABLE_FAILOVER, DEFAULT_ENABLE_FAILOVER
    )
    coordinator._api.set_failover_enabled(enable_failover)

    await coordinator.async_request_refresh()


async def _async_register_card_resource(
    hass: HomeAssistant, card_url: str
) -> None:
    """Register the card JS as a Lovelace resource.

    Tries the modern ResourceStorageCollection first (persists across
    restarts in storage-mode dashboards). Falls back to
    ``add_extra_js_url`` for YAML-mode dashboards or when the
    resource collection is not yet available.

    Idempotent: re-runs update the existing entry rather than
    creating duplicates. Safe to call on every config-entry setup.
    """
    lovelace = hass.data.get("lovelace")
    resources = (
        lovelace.resources
        if lovelace is not None and hasattr(lovelace, "resources")
        else None
    )

    if isinstance(resources, ResourceStorageCollection):
        # Force-load if not already loaded — required on first HA boot.
        if hasattr(resources, "loaded") and not getattr(resources, "loaded", False):
            await resources.async_load()
            resources.loaded = True  # type: ignore[attr-defined]

        for item in resources.async_items():
            url = item.get("url", "")
            if url.startswith(_CARD_BASE_URL):
                # Already registered — just update the URL if it changed
                # (e.g. cache-buster query string or path correction).
                if url != card_url:
                    await resources.async_update_item(
                        item["id"],
                        {"res_type": "module", "url": card_url},
                    )
                return

        await resources.async_create_item(
            {"res_type": "module", "url": card_url}
        )
        return

    # Fallback: YAML-mode Lovelace or resource collection unavailable.
    add_extra_js_url(hass, card_url)
