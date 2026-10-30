"""Constantes da integração Solar Cover."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "solar_cover"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Config entry (data)
CONF_COVER = "cover_entity_id"

# Config entry (options)
CONF_FACADE_AZIMUTH = "facade_azimuth"
CONF_MAX_INCIDENCE = "max_incidence"
CONF_ROLL_CENTER = "roll_center_height"
CONF_EDGE_TO_ROLL_OPEN = "edge_to_roll_open"
CONF_EDGE_TO_FLOOR_CLOSED = "edge_to_floor_closed"
CONF_BEAM_HEIGHT = "beam_height"
CONF_DOOR_DISTANCE = "door_distance"
CONF_DOOR_HEIGHT = "door_height"
CONF_TEMPERATURE_ENTITY = "temperature_entity"
CONF_LUX_ENTITY = "lux_entity"
CONF_ALARM_ENTITY = "alarm_entity"
CONF_HORIZON = "horizon"

GEOMETRY_KEYS = (
    CONF_ROLL_CENTER,
    CONF_EDGE_TO_ROLL_OPEN,
    CONF_EDGE_TO_FLOOR_CLOSED,
    CONF_BEAM_HEIGHT,
    CONF_DOOR_DISTANCE,
    CONF_DOOR_HEIGHT,
)

DEFAULT_FACADE_AZIMUTH = 270.0
DEFAULT_MAX_INCIDENCE = 85.0

# Cotas de partida: as do croqui da cortina da cozinha (cm).
DEFAULT_GEOMETRY = {
    CONF_ROLL_CENTER: 255.0,
    CONF_EDGE_TO_ROLL_OPEN: 9.0,
    CONF_EDGE_TO_FLOOR_CLOSED: 9.0,
    CONF_BEAM_HEIGHT: 230.0,
    CONF_DOOR_DISTANCE: 120.0,
    CONF_DOOR_HEIGHT: 220.0,
}

UPDATE_INTERVAL = timedelta(seconds=30)
COMMAND_GRACE = timedelta(seconds=180)
"""Depois de um comando nosso, movimentos da cortina não contam como ajuste manual."""

STORAGE_VERSION = 1
STORAGE_SAVE_DELAY = 5

MOVING_STATES = ("opening", "closing")

# Classes de dispositivo que a autodescoberta sugere (persianas, cortinas, toldos...).
DISCOVERABLE_DEVICE_CLASSES = frozenset({"awning", "blind", "curtain", "shade", "shutter"})
