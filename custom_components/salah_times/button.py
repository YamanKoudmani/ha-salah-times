"""Button platform for the Salah Times integration.

Provides a debug button that force-refreshes the coordinator data on press.
Disabled by default — users must explicitly enable it.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SalahTimesCoordinator
from .entity import SalahTimesEntity

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Button description
# ---------------------------------------------------------------------------

DEBUG_REFRESH_DESCRIPTION = ButtonEntityDescription(
    key="refresh",
    name="Refresh",
    translation_key="refresh",
    icon="mdi:refresh",
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
)


# ---------------------------------------------------------------------------
# Debug refresh button
# ---------------------------------------------------------------------------


class SalahTimesDebugRefreshButton(SalahTimesEntity, ButtonEntity):
    """Button that force-refreshes the coordinator data.

    Disabled by default (entity_category=DIAGNOSTIC).  On press, calls
    ``coordinator.async_request_refresh()`` to immediately fetch the
    latest prayer times from the API.
    """

    def __init__(
        self,
        coordinator: SalahTimesCoordinator,
        entry_id: str,
        name: str,
    ) -> None:
        """Initialise the debug refresh button."""
        super().__init__(coordinator, entry_id, name)
        self.entity_description = DEBUG_REFRESH_DESCRIPTION
        self._attr_unique_id = f"{entry_id}-refresh"
        self._attr_order = 200

    async def async_press(self) -> None:
        """Press the button — force-refresh the coordinator."""
        _LOGGER.debug("Debug refresh button pressed — requesting coordinator refresh")
        await self.coordinator.async_request_refresh()


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Salah Times debug button from a config entry."""
    coordinator: SalahTimesCoordinator = entry.runtime_data

    async_add_entities(
        [
            SalahTimesDebugRefreshButton(
                coordinator=coordinator,
                entry_id=entry.entry_id,
                name=entry.title,
            )
        ]
    )
