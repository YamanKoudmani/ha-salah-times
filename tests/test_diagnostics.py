"""Tests for the Salah Times diagnostics."""

from __future__ import annotations

import pytest
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from custom_components.salah_times.diagnostics import (
    async_get_config_entry_diagnostics,
)


class TestDiagnostics:
    """Tests for diagnostics data."""

    async def test_redacts_coordinates(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_coordinator,
    ) -> None:
        """Test that lat/lon are redacted in diagnostics output."""
        # Wire the coordinator so diagnostics can find it
        mock_config_entry.runtime_data = mock_coordinator

        result = await async_get_config_entry_diagnostics(
            hass, mock_config_entry
        )

        # The entry data should be a nested dict under result["entry"]
        entry_data = result["entry"]["data"]

        # Latitude and longitude should be redacted
        assert entry_data[CONF_LATITUDE] == "**REDACTED**"
        assert entry_data[CONF_LONGITUDE] == "**REDACTED**"

        # Coordinator data should be present
        assert result["data"] is not None
        assert result["month_cache_size"] > 0
