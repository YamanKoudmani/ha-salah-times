"""Config flow for the Salah Times integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    BooleanSelector,
    LocationSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CALCULATION_METHODS,
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
    DEFAULT_NAME,
    DEFAULT_POLLING_INTERVAL_HOURS,
    DEFAULT_SCHOOL,
    DOMAIN,
    LATITUDE_ADJUSTMENT_METHODS,
    SCHOOLS,
)


def _get_options_schema(
    hass: HomeAssistant,
    config_entry: ConfigEntry | None = None,
) -> vol.Schema:
    """Build the options flow schema.

    Returns a voluptuous schema with all configurable options.
    Defaults are pulled from the config entry options when available,
    otherwise from module-level defaults.
    """
    if config_entry is not None:
        calc_method = config_entry.options.get(
            CONF_CALCULATION_METHOD, DEFAULT_CALCULATION_METHOD
        )
        school = config_entry.options.get(CONF_SCHOOL, DEFAULT_SCHOOL)
        lat_adj = config_entry.options.get(
            CONF_LATITUDE_ADJUSTMENT_METHOD, DEFAULT_LATITUDE_ADJUSTMENT_METHOD
        )
        hijri_adj = config_entry.options.get(
            CONF_HIJRI_ADJUSTMENT_DAYS, DEFAULT_HIJRI_ADJUSTMENT_DAYS
        )
        poll_int = config_entry.options.get(
            CONF_POLLING_INTERVAL_HOURS, DEFAULT_POLLING_INTERVAL_HOURS
        )
        failover = config_entry.options.get(
            CONF_ENABLE_FAILOVER, DEFAULT_ENABLE_FAILOVER
        )
    else:
        calc_method = DEFAULT_CALCULATION_METHOD
        school = DEFAULT_SCHOOL
        lat_adj = DEFAULT_LATITUDE_ADJUSTMENT_METHOD
        hijri_adj = DEFAULT_HIJRI_ADJUSTMENT_DAYS
        poll_int = DEFAULT_POLLING_INTERVAL_HOURS
        failover = DEFAULT_ENABLE_FAILOVER

    return vol.Schema(
        {
            vol.Optional(
                CONF_CALCULATION_METHOD,
                default=calc_method,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": k, "label": v}
                        for k, v in CALCULATION_METHODS.items()
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_SCHOOL,
                default=school,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": k, "label": v}
                        for k, v in SCHOOLS.items()
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_LATITUDE_ADJUSTMENT_METHOD,
                default=lat_adj,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": k, "label": v}
                        for k, v in LATITUDE_ADJUSTMENT_METHODS.items()
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_HIJRI_ADJUSTMENT_DAYS,
                default=hijri_adj,
            ): NumberSelector(
                NumberSelectorConfig(
                    min=-2,
                    max=2,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_POLLING_INTERVAL_HOURS,
                default=poll_int,
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=24,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_ENABLE_FAILOVER,
                default=failover,
            ): BooleanSelector(),
        }
    )


class SalahTimesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Salah Times."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step.

        Collects name, latitude, and longitude.
        Sets unique ID from lat/lon (4 decimal places).
        Aborts if a config entry with that unique ID already exists.
        """
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_NAME, default=DEFAULT_NAME
                        ): TextSelector(),
                        vol.Required(
                            CONF_LATITUDE,
                            default={
                                "latitude": self.hass.config.latitude,
                                "longitude": self.hass.config.longitude,
                            },
                        ): LocationSelector(),
                    }
                ),
            )

        # Flatten LocationSelector output into separate lat/lon keys
        location = user_input.pop(CONF_LATITUDE, {})
        lat = location.get("latitude", 0.0)
        lon = location.get("longitude", 0.0)
        user_input[CONF_LATITUDE] = lat
        user_input[CONF_LONGITUDE] = lon

        errors: dict[str, str] = {}
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            errors["base"] = "invalid_coordinates"

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_NAME,
                            default=user_input.get(CONF_NAME, DEFAULT_NAME),
                        ): TextSelector(),
                        vol.Required(
                            CONF_LATITUDE,
                            default={"latitude": lat, "longitude": lon},
                        ): LocationSelector(),
                    }
                ),
                errors=errors,
            )

        unique_id = f"{lat:.4f}-{lon:.4f}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data={
                CONF_NAME: user_input[CONF_NAME],
                CONF_LATITUDE: lat,
                CONF_LONGITUDE: lon,
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure step for editing name/lat/lon.

        Allows changing location data without deleting the entry.
        """
        entry = self._get_reconfigure_entry()

        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_NAME,
                            default=entry.data.get(CONF_NAME, DEFAULT_NAME),
                        ): TextSelector(),
                        vol.Required(
                            CONF_LATITUDE,
                            default={
                                "latitude": entry.data.get(
                                    CONF_LATITUDE, self.hass.config.latitude
                                ),
                                "longitude": entry.data.get(
                                    CONF_LONGITUDE, self.hass.config.longitude
                                ),
                            },
                        ): LocationSelector(),
                    }
                ),
            )

        # Flatten LocationSelector output into separate lat/lon keys
        location = user_input.pop(CONF_LATITUDE, {})
        lat = location.get("latitude", 0.0)
        lon = location.get("longitude", 0.0)
        user_input[CONF_LATITUDE] = lat
        user_input[CONF_LONGITUDE] = lon

        errors: dict[str, str] = {}
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            errors["base"] = "invalid_coordinates"

        if errors:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_NAME,
                            default=user_input.get(CONF_NAME, DEFAULT_NAME),
                        ): TextSelector(),
                        vol.Required(
                            CONF_LATITUDE,
                            default={"latitude": lat, "longitude": lon},
                        ): LocationSelector(),
                    }
                ),
                errors=errors,
            )

        new_unique_id = f"{lat:.4f}-{lon:.4f}"
        if new_unique_id != entry.unique_id:
            await self.async_set_unique_id(new_unique_id)
            self._abort_if_unique_id_configured(reload_on_update=True)

        return self.async_update_reload_and_abort(
            entry,
            data_updates={
                CONF_NAME: user_input[CONF_NAME],
                CONF_LATITUDE: lat,
                CONF_LONGITUDE: lon,
            },
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow handler for this integration."""
        return SalahTimesOptionsFlow(config_entry)


class SalahTimesOptionsFlow(config_entries.OptionsFlow):
    """Handle the options flow for Salah Times."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Store a reference to the config entry.

        Args:
            config_entry: The config entry being configured.
        """
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Route to the options step."""
        return await self.async_step_options(user_input)

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options step.

        Collects calculation method, school, latitude adjustment method,
        hijri adjustment days, polling interval, and failover toggle.

        Writes to entry.options so changes don't require re-creating the entry.
        """
        if user_input is None:
            return self.async_show_form(
                step_id="options",
                data_schema=_get_options_schema(self.hass, self._config_entry),
            )

        return self.async_create_entry(title="", data=user_input)
