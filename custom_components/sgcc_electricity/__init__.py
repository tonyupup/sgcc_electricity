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
from homeassistant.core import callback
from homeassistant.const import CONF_NAME, CONF_HOST
from .const import DOMAIN


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
                "sensor",
            ],
        )
    )
    return True
