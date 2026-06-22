"""Base entity for the Salah Times integration.

All prayer sensors and the calendar entity inherit from SalahTimesEntity,
which provides device info and coordinator integration.
"""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SalahTimesCoordinator


class SalahTimesEntity(CoordinatorEntity[SalahTimesCoordinator]):
    """Base entity for all Salah Times entities.

    Provides:
    - ``_attr_has_entity_name = True``
    - Device info via ``_attr_device_info``
    - Coordinator integration
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
