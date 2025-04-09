"""Config flow for SGCC Electricity integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    selector,
)

from .const import (
    DOMAIN,
    SGCC_USERID,
    SGCC_USERNAME,
    SGCC_PASSWORD,
    REMOTE_WEBDRIVER,
    HEADLESS_MODE,
    SCAN_QR_CODE,
)


class SGCCElectricityConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SGCC Electricity."""

    VERSION = 1

    data_schema = vol.Schema(
        {
            vol.Required(SGCC_USERNAME): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                    autocomplete="username",
                ),
            ),
            vol.Required(SGCC_PASSWORD): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.PASSWORD,
                    autocomplete="current-password",
                ),
            ),
            vol.Optional(SGCC_USERID): selector.TextSelector(
                selector.TextSelectorConfig(
                    multiple=True,
                    type=selector.TextSelectorType.NUMBER,
                ),
            ),
            vol.Required(REMOTE_WEBDRIVER): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.URL,
                    autocomplete="webdriver_url",
                ),
            ),
            vol.Optional(HEADLESS_MODE, default=True): cv.boolean,
            vol.Optional(SCAN_QR_CODE, default=False): cv.boolean,
        }
    )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[SGCC_USERNAME]}")
            return self.async_create_entry(
                title=f"SGCC Electricity for {user_input[SGCC_USERNAME]}",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user", data_schema=self.data_schema, errors=errors
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Handle the reconfiguration step.

        Parameters
        ----------
        user_input : dict[str, Any] | None
            The user input provided during the reconfiguration step.

        Returns
        -------
        FlowResult
            The result of the reconfiguration step.
        """
        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[SGCC_USERNAME]}")
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data_updates=user_input,
                unique_id=f"{user_input[SGCC_USERNAME]}",
                title=f"SGCC Electricity for {user_input[SGCC_USERNAME]}",
            )

        return self.async_show_form(step_id="reconfigure", data_schema=self.data_schema)
