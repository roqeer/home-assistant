"""
homeassistant.components.influxdb
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
InfluxDB component which allows you to send data to an Influx database.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/influxdb/
"""
import logging
import homeassistant.util as util
from homeassistant.helpers import validate_config
from homeassistant.const import (EVENT_STATE_CHANGED, STATE_ON, STATE_OFF,
                                 STATE_UNLOCKED, STATE_LOCKED, STATE_UNKNOWN)
from homeassistant.components.sun import (STATE_ABOVE_HORIZON,
                                          STATE_BELOW_HORIZON)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "influxdb"
DEPENDENCIES = []

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8086
DEFAULT_DATABASE = 'home_assistant'
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = False

REQUIREMENTS = ['influxdb==2.12.0']

CONF_HOST = 'host'
CONF_PORT = 'port'
CONF_DB_NAME = 'database'
CONF_USERNAME = 'username'
CONF_PASSWORD = 'password'
CONF_SSL = 'ssl'
CONF_VERIFY_SSL = 'verify_ssl'


def setup(hass, config):
    """ Setup the InfluxDB component. """

    from influxdb import InfluxDBClient, exceptions

    if not validate_config(config, {DOMAIN: ['host']}, _LOGGER):
        return False

    conf = config[DOMAIN]

    host = conf[CONF_HOST]
    port = util.convert(conf.get(CONF_PORT), int, DEFAULT_PORT)
    database = util.convert(conf.get(CONF_DB_NAME), str, DEFAULT_DATABASE)
    username = util.convert(conf.get(CONF_USERNAME), str)
    password = util.convert(conf.get(CONF_PASSWORD), str)
    ssl = util.convert(conf.get(CONF_SSL), bool, DEFAULT_SSL)
    verify_ssl = util.convert(conf.get(CONF_VERIFY_SSL), bool,
                              DEFAULT_VERIFY_SSL)

    try:
        influx = InfluxDBClient(host=host, port=port, username=username,
                                password=password, database=database,
                                ssl=ssl, verify_ssl=verify_ssl)
        influx.query("select * from /.*/ LIMIT 1;")
    except exceptions.InfluxDBClientError as exc:
        _LOGGER.error("Database host is not accessible due to '%s', please "
                      "check your entries in the configuration file and that"
                      " the database exists and is READ/WRITE.", exc)
        return False

    def influx_event_listener(event):
        """ Listen for new messages on the bus and sends them to Influx. """

        state = event.data.get('new_state')
        if state is None or state.state in (STATE_UNKNOWN, ''):
            return

        if state.state in (STATE_ON, STATE_LOCKED, STATE_ABOVE_HORIZON):
            _state = 1
        elif state.state in (STATE_OFF, STATE_UNLOCKED, STATE_BELOW_HORIZON):
            _state = 0
        else:
            try:
                _state = float(state.state)
            except ValueError:
                _state = state.state

        measurement = state.attributes.get('unit_of_measurement')
        if measurement in (None, ''):
            measurement = state.entity_id

        json_body = [
            {
                'measurement': measurement,
                'tags': {
                    'domain': state.domain,
                    'entity_id': state.object_id,
                },
                'time': event.time_fired,
                'fields': {
                    'value': _state,
                }
            }
        ]

        try:
            influx.write_points(json_body)
        except exceptions.InfluxDBClientError:
            _LOGGER.exception('Error saving event "%s" to InfluxDB', json_body)

    hass.bus.listen(EVENT_STATE_CHANGED, influx_event_listener)

    return True
