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
    discovery_flow,
    selector,
)

from .const import (
    DOMAIN,
    HEADLESS_MODE,
    REMOTE_WEBDRIVER,
    SGCC_PASSWORD,
    SGCC_USERNAME,
    SGCC_USERID,
)


_LOGGER = logging.getLogger(__name__)


class SGCCElectricityConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SGCC Electricity."""

    VERSION = 1

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
                        type=selector.TextSelectorType.TEXT,
                    ),
                ),
                vol.Required(REMOTE_WEBDRIVER): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.URL,
                        autocomplete="webdriver_url",
                    ),
                ),
                vol.Optional(HEADLESS_MODE, default=True): bool,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_config)
