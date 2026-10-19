"""Constants for the Aquanta integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

NAME = "Aquanta"
DOMAIN = "aquanta"
MODEL = "Aquanta Water Heater Controller"
ATTRIBUTION = ""

# Options
CONF_AWAY_DAYS = "away_days"
DEFAULT_AWAY_DAYS = 0  # 0 = stay in Away until turned off
INDEFINITE_AWAY_DAYS = 3650  # far-future window used when DEFAULT_AWAY_DAYS is 0
