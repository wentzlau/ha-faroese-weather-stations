"""Platform for sensor integration."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
import re

import aiohttp
import async_timeout

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from homeassistant.components import sensor
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE,
    TEMP_FAHRENHEIT, TEMP_CELSIUS, LENGTH_INCHES,
    LENGTH_FEET, LENGTH_MILLIMETERS, LENGTH_METERS, SPEED_MILES_PER_HOUR, SPEED_KILOMETERS_PER_HOUR,
    PERCENTAGE, PRESSURE_INHG, PRESSURE_MBAR, PRECIPITATION_INCHES_PER_HOUR, PRECIPITATION_MILLIMETERS_PER_HOUR,
    ATTR_ATTRIBUTION)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv
from homeassistant.util.unit_system import METRIC_SYSTEM

import voluptuous as vol
import xml.etree.ElementTree as ET

_LOGGER = logging.getLogger("foweather")

CONF_STATIONS = "stations"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)
CONF_ATTRIBUTION = "Data provided by the Landverk (lv.fo)"
TEMPUNIT = 0
LENGTHUNIT = 1
ALTITUDEUNIT = 2
SPEEDUNIT = 3
PRESSUREUNIT = 4
RATE = 5
PERCENTAGEUNIT = 6


class WeatherSensorConfig:
    """Sensor Configuration.
    defines basic HA properties of the weather sensor and
    stores callbacks that can parse sensor values out of
    the json data received by WU API.
    """

    def __init__(self, friendly_name, feature, value,
                 unit_of_measurement=None, entity_picture=None,
                 icon="mdi:gauge", device_state_attributes=None,
                 device_class=None):
        """Constructor.
        Args:
            friendly_name (string|func): Friendly name
            feature (string): WU feature. See:
                https://docs.google.com/document/d/1eKCnKXI9xnoMGRRzOL1xPCBihNV2rOet08qpE_gArAY/edit
            value (function(WUndergroundData)): callback that
                extracts desired value from WUndergroundData object
            unit_of_measurement (string): unit of measurement
            entity_picture (string): value or callback returning
                URL of entity picture
            icon (string): icon name
            device_state_attributes (dict): dictionary of attributes,
                or callable that returns it
        """
        self.friendly_name = friendly_name
        self.unit_of_measurement = unit_of_measurement
        self.feature = feature
        self.value = value
        self.entity_picture = entity_picture
        self.icon = icon
        self.device_state_attributes = device_state_attributes or {}
        self.device_class = device_class


class WeatherCurrentConditionsSensorConfig(WeatherSensorConfig):
    """Helper for defining sensor configurations for current conditions."""

    def __init__(self, friendly_name, source, station_id, field , icon="mdi:gauge",
                 unit_of_measurement=None, device_class=None):
        """Constructor.
        Args:
            friendly_name (string|func): Friendly name of sensor
            field (string): Field name in the "observations[0][unit_system]"
                            dictionary.
            icon (string): icon name , if None sensor
                           will use current weather symbol
            unit_of_measurement (string): unit of measurement
        """
        super().__init__(
            friendly_name,
            "conditions",
            value=lambda wu: wu.data[field],
            icon=icon,
            unit_of_measurement= unit_of_measurement,
            device_state_attributes={
                'date': lambda wu: wu.data['time']
            },
            device_class=device_class
        )



# SENSOR_TYPES = {
#     # current
#     'obsTimeLocal': WeatherSensorConfig(
#         'Local Observation Time', 'observations',
#         value=lambda wu: wu.data['time'],
#         icon="mdi:clock"),
#     'humidity': WeatherSensorConfig(
#         'Relative Humidity', 'observations',
#         value=lambda wu: wu.data['hum'],
#         unit_of_measurement='%',
#         icon="mdi:water-percent",
#         device_class="humidity"),
#     'winddir': WeatherSensorConfig(
#         'Wind Direction', 'observations',
#         value=lambda wu: wu.data['dir'],
#         unit_of_measurement='\u00b0',
#         icon="mdi:weather-windy"),
#     'windDirectionName': WeatherSensorConfig(
#         'Wind Direction', 'observations',
#         value=lambda wu: wind_direction_to_friendly_name(wu.data['dir']),
#         unit_of_measurement='',
#         icon="mdi:weather-windy"),
#     'dewpt': WeatherCurrentConditionsSensorConfig(
#         'Dewpoint', 'dew', 'mdi:water', TEMPUNIT),
#     'pressure': WeatherCurrentConditionsSensorConfig(
#         'Pressure', 'press1', "mdi:gauge", PRESSUREUNIT,
#         device_class="pressure"),
#     'temp': WeatherCurrentConditionsSensorConfig(
#         'Temperature', 'temp2', "mdi:thermometer", TEMPUNIT,
#         device_class="temperature"),
#     'windGust': WeatherCurrentConditionsSensorConfig(
#         'Wind Gust', 'gust2', "mdi:weather-windy", SPEEDUNIT),
#     'windSpeed': WeatherCurrentConditionsSensorConfig(
#         'Wind Speed', 'mean1', "mdi:weather-windy", SPEEDUNIT),
#     'precipRate': WeatherCurrentConditionsSensorConfig(
#         'Precipitation Rate', 'rain', "mdi:umbrella", LENGTHUNIT),
#     'precipTotal': WeatherCurrentConditionsSensorConfig(
#         'Precipitation Today', 'rainsum', "mdi:umbrella", LENGTHUNIT),
    
# }

SENSOR_TYPES = {
    # current
    'humidity': {
        'name': 'Relative Humidity',
        'unit_of_measurement': '%',
        'icon': "mdi:water-percent",
        'device_class': "humidity"  
    },
    'winddir': {
        'name': 'Wind Direction',
        'unit_of_measurement': '\u00b0',
        'icon':"mdi:weather-windy",
        'device_class': ""
    },
    'windDirectionName': {
        'name': 'Wind Direction',
        'unit_of_measurement': '',
        'icon': "mdi:weather-windy",
        'device_class': ""
    },
    'dewpt': {
        'name': 'Dew point',
        'icon': 'mdi:water',
        'unit_of_measurement': TEMPUNIT,
        'device_class': ""
    },
    'pressure': {
        'name': 'Pressure',
        'icon': "mdi:gauge",
        'unit_of_measurement': PRESSUREUNIT,
        'device_class': "pressure"
    },
    'temp':{
        'name': 'Temperature', 
        'icon': "mdi:thermometer",
        'unit_of_measurement': TEMPUNIT,
        'device_class': "temperature"
    },
    'windGust':{
        'name': 'Wind gust',
        'icon': "mdi:weather-windy",
        'unit_of_measurement': SPEEDUNIT,
        'device_class': ""
    },
    'windSpeed': {
        'name': 'Wind speed',
        'icon': "mdi:weather-windy",
        'unit_of_measurement': SPEEDUNIT,
        'device_class': ""
    },
    'precipRate':{
        'name':'Precipitation rate',
        'icon': "mdi:umbrella",
        'unit_of_measurement': LENGTHUNIT,
        'device_class': ""
    },
    'precipTotal': {
        'name': 'Precipitation today',
        'icon': "mdi:umbrella", 
        'unit_of_measurement': LENGTHUNIT,
        'device_class': ""
    }
    
}

def wind_direction_to_friendly_name(argument):
    if (argument < 0):
        return ""
    if 348.75 <= argument or 11.25 > argument:
        return "N"
    if 11.25 <= argument < 33.75:
        return "NNE"
    if 33.75 <= argument < 56.25:
        return "NE"
    if 56.25 <= argument < 78.75:
        return "ENE"
    if 78.75 <= argument < 101.25:
        return "E"
    if 101.25 <= argument < 123.75:
        return "ESE"
    if 123.75 <= argument < 146.25:
        return "SE"
    if 146.25 <= argument < 168.75:
        return "SSE"
    if 168.75 <= argument < 191.25:
        return "S"
    if 191.25 <= argument < 213.75:
        return "SSW"
    if 213.75 <= argument < 236.25:
        return "SW"
    if 236.25 <= argument < 258.75:
        return "WSW"
    if 258.75 <= argument < 281.25:
        return "W"
    if 281.25 <= argument < 303.75:
        return "WNW"
    if 303.75 <= argument < 326.25:
        return "NW"
    if 326.25 <= argument < 348.75:
        return "NNW"
    return ""

LV_STATIONS = {
    'lv_kambsdalur': { 'name': 'Kambsdalur', 'source': 'lv', 'station_id': 'F-10' },
    'lv_hogareyn': { 'name': 'Høgareyn', 'source': 'lv', 'station_id': 'F-12' },
    'lv_sund': { 'name': 'Sund', 'source': 'lv', 'station_id': 'F-21' },
    'lv_runavik': { 'name': 'Runavík', 'source': 'lv', 'station_id': 'F-22' },
    'lv_vatnsoyrar': { 'name': 'Vatnsoyrar', 'source': 'lv', 'station_id': 'F-23' },
    'lv_klaksvik': { 'name': 'Klaksvík', 'source': 'lv', 'station_id': 'F-24' },
    'lv_sandoy': { 'name': 'Sandoy,á Brekkuni Stóru', 'source': 'lv', 'station_id': 'F-25' },
    'lv_sydradalur': { 'name': 'Syðradalur', 'source': 'lv', 'station_id': 'F-26' },
    'lv_porkerishalsur': { 'name': 'Porkerishálsur', 'source': 'lv', 'station_id': 'F-27' },
    'lv_krambatangi': { 'name': 'Krambatangi', 'source': 'lv', 'station_id': 'F-28' },
    'lv_skopun': { 'name': 'Skopun', 'source': 'lv', 'station_id': 'F-29' },
    'lv_nordradalsskard': { 'name': 'Norðradalsskarð', 'source': 'lv', 'station_id': 'F-33' },
    'lv_tjornuvík': { 'name': 'Tjørnuvík', 'source': 'lv', 'station_id': 'F-35' },
    'lv_nordurisundum': { 'name': 'Norðuri í Sundum, Kollaf', 'source': 'lv', 'station_id': 'F-36' },
    'lv_nordskalatunnilin': { 'name': 'Norðskálatunnilin', 'source': 'lv', 'station_id': 'F-37' },
    'lv_kaldbaksbotnur': { 'name': 'Kaldbaksbotnur', 'source': 'lv', 'station_id': 'F-38' },
    'lv_gotueidi': { 'name': 'Gøtueiði', 'source': 'lv', 'station_id': 'F-39' },
    'lv_dalavegur': { 'name': 'Dalavegur til Viðareiðis', 'source': 'lv', 'station_id': 'F-40' },
    'lv_sandavagshalsi': { 'name': 'Á Sandavágshálsi', 'source': 'lv', 'station_id': 'F-41' },
    'lv_gjaarskard': { 'name': 'Gjáarskarð', 'source': 'lv', 'station_id': 'F-42' },
    'lv_heltnin': { 'name': 'Heltnin, Oyndarfjarðarvegurin', 'source': 'lv', 'station_id': 'F-43' },
    'lv_hvalba': { 'name': 'Hvalba', 'source': 'lv', 'station_id': 'F-44' },
    'lv_streymnes': { 'name': 'Streymnes', 'source': 'lv', 'station_id': 'F-45' },
    'lv_velbastadhals': { 'name': 'Við Velbastaðháls', 'source': 'lv', 'station_id': 'F-48' },
    'lv_ordaskard': { 'name': 'Ørðaskarð, Fámjinsvegur', 'source': 'lv', 'station_id': 'F-49' },
    
    
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATIONS): vol.All(cv.ensure_list, vol.Length(min=1), [vol.In(LV_STATIONS)])
})

async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):
    """Set up the WUnderground sensor."""
    
    if hass.config.units is METRIC_SYSTEM:
        unit_system_api = 'm'
        unit_system = 'metric'
    else:
        unit_system_api = 'e'
        unit_system = 'imperial'

    stations = config.get(CONF_STATIONS)
    _LOGGER.info("Weatherstations in config: %s", stations )
    print("stations", stations)
    sensors = []
    for station_id in stations:
        station = LV_STATIONS[station_id]
        _LOGGER.info("Start monitor station: %s", station['name'] )
        if station['source'] == 'lv':
            rest = LVWeatherData(hass, station['station_id'])
            await rest.async_update()
            unique_id_base = station_id
            sensors.append(WeatherSensor(hass, rest, 'temp', station['name'], 'lv', station['station_id'],'temp2', unique_id_base))
            sensors.append(WeatherSensor(hass, rest, 'pressure', station['name'], 'lv', station['station_id'],'press1', unique_id_base))
            sensors.append(WeatherSensor(hass, rest, 'windSpeed', station['name'], 'lv', station['station_id'],'mean1', unique_id_base))
            sensors.append(WeatherSensor(hass, rest, 'windGust', station['name'], 'lv', station['station_id'],'gust2', unique_id_base))
            sensors.append(WeatherSensor(hass, rest, 'precipRate', station['name'], 'lv', station['station_id'],'rain', unique_id_base))
            sensors.append(WeatherSensor(hass, rest, 'precipTotal', station['name'], 'lv', station['station_id'],'rainsum', unique_id_base))
            sensors.append(WeatherSensor(hass, rest, 'dewpt', station['name'], 'lv', station['station_id'],'dew', unique_id_base))
            sensors.append(WeatherSensor(hass, rest, 'winddir', station['name'], 'lv', station['station_id'],'dir', unique_id_base))
            sensors.append(WeatherSensor(hass, rest, 'humidity', station['name'], 'lv', station['station_id'],'hum', unique_id_base))

    async_add_entities(sensors, True)



class WeatherSensor(Entity):
    """Implementing the WUnderground sensor."""

    def __init__(self, hass: HomeAssistantType, rest, sensor_type, station_name, source, station_id, data_field, unique_id_base: str):
        """Initialize the sensor."""
        self.data_field = data_field
        self.rest = rest
        self.station_name = station_name
        self._sensor_type = sensor_type
        self.source = source
        self.station_id = station_id
        self._state = None
        self._attributes = {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        }
        self._icon = None
        self._entity_picture = None
        self._unit_of_measurement = self._cfg_expand("unit_of_measurement")
        # This is only the suggested entity id, it might get changed by
        # the entity registry later.
        self.entity_id = sensor.ENTITY_ID_FORMAT.format('fo_weather_' + source + '_' + station_id + '_' + sensor_type)
        self._unique_id = "{},{},{}".format(source,unique_id_base, sensor_type)
        self._device_class = self._cfg_expand("device_class")

    def _cfg_expand(self, what, default=None):
        """Parse and return sensor data."""
        sensor_info = SENSOR_TYPES[self._sensor_type]
        cfg = WeatherCurrentConditionsSensorConfig(
            sensor_info['name'] + " (" + self.station_name + ")",
            station_id = self.station_id,
            source = self.source,
            field= self.data_field,
            icon = sensor_info['icon'],
            unit_of_measurement=sensor_info['unit_of_measurement'],
            device_class= sensor_info['device_class']
        )
        #SENSOR_TYPES[self._condition]
        val = getattr(cfg, what)
        if not callable(val):
            return val
        try:
            val = val(self.rest)
        except (KeyError, IndexError, TypeError, ValueError) as err:
            _LOGGER.warning("Failed to expand cfg from WU API."
                            " Condition: %s Attr: %s Error: %s",
                            self._sensor_type, what, repr(err))
            val = default

        return val

    def _update_attrs(self):
        """Parse and update device state attributes."""
        attrs = self._cfg_expand("device_state_attributes", {})

        for (attr, callback) in attrs.items():
            if callable(callback):
                try:
                    self._attributes[attr] = callback(self.rest)
                except (KeyError, IndexError, TypeError, ValueError) as err:
                    _LOGGER.warning("Failed to update attrs from WU API."
                                    " Condition: %s Attr: %s Error: %s",
                                    self._sensor_type, attr, repr(err))
            else:
                self._attributes[attr] = callback

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._cfg_expand("friendly_name")

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Return icon."""
        return self._icon

    @property
    def entity_picture(self):
        """Return the entity picture."""
        return self._entity_picture

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the units of measurement."""
        return self._device_class

    async def async_update(self):
        """Update current conditions."""
        await self.rest.async_update()

        if not self.rest.data:
            # no data, return
            return

        self._state = self._cfg_expand("value")
        self._update_attrs()
        self._icon = self._cfg_expand("icon", super().icon)
        url = self._cfg_expand("entity_picture")
        if isinstance(url, str):
            self._entity_picture = re.sub(r'^http://', 'https://',
                                          url, flags=re.IGNORECASE)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

class LVWeatherData:
    """Get data from lv.fo"""
    def __init__(self, hass, lv_station):
        """Initialize the data object."""
        self._hass = hass
        self.lv_station = lv_station
        self._features = set()
        self.data = None
        self._session = async_get_clientsession(self._hass)
    

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from WUnderground."""
        headers = {'Accept-Encoding': 'gzip'}
        ns = {'ss':"urn:schemas-microsoft-com:office:spreadsheet", 'html':"http://www.w3.org/TR/REC-html40"}
        lv_url = "https://lv.fo/fr/excel.php"
        current_date = datetime.today()
        url = f"{lv_url}?station={self.lv_station}&year={current_date.year}&month={current_date.month}&day={current_date.day}"
        try:
            with async_timeout.timeout(10):
                weather_data = await self._session.get(url)
                if weather_data is None:
                    raise ValueError('NO CURRENT RESULT')
                                   
                
        except ValueError as err:
            _LOGGER.error("Check weather API %s", err.args)
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error fetching weather data: %s", repr(err))
        byte_data = bytearray()
        while not weather_data.content.at_eof():
            chunk = await weather_data.content.read(1024)
            byte_data += chunk   
        root = ET.fromstring(byte_data)
        work_sheet = root.find("ss:Worksheet", ns)
        table = work_sheet.find("ss:Table", ns)
        row_values = []
        for row in table.findall('ss:Row', ns):
            cell_values = []
            for cell in row.findall('ss:Cell', ns):
                value = cell.find("ss:Data", ns)
                value_type = value.attrib["{urn:schemas-microsoft-com:office:spreadsheet}Type"]
                if value_type == 'String':
                    cell_values.append(value.text)
                if value_type == 'Number':
                    cell_values.append(float(value.text))
            row_values.append(cell_values)

        idx = 0
        data = {}
        name_row = row_values[0]
        value_row = row_values[1]
        for cell in name_row:
            if not cell == 'undef':
                data[cell] = value_row[idx]
            idx += 1
        
        self.data = data
        