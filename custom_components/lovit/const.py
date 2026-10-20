"""Constants for the Lovit integration."""

from __future__ import annotations

import logging

DOMAIN = "lovit"
LOGGER = logging.getLogger(__package__)

#: Base URL of the Lovit personal cabinet.
BASE_URL = "https://lk.lovit.ru"
LOGIN_PATH = "/login"
USER_INFO_PATH = "/api/user/info"

CONF_LOGIN = "login"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 15  # minutes
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 1440

MANUFACTURER = "Lovit"
MODEL = "Personal cabinet"
