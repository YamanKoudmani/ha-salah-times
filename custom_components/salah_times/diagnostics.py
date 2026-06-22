"""Diagnostics support for the Salah Times integration.

Provides config entry diagnostics with lat/lon redacted.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .coordinator import SalahTimesCoordinator

# Keys to redact from diagnostics output.
TO_REDACT: set[str] = {CONF_LATITUDE, CONF_LONGITUDE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    Returns a dict containing:
    - entry data/options (with lat/lon redacted)
    - coordinator data (if available)
    - month cache size

    Args:
        hass: The HomeAssistant instance.
        config_entry: The config entry to diagnose.

    Returns:
        A dict with redacted sensitive data.
    """
    coordinator: SalahTimesCoordinator | None = getattr(
        config_entry, "runtime_data", None
    )

    result: dict[str, Any] = {
        "entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
    }

    if coordinator is not None:
        result["data"] = coordinator.data
        result["month_cache_size"] = len(coordinator.month_cache)
    else:
        result["data"] = None
        result["month_cache_size"] = 0

    return result
