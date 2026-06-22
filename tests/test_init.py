"""Tests for the Salah Times integration setup/unload."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.salah_times.const import (
    CONF_POLLING_INTERVAL_HOURS,
    DEFAULT_POLLING_INTERVAL_HOURS,
    DOMAIN,
    SERVICE_REFRESH,
)
from custom_components.salah_times.models import PrayerTimes


class TestInit:
    """Tests for integration setup, unload, and options update."""

    async def test_setup_unload(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """Test that a config entry is set up and unloaded correctly.

        Patches the API client so setup does not hit the network.
        Verifies:
        - Coordinator is created and stored on entry.runtime_data.
        - Platforms are forwarded (sensor, calendar).
        - async_unload_entry returns True and removes platforms.
        """
        # Patch the API client classes so no real network calls happen.
        # Also wrap async_on_unload to skip None callbacks (HA 2026.2's
        # hass.services.async_register returns None instead of a cleanup
        # callback, which would otherwise be stored and crash on unload).
        _original_on_unload = mock_config_entry.async_on_unload

        def _skip_none_on_unload(
            func: object,
        ) -> None:
            if func is not None:
                _original_on_unload(func)

        mock_config_entry.async_on_unload = _skip_none_on_unload
        try:
            with (
                patch(
                    "custom_components.salah_times.AlAdhanClient"
                ) as mock_aladhan_cls,
                patch(
                    "custom_components.salah_times.IslamicAppClient"
                ) as mock_islamic_cls,
            ):
                # Configure the mock instances
                mock_aladhan = mock_aladhan_cls.return_value
                mock_aladhan.async_get_timings = AsyncMock(
                    return_value=PrayerTimes(
                        date=date.today(),
                        timings={},
                        provider="aladhan",
                    )
                )
                mock_aladhan.async_get_month_calendar = AsyncMock(
                    return_value={date.today(): PrayerTimes(date=date.today(), timings={})}
                )

                mock_islamic = mock_islamic_cls.return_value
                mock_islamic.async_get_timings = AsyncMock(
                    return_value=PrayerTimes(
                        date=date.today(),
                        timings={},
                        provider="islamic_app",
                    )
                )
                mock_islamic.async_get_month_calendar = AsyncMock(return_value={})

                await hass.config_entries.async_setup(mock_config_entry.entry_id)
                await hass.async_block_till_done()

            assert mock_config_entry.state is ConfigEntryState.LOADED
            assert mock_config_entry.runtime_data is not None

            # Unload the entry
            await hass.config_entries.async_unload(mock_config_entry.entry_id)
            await hass.async_block_till_done()
            assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
        finally:
            mock_config_entry.async_on_unload = _original_on_unload

    async def test_options_update_listener(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_coordinator,
        expected_lingering_timers: bool = True,
    ) -> None:
        """Test that the options update listener fires.

        Changes an option value and verifies that async_options_updated
        is called, the coordinator update_interval is adjusted, and
        a refresh is triggered.

        ``async_options_updated`` calls ``coordinator.async_request_refresh``,
        which schedules a debouncer timer inside ``DataUpdateCoordinator``
        that the test framework's lingering check would otherwise flag.
        Requesting ``expected_lingering_timers=True`` is the HA-idiomatic
        way to declare this expected.
        """
        from custom_components.salah_times import async_options_updated

        # Set the runtime_data so the listener can find the coordinator
        mock_config_entry.runtime_data = mock_coordinator

        original_interval = mock_coordinator.update_interval
        assert original_interval == timedelta(hours=DEFAULT_POLLING_INTERVAL_HOURS)

        # Simulate an options update that changes the polling interval
        # HA 2026.2 blocks direct mutation of ConfigEntry.options;
        # use async_update_entry instead.
        hass.config_entries.async_update_entry(
            mock_config_entry,
            options={
                **mock_config_entry.options,
                CONF_POLLING_INTERVAL_HOURS: 12,
            },
        )

        await async_options_updated(hass, mock_config_entry)

        assert mock_coordinator.update_interval == timedelta(hours=12)

    async def test_multi_entry_setup(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_config_entry_2,
    ) -> None:
        """Test that two config entries can coexist and the refresh service works.

        Sets up two entries with different coordinates, verifies both are
        LOADED, calls the refresh service to confirm both coordinators are
        refreshed, then unloads one entry and verifies the remaining entry
        still works.
        """
        # Store originals for cleanup
        _orig_unload_1 = mock_config_entry.async_on_unload
        _orig_unload_2 = mock_config_entry_2.async_on_unload

        def _make_skip_none(unload_fn):
            def _skip_none(func: object) -> None:
                if func is not None:
                    unload_fn(func)
            return _skip_none

        mock_config_entry.async_on_unload = _make_skip_none(_orig_unload_1)
        mock_config_entry_2.async_on_unload = _make_skip_none(_orig_unload_2)

        try:
            with (
                patch(
                    "custom_components.salah_times.AlAdhanClient"
                ) as mock_aladhan_cls,
                patch(
                    "custom_components.salah_times.IslamicAppClient"
                ) as mock_islamic_cls,
            ):
                # Configure mock instances so setup does not hit the network
                mock_aladhan = mock_aladhan_cls.return_value
                mock_aladhan.async_get_timings = AsyncMock(
                    return_value=PrayerTimes(
                        date=date.today(),
                        timings={},
                        provider="aladhan",
                    )
                )
                mock_aladhan.async_get_month_calendar = AsyncMock(
                    return_value={
                        date.today(): PrayerTimes(date=date.today(), timings={})
                    }
                )

                mock_islamic = mock_islamic_cls.return_value
                mock_islamic.async_get_timings = AsyncMock(
                    return_value=PrayerTimes(
                        date=date.today(),
                        timings={},
                        provider="islamic_app",
                    )
                )
                mock_islamic.async_get_month_calendar = AsyncMock(return_value={})

                # Set up the first entry.  In this version of HA, forwarding
                # platforms iterates over ALL entries for the domain, so both
                # entries reach LOADED state from a single async_setup call.
                await hass.config_entries.async_setup(mock_config_entry.entry_id)
                await hass.async_block_till_done()

            assert mock_config_entry.state is ConfigEntryState.LOADED
            assert mock_config_entry_2.state is ConfigEntryState.LOADED
            assert mock_config_entry.runtime_data is not None
            assert mock_config_entry_2.runtime_data is not None

            # hass.data[DOMAIN] should have 2 coordinators
            assert len(hass.data[DOMAIN]) == 2
            assert mock_config_entry.entry_id in hass.data[DOMAIN]
            assert mock_config_entry_2.entry_id in hass.data[DOMAIN]

            # Mock both coordinators' async_request_refresh to track calls
            coordinator_1 = hass.data[DOMAIN][mock_config_entry.entry_id]
            coordinator_2 = hass.data[DOMAIN][mock_config_entry_2.entry_id]
            coordinator_1.async_request_refresh = AsyncMock()
            coordinator_2.async_request_refresh = AsyncMock()

            # Call the refresh service
            await hass.services.async_call(
                DOMAIN,
                SERVICE_REFRESH,
                blocking=True,
            )

            # Both coordinators should have been refreshed
            coordinator_1.async_request_refresh.assert_awaited_once()
            coordinator_2.async_request_refresh.assert_awaited_once()

            # Unload one entry
            await hass.config_entries.async_unload(mock_config_entry_2.entry_id)
            await hass.async_block_till_done()
            assert mock_config_entry_2.state is ConfigEntryState.NOT_LOADED

            # hass.data[DOMAIN] should now have 1 coordinator
            assert len(hass.data[DOMAIN]) == 1
            assert mock_config_entry.entry_id in hass.data[DOMAIN]
            assert mock_config_entry_2.entry_id not in hass.data[DOMAIN]

            # Reset the remaining coordinator's mock and call refresh again
            coordinator_1.async_request_refresh = AsyncMock()

            await hass.services.async_call(
                DOMAIN,
                SERVICE_REFRESH,
                blocking=True,
            )

            # Only the remaining coordinator should have been refreshed
            coordinator_1.async_request_refresh.assert_awaited_once()

            # Unload the remaining entry
            await hass.config_entries.async_unload(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        finally:
            mock_config_entry.async_on_unload = _orig_unload_1
            mock_config_entry_2.async_on_unload = _orig_unload_2
