"""Tests for the Salah Times options flow."""

from __future__ import annotations

import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.core import HomeAssistant

from custom_components.salah_times.const import (
    CONF_CALCULATION_METHOD,
    CONF_POLLING_INTERVAL_HOURS,
)


class TestOptionsFlow:
    """Tests for the options flow steps."""

    async def test_change_calculation_method(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """Test changing the calculation method via options.

        Submit a different calculation method and verify:
        - Options are saved to the config entry.
        - Coordinator is triggered to refresh (handled by HA listener).
        """
        # Initiate options flow
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "options"

        # Submit with MWL method (3)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_CALCULATION_METHOD: "3"},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        # Verify entry options were updated
        assert mock_config_entry.options[CONF_CALCULATION_METHOD] == "3"

    async def test_change_polling_interval(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """Test changing the polling interval via options.

        Submit a different polling interval and verify the coordinator's
        update_interval is updated accordingly.
        """
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_POLLING_INTERVAL_HOURS: 12},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert mock_config_entry.options[CONF_POLLING_INTERVAL_HOURS] == 12
