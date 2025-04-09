"""Integration for SGCC (State Grid Corporation of China)."""

from __future__ import annotations
import logging
from typing import Any
from homeassistant import config_entries, core
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.const import CONF_NAME, CONF_HOST, Platform
from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Forward the setup to the sensor platform.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(
            entry,
            [
                Platform.SENSOR,
            ],
        )
    )
    return True


# Example migration function
async def async_migrate_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        new_data = {**config_entry.data}
        if config_entry.minor_version < 2:
            # TODO: modify Config Entry data with changes in version 1.2
            pass
        if config_entry.minor_version < 3:
            # TODO: modify Config Entry data with changes in version 1.3
            pass

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, minor_version=3, version=1
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    # Remove the entry from the data store
    hass.data[DOMAIN].pop(entry.entry_id, None)
    # Unload the platforms associated with this entry
    # This will call the unload method of each platform
    return await hass.config_entries.async_unload_platforms(entry, Platform.SENSOR)


# async def async_remove_config_entry_device(
#     hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry, device_entry: DeviceEntry
# ) -> bool:
