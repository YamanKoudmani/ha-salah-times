"""Base entity for the Salah Times integration.

All prayer sensors and the calendar entity inherit from SalahTimesEntity,
which provides device info and coordinator integration.
"""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SalahTimesCoordinator


class SalahTimesEntity(CoordinatorEntity[SalahTimesCoordinator]):
    """Base entity for all Salah Times entities.

    Provides:
    - ``_attr_has_entity_name = True``
    - Device info via ``device_info`` property
    - Coordinator integration with initial data push on entity add
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SalahTimesCoordinator,
        entry_id: str,
        name: str,
    ) -> None:
        """Initialise the entity.

        Args:
            coordinator: The data coordinator.
            entry_id: The config entry ID (used for unique_id prefix).
            name: The user-facing name for this location (e.g. "Home").
        """
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._location_name = name

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        Delegates to subclass implementation.  Subclasses override this
        to set ``_attr_native_value`` etc., then call
        ``self.async_write_ha_state()``.
        """
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass.

        The coordinator's first refresh happens BEFORE entities are
        created (in ``async_setup_entry``).  This means ``_handle_coordinator_update``
        would never be called for the initial data — the entity would
        show "unknown" until the next poll (potentially hours later).

        By calling ``_handle_coordinator_update`` here, we push the
        coordinator's existing data to the entity immediately on add.
        """
        await super().async_added_to_hass()
        if self.coordinator.data is not None:
            self._handle_coordinator_update()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this config entry.

        Groups all entities under one device per config entry.
        The model reflects the active provider (updates on failover).
        """
        model = "AlAdhan"
        if self.coordinator.data and self.coordinator.data.provider:
            model = self.coordinator.data.provider.replace("_", " ").title()
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._location_name,
            manufacturer="Salah Times",
            model=model,
            entry_type=DeviceEntryType.SERVICE,
        )
