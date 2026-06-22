"""Tests for the Salah Times debug button."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant

from custom_components.salah_times.button import (
    DEBUG_REFRESH_DESCRIPTION,
    SalahTimesDebugRefreshButton,
    async_setup_entry,
)


class TestDebugRefreshButton:
    """Tests for the debug refresh button entity."""

    async def test_disabled_by_default(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
    ) -> None:
        """Test that the debug button is disabled by default."""
        button = SalahTimesDebugRefreshButton(
            coordinator=mock_coordinator,
            entry_id=mock_config_entry.entry_id,
            name=mock_config_entry.title,
        )
        assert button.entity_registry_enabled_default is False

    async def test_entity_category_diagnostic(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
    ) -> None:
        """Test that the debug button has DIAGNOSTIC entity category."""
        button = SalahTimesDebugRefreshButton(
            coordinator=mock_coordinator,
            entry_id=mock_config_entry.entry_id,
            name=mock_config_entry.title,
        )
        assert button.entity_category is EntityCategory.DIAGNOSTIC

    async def test_unique_id(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
    ) -> None:
        """Test that the debug button has a correct unique_id."""
        button = SalahTimesDebugRefreshButton(
            coordinator=mock_coordinator,
            entry_id=mock_config_entry.entry_id,
            name=mock_config_entry.title,
        )
        expected_uid = f"{mock_config_entry.entry_id}-refresh"
        assert button.unique_id == expected_uid

    async def test_async_press_calls_coordinator_refresh(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
    ) -> None:
        """Test that pressing the button triggers a coordinator refresh."""
        button = SalahTimesDebugRefreshButton(
            coordinator=mock_coordinator,
            entry_id=mock_config_entry.entry_id,
            name=mock_config_entry.title,
        )

        # Replace the real async_request_refresh with a mock
        mock_coordinator.async_request_refresh = AsyncMock()

        await button.async_press()

        mock_coordinator.async_request_refresh.assert_awaited_once()

    async def test_async_press_triggers_api_call(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
        mock_aladhan_client: AsyncMock,
    ) -> None:
        """End-to-end test: pressing the button results in the API being called.

        This tests that ``async_press()`` → ``async_request_refresh()`` →
        ``_async_update_data()`` → ``api.async_get_timings()`` actually fires
        on the underlying HTTP client.
        """
        mock_aladhan_client.async_get_timings.reset_mock()

        button = SalahTimesDebugRefreshButton(
            coordinator=mock_coordinator,
            entry_id=mock_config_entry.entry_id,
            name=mock_config_entry.title,
        )

        await button.async_press()

        mock_aladhan_client.async_get_timings.assert_awaited()

        # ``async_press`` → ``async_request_refresh`` schedules a
        # debouncer timer in the event loop.  Cancel it so the
        # framework's lingering-timer check stays happy.
        if getattr(mock_coordinator, "_debouncer", None) is not None:
            await mock_coordinator._debouncer.async_cancel()

    async def test_entity_description(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
    ) -> None:
        """Test that the button uses the correct entity description."""
        button = SalahTimesDebugRefreshButton(
            coordinator=mock_coordinator,
            entry_id=mock_config_entry.entry_id,
            name=mock_config_entry.title,
        )
        assert button.entity_description is DEBUG_REFRESH_DESCRIPTION
        assert button.entity_description.key == "refresh"
        assert button.entity_description.translation_key == "refresh"

    async def test_entity_registry(
        self,
        hass: HomeAssistant,
        mock_coordinator,
        mock_config_entry,
    ) -> None:
        """Test that async_setup_entry creates the button with correct unique_id."""
        mock_config_entry.runtime_data = mock_coordinator

        async_add_entities = AsyncMock()
        await async_setup_entry(hass, mock_config_entry, async_add_entities)

        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 1

        button = entities[0]
        expected_uid = f"{mock_config_entry.entry_id}-refresh"
        assert button.unique_id == expected_uid
        assert button.entity_registry_enabled_default is False
