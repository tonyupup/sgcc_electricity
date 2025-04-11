from enum import Enum

# 国网电力官网
LOGIN_URL = "https://www.95598.cn/osgweb/login"
ELECTRIC_USAGE_URL = "https://www.95598.cn/osgweb/electricityCharge"
BALANCE_URL = "https://www.95598.cn/osgweb/userAcc"


# Home Assistant
SUPERVISOR_URL = "http://supervisor/core"
API_PATH = "/api/states/"  # https://developers.home-assistant.io/docs/api/rest/

BALANCE_SENSOR_NAME = "sensor.electricity_charge_balance"
DAILY_USAGE_SENSOR_NAME = "sensor.last_electricity_usage"
YEARLY_USAGE_SENSOR_NAME = "sensor.yearly_electricity_usage"
YEARLY_CHARGE_SENSOR_NAME = "sensor.yearly_electricity_charge"
MONTH_USAGE_SENSOR_NAME = "sensor.month_electricity_usage"
MONTH_CHARGE_SENSOR_NAME = "sensor.month_electricity_charge"
BALANCE_UNIT = "CNY"
USAGE_UNIT = "kWh"


# mqtt message
SGCC_DEVICE_MSG = {
    "identifiers": [
        "sgcc_{user_id}",
    ],
    "name": "国家电网",
    "manufacturer": "95598.cn",
    "serial_number": "{user_id}",
}

# 实时余额
CURRENT_BALANCE_CONFIG_TOPIC = (
    "homeassistant/sensor/sgcc_current_electricity_balance/config"
)
CURRENT_BALANCE_MSG = {
    "name": "当前电费余额",
    "unique_id": "sgcc_current_electricity_balance_{user_id}",
    "device_class": "monetary",
    "state_class": "measurement",
    "state_topic": "homeassistant/sensor/sgcc_current_electricity_balance_{user_id}/state",
    "unit_of_measurement": "CNY",
    "icon": "mdi:currency-cny",
    "json_attributes_topic": "homeassistant/sensor/sgcc_current_electricity_balance_{user_id}/attr",
    "json_attributes_template": "{{ value }}",
    "value_template": "{{ float(value) }}",
}


# 昨日用电量
LASTDAILY_USAGE_CONFIG_TOPIC = (
    "homeassistant/sensor/sgcc_daily_electricity_usage/config"
)
LASTDAILY_USAGE_MSG = {
    "name": "昨日用电量",
    "unique_id": "sgcc_daily_electricity_usage_{user_id}",
    "device_class": "energy",
    "state_class": "total_increasing",
    "state_topic": "homeassistant/sensor/sgcc_daily_electricity_usage_{user_id}/state",
    "unit_of_measurement": "kWh",
    "icon": "mdi:flash",
    "json_attributes_topic": "homeassistant/sensor/sgcc_daily_electricity_usage_{user_id}/attr",
    "json_attributes_template": "{{ value }}",
    "value_template": "{{ float(value) }}",
}

# 昨日电费
LASTDAILY_CHARGE_CONFIG_TOPIC = (
    "homeassistant/sensor/sgcc_daily_electricity_charge/config"
)
LASTDAILY_CHARGE_MSG = {
    "name": "昨日电费",
    "unique_id": "sgcc_daily_electricity_charge_{user_id}",
    "device_class": "monetary",
    "state_class": "measurement",
    "state_topic": "homeassistant/sensor/sgcc_daily_electricity_charge_{user_id}/state",
    "unit_of_measurement": "CNY",
    "icon": "mdi:currency-cny",
    "json_attributes_topic": "homeassistant/sensor/sgcc_daily_electricity_charge_{user_id}/attr",
    "json_attributes_template": "{{ value }}",
    "value_template": "{{ float(value) }}",
}

# 当月用电量
MONTH_USAGE_CONFIG_TOPIC = "homeassistant/sensor/sgcc_month_electricity_usage/config"
MONTH_USAGE_MSG = {
    "name": "当月用电量",
    "unique_id": "sgcc_month_electricity_usage_{user_id}",
    "device_class": "energy",
    "state_class": "total_increasing",
    "state_topic": "homeassistant/sensor/sgcc_month_electricity_usage_{user_id}/state",
    "unit_of_measurement": "kWh",
    "icon": "mdi:flash",
    "json_attributes_topic": "homeassistant/sensor/sgcc_month_electricity_usage_{user_id}/attr",
    "json_attributes_template": "{{ value }}",
    "value_template": "{{ float(value) }}",
}
# 当月电费
MONTH_CHARGE_CONFIG_TOPIC = "homeassistant/sensor/sgcc_month_electricity_charge/config"
MONTH_CHARGE_MSG = {
    "name": "当月电费",
    "unique_id": "sgcc_month_electricity_charge_{user_id}",
    "device_class": "monetary",
    "state_class": "measurement",
    "state_topic": "homeassistant/sensor/sgcc_month_electricity_charge_{user_id}/state",
    "unit_of_measurement": "CNY",
    "icon": "mdi:currency-cny",
    "json_attributes_topic": "homeassistant/sensor/sgcc_month_electricity_charge_{user_id}/attr",
    "json_attributes_template": "{{ value }}",
    "value_template": "{{ float(value) }}",
}
# 当年用电量
YEARLY_USAGE_CONFIG_TOPIC = "homeassistant/sensor/sgcc_yearly_electricity_usage/config"
YEARLY_USAGE_MSG = {
    "name": "当年用电量",
    "unique_id": "sgcc_yearly_electricity_usage_{user_id}",
    "device_class": "energy",
    "state_class": "total_increasing",
    "state_topic": "homeassistant/sensor/sgcc_yearly_electricity_usage_{user_id}/state",
    "unit_of_measurement": "kWh",
    "icon": "mdi:flash",
    "json_attributes_topic": "homeassistant/sensor/sgcc_yearly_electricity_usage_{user_id}/attr",
    "json_attributes_template": "{{ value }}",
    "value_template": "{{ float(value) }}",
}
# 当年电费
YEARLY_CHARGE_CONFIG_TOPIC = (
    "homeassistant/sensor/sgcc_yearly_electricity_charge/config"
)
YEARLY_CHARGE_MSG = {
    "name": "当年电费",
    "unique_id": "sgcc_yearly_electricity_charge_{user_id}",
    "device_class": "monetary",
    "state_class": "measurement",
    "state_topic": "homeassistant/sensor/sgcc_yearly_electricity_charge_{user_id}/state",
    "unit_of_measurement": "CNY",
    "icon": "mdi:currency-cny",
    "json_attributes_topic": "homeassistant/sensor/sgcc_yearly_electricity_charge_{user_id}/attr",
    "json_attributes_template": "{{ value }}",
    "value_template": "{{ float(value) }}",
}


class MQTT_MsgEnum(Enum):
    CURRENT_BALANCE_MSG = (CURRENT_BALANCE_MSG, CURRENT_BALANCE_CONFIG_TOPIC)
    LASTDAILY_USAGE_MSG = (LASTDAILY_USAGE_MSG, LASTDAILY_USAGE_CONFIG_TOPIC)
    LASTDAILY_CHARGE_MSG = (LASTDAILY_CHARGE_MSG, LASTDAILY_CHARGE_CONFIG_TOPIC)
    MONTH_USAGE_MSG = (MONTH_USAGE_MSG, MONTH_USAGE_CONFIG_TOPIC)
    MONTH_CHARGE_MSG = (MONTH_CHARGE_MSG, MONTH_CHARGE_CONFIG_TOPIC)
    YEARLY_USAGE_MSG = (YEARLY_USAGE_MSG, YEARLY_USAGE_CONFIG_TOPIC)
    YEARLY_CHARGE_MSG = (YEARLY_CHARGE_MSG, YEARLY_CHARGE_CONFIG_TOPIC)


def get_message(msg_type: MQTT_MsgEnum, user_id: str):
    device_msg = SGCC_DEVICE_MSG.copy()
    device_msg["identifiers"][0] = device_msg["identifiers"][0].format(user_id=user_id)
    device_msg["serial_number"] = user_id

    config_msg = msg_type.value[0].copy()
    config_topic = msg_type.value[1]

    config_msg["device"] = device_msg
    config_msg["name"] = config_msg["name"] + f"_{user_id}"
    config_msg["unique_id"] = config_msg["unique_id"].format(user_id=user_id)
    config_msg["state_topic"] = config_msg["state_topic"].format(user_id=user_id)
    config_msg["json_attributes_topic"] = config_msg["json_attributes_topic"].format(
        user_id=user_id
    )

    return (
        config_topic,
        config_msg,
        config_msg["state_topic"],
        config_msg["json_attributes_topic"],
    )
