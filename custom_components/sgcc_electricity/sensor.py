"""sgcc sensor."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
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

_LOGGER = logging.getLogger(__name__)


class SGCCDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching SGCC data API."""

    # single instance of the coordinator
    _instance = None

    def __new__(cls, *args, **kwargs):
        """Ensure a single instance of the SGCCDataUpdateCoordinator."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize global SGCC data updater."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=5),
        )
        self.data = None

    @staticmethod
    def fetch_by_selenium(data: dict) -> dict:
        """Fetch data using Selenium.

        Returns
        -------
        dict
            A dictionary containing fetched data with keys such as balance, last_daily_date,
            last_daily_usage, yearly_charge, yearly_usage, month_charge, and month_usage.
        """
        from .src.data_fetcher import DataFetcher

        with DataFetcher(
            _LOGGER,
            data.get(SGCC_USERNAME),
            data.get(SGCC_PASSWORD),
            {
                "SCAN_QR_CODE": data.get(SCAN_QR_CODE, False),
                "REMOTE_DRIVER": data.get(REMOTE_WEBDRIVER),
                "HEADLESS_MODE": data.get(HEADLESS_MODE, True),
            },
        ) as fetch:
            results = fetch.fetch()
            if not results:
                return None
            return {
                result[0]: {
                    "balance": result[1],
                    "last_daily_date": result[2],
                    "last_daily_usage": result[3],
                    "yearly_charge": result[4],
                    "yearly_usage": result[5],
                    "month_charge": result[6],
                    "month_usage": result[7],
                }
                for result in results
            }

    async def _async_update_data(self) -> dict:
        """Fetch data from SGCC API."""
        if self.data is not None:
            return self.data
        self.data = await self.hass.async_add_executor_job(
            self.fetch_by_selenium,
            self.config_entry.data,
        )
        return self.data


class SGCCSensor(CoordinatorEntity, SensorEntity):
    """Representation of a SGCC sensor."""

    def __init__(
        self,
        coordinator: CoordinatorEntity,
        hass: HomeAssistant,
        user_id: str,
        entity_description: SensorEntityDescription,
        updater: Callable[[SGCCSensor, dict], None],
        context=None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, context)
        self.entity_description = entity_description
        self._user_id = user_id
        self._attr_unique_id = self.entity_id = generate_entity_id(
            "sensor.{}", f"{user_id}_{self.entity_description.name}", hass=hass
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, user_id)},
            manufacturer="SGCC",
            model="SGCC",
            name="SGCC",
            sw_version="0.1",
            configuration_url="https://www.sgcc.com.cn/",
            suggested_area="SGCC",
        )

        self._updater = updater

    @callback
    def _handle_coordinator_update(self):
        if not self.coordinator.data:
            return
        self._updater(self, self.coordinator.data.get(self._user_id))
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up SGCC sensor from a config entry."""

    def update_lastday_elec_sensor(sensor: SGCCSensor, data: dict):
        setattr(
            sensor,
            "_attr_last_reset",
            datetime.strptime(data["last_daily_date"], "%Y-%m-%d"),
        )
        setattr(sensor, "_attr_native_value", data["last_daily_usage"])

    def update_native_value_wrap(key: str):
        def update_native_value(sensor: SGCCSensor, data: dict):
            setattr(sensor, "_attr_native_value", float(data[key]))

        return update_native_value

    updater_coordinator = SGCCDataUpdateCoordinator(hass, entry)
    await updater_coordinator.async_config_entry_first_refresh()

    async_add_entities(
        [
            SGCCSensor(
                coordinator=updater_coordinator,
                hass=hass,
                user_id=user_id,
                entity_description=entity_description,
                updater=updater,
            )
            for entity_description, updater in [
                (
                    SensorEntityDescription(
                        key="sgcc_current_balance",
                        name="Current Balance",
                        icon="mdi:currency-cny",
                        unit_of_measurement="CNY",
                        state_class=SensorStateClass.TOTAL,
                        device_class=SensorDeviceClass.MONETARY,
                        native_unit_of_measurement="CNY",
                    ),
                    update_native_value_wrap("balance"),
                ),
                (
                    SensorEntityDescription(
                        key="sgcc_lastday_energy",
                        name="Last Day Energy",
                        icon="mdi:flash",
                        state_class=SensorStateClass.TOTAL,
                        device_class=SensorDeviceClass.ENERGY,
                        unit_of_measurement="kWh",
                        native_unit_of_measurement="kWh",
                    ),
                    update_lastday_elec_sensor,
                ),
                (
                    SensorEntityDescription(
                        key="sgcc_yearly_energy",
                        name="Yearly Energy",
                        icon="mdi:flash",
                        state_class=SensorStateClass.TOTAL,
                        device_class=SensorDeviceClass.ENERGY,
                        unit_of_measurement="kWh",
                        native_unit_of_measurement="kWh",
                    ),
                    update_native_value_wrap("yearly_usage"),
                ),
                (
                    SensorEntityDescription(
                        key="sgcc_monthly_energy",
                        name="Monthly Energy",
                        icon="mdi:flash",
                        state_class=SensorStateClass.TOTAL,
                        device_class=SensorDeviceClass.ENERGY,
                        unit_of_measurement="kWh",
                        native_unit_of_measurement="kWh",
                    ),
                    update_native_value_wrap("month_usage"),
                ),
                (
                    SensorEntityDescription(
                        key="sgcc_yearly_charge",
                        name="Yearly Charge",
                        icon="mdi:currency-cny",
                        state_class=SensorStateClass.TOTAL,
                        device_class=SensorDeviceClass.MONETARY,
                        unit_of_measurement="CNY",
                        native_unit_of_measurement="CNY",
                    ),
                    update_native_value_wrap("yearly_charge"),
                ),
                (
                    SensorEntityDescription(
                        key="sgcc_monthly_charge",
                        name="Monthly Charge",
                        icon="mdi:currency-cny",
                        state_class=SensorStateClass.TOTAL,
                        device_class=SensorDeviceClass.MONETARY,
                        unit_of_measurement="CNY",
                        native_unit_of_measurement="CNY",
                    ),
                    update_native_value_wrap("month_charge"),
                ),
            ]
            for user_id in updater_coordinator.data
            if entry.data.get(SGCC_USERID) is None
            or user_id in entry.data.get(SGCC_USERID, [])
        ]
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    await hass.config_entries.async_unload(entry.entry_id)

    await hass.config_entries.async_remove(entry.entry_id)
    return True
