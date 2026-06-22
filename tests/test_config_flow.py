"""Tests for the Salah Times config flow."""

from __future__ import annotations

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.salah_times.const import (
    CONF_CALCULATION_METHOD,
    CONF_ENABLE_FAILOVER,
    CONF_HIJRI_ADJUSTMENT_DAYS,
    CONF_LATITUDE_ADJUSTMENT_METHOD,
    CONF_POLLING_INTERVAL_HOURS,
    CONF_SCHOOL,
    DEFAULT_CALCULATION_METHOD,
    DEFAULT_ENABLE_FAILOVER,
    DEFAULT_HIJRI_ADJUSTMENT_DAYS,
    DEFAULT_LATITUDE_ADJUSTMENT_METHOD,
    DEFAULT_POLLING_INTERVAL_HOURS,
    DEFAULT_SCHOOL,
    DOMAIN,
)


class TestConfigFlow:
    """Tests for the user and reconfigure config flow steps."""

    async def test_user_step_happy_path(
        self, hass: HomeAssistant
    ) -> None:
        """Test the full user step with valid input creates an entry.

        Submit name, lat, lon and verify the config entry is created with
        the correct unique_id and data.
        """
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Test Location",
                CONF_LATITUDE: {"latitude": 40.7128, "longitude": -74.0060},
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Test Location"
        assert result["data"][CONF_LATITUDE] == 40.7128
        assert result["data"][CONF_LONGITUDE] == -74.0060
        # Verify options are seeded with defaults
        assert result["options"][CONF_CALCULATION_METHOD] == DEFAULT_CALCULATION_METHOD
        assert result["options"][CONF_SCHOOL] == DEFAULT_SCHOOL
        assert (
            result["options"][CONF_LATITUDE_ADJUSTMENT_METHOD]
            == DEFAULT_LATITUDE_ADJUSTMENT_METHOD
        )
        assert result["options"][CONF_HIJRI_ADJUSTMENT_DAYS] == DEFAULT_HIJRI_ADJUSTMENT_DAYS
        assert (
            result["options"][CONF_POLLING_INTERVAL_HOURS]
            == DEFAULT_POLLING_INTERVAL_HOURS
        )
        assert result["options"][CONF_ENABLE_FAILOVER] == DEFAULT_ENABLE_FAILOVER

        # The config flow framework auto-sets-up the new entry, which
        # creates a coordinator and registers the midnight-refresh
        # listener.  Cleanup is handled by the conftest autouse
        # fixture, which walks SalahTimesCoordinator._all_instances
        # and calls async_unload on every coordinator created during
        # the test.

    async def test_unique_id_collision_abort(
        self, hass: HomeAssistant
    ) -> None:
        """Test that adding a duplicate lat/lon aborts.

        Create one entry, then attempt another with the same coordinates.
        Verify that the flow aborts with "already_configured".
        """
        # Create first entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Home",
                CONF_LATITUDE: {"latitude": 40.7128, "longitude": -74.0060},
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

        # Attempt second entry with same coordinates
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Duplicate",
                CONF_LATITUDE: {"latitude": 40.7128, "longitude": -74.0060},
            },
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"

        # Coordinator cleanup is handled by the conftest autouse
        # fixture via the class-level _all_instances registry.

    async def test_invalid_coordinates(
        self, hass: HomeAssistant
    ) -> None:
        """Test that out-of-range lat/lon raises an error.

        Latitude > 90 or < -90 should show the invalid_coordinates error.
        Longitude > 180 or < -180 should show the invalid_coordinates error.
        """
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Bad",
                CONF_LATITUDE: {"latitude": 999, "longitude": 0.0},
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_coordinates"

    async def test_reconfigure(
        self, hass: HomeAssistant
    ) -> None:
        """Test that reconfigure updates name/lat/lon.

        Start reconfigure flow, submit new coordinates, verify the
        entry data is updated.
        """
        # Create initial entry
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="40.7128--74.0060",
            data={
                CONF_NAME: "Original",
                CONF_LATITUDE: 40.7128,
                CONF_LONGITUDE: -74.0060,
            },
            options={
                CONF_CALCULATION_METHOD: DEFAULT_CALCULATION_METHOD,
                CONF_SCHOOL: DEFAULT_SCHOOL,
                CONF_LATITUDE_ADJUSTMENT_METHOD: DEFAULT_LATITUDE_ADJUSTMENT_METHOD,
                CONF_HIJRI_ADJUSTMENT_DAYS: DEFAULT_HIJRI_ADJUSTMENT_DAYS,
                CONF_POLLING_INTERVAL_HOURS: DEFAULT_POLLING_INTERVAL_HOURS,
                CONF_ENABLE_FAILOVER: DEFAULT_ENABLE_FAILOVER,
            },
        )
        entry.add_to_hass(hass)

        # Initiate reconfigure flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"
        # The form should be pre-populated with original values
        data_schema = result["data_schema"]
        assert data_schema is not None

        # Submit new coordinates
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Updated Location",
                CONF_LATITUDE: {"latitude": 34.0522, "longitude": -118.2437},
            },
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

        # ``async_update_reload_and_abort`` reloads the entry, which
        # sets it up and registers the midnight-refresh listener.
        # Cleanup is handled by the conftest autouse fixture via the
        # class-level _all_instances registry.
        # Verify entry data was updated
        assert entry.data[CONF_NAME] == "Updated Location"
        assert entry.data[CONF_LATITUDE] == 34.0522
        assert entry.data[CONF_LONGITUDE] == -118.2437
        # Note: In HA 2026.2, async_update_reload_and_abort does not update
        # the entry's unique_id unless explicitly passed. The implementation
        # sets the unique_id on the flow for abort-if-configured checks but
        # does not pass it to async_update_reload_and_abort, so the entry's
        # unique_id remains unchanged (which is fine — unique IDs are stable
        # across reconfigure flows).

    async def test_reconfigure_collision(
        self, hass: HomeAssistant
    ) -> None:
        """Test reconfigure to coordinates that collide with another entry.

        Entry A is at (40.7128, -74.0060).  Entry B is at (34.0522, -118.2437).
        Reconfiguring entry B to (40.7128, -74.0060) should abort with
        'already_configured' because entry A already owns that unique_id.
        """
        # Create entry A (NYC)
        entry_a = MockConfigEntry(
            domain=DOMAIN,
            unique_id="40.7128--74.0060",
            data={
                CONF_NAME: "NYC",
                CONF_LATITUDE: 40.7128,
                CONF_LONGITUDE: -74.0060,
            },
            options={
                CONF_CALCULATION_METHOD: DEFAULT_CALCULATION_METHOD,
                CONF_SCHOOL: DEFAULT_SCHOOL,
                CONF_LATITUDE_ADJUSTMENT_METHOD: DEFAULT_LATITUDE_ADJUSTMENT_METHOD,
                CONF_HIJRI_ADJUSTMENT_DAYS: DEFAULT_HIJRI_ADJUSTMENT_DAYS,
                CONF_POLLING_INTERVAL_HOURS: DEFAULT_POLLING_INTERVAL_HOURS,
                CONF_ENABLE_FAILOVER: DEFAULT_ENABLE_FAILOVER,
            },
        )
        entry_a.add_to_hass(hass)

        # Create entry B (LA)
        entry_b = MockConfigEntry(
            domain=DOMAIN,
            unique_id="34.0522--118.2437",
            data={
                CONF_NAME: "LA",
                CONF_LATITUDE: 34.0522,
                CONF_LONGITUDE: -118.2437,
            },
            options={
                CONF_CALCULATION_METHOD: DEFAULT_CALCULATION_METHOD,
                CONF_SCHOOL: DEFAULT_SCHOOL,
                CONF_LATITUDE_ADJUSTMENT_METHOD: DEFAULT_LATITUDE_ADJUSTMENT_METHOD,
                CONF_HIJRI_ADJUSTMENT_DAYS: DEFAULT_HIJRI_ADJUSTMENT_DAYS,
                CONF_POLLING_INTERVAL_HOURS: DEFAULT_POLLING_INTERVAL_HOURS,
                CONF_ENABLE_FAILOVER: DEFAULT_ENABLE_FAILOVER,
            },
        )
        entry_b.add_to_hass(hass)

        # Initiate reconfigure on entry B
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry_b.entry_id,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

        # Submit the same coordinates as entry A (NYC) — should collide
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "LA Renamed",
                CONF_LATITUDE: {"latitude": 40.7128, "longitude": -74.0060},
            },
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
