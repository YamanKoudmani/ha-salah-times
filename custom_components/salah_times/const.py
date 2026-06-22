"""Constants for the Salah Times integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "salah_times"
ICON: Final = "mdi:mosque"

# ---------------------------------------------------------------------------
# Config flow — entry.data keys (persistent, require reconfigure to change)
# ---------------------------------------------------------------------------
CONF_NAME: Final = "name"
CONF_LATITUDE: Final = "latitude"
CONF_LONGITUDE: Final = "longitude"

# ---------------------------------------------------------------------------
# Config flow — entry.options keys (editable via options flow)
# ---------------------------------------------------------------------------
CONF_CALCULATION_METHOD: Final = "calculation_method"
CONF_SCHOOL: Final = "school"
CONF_LATITUDE_ADJUSTMENT_METHOD: Final = "latitude_adjustment_method"
CONF_HIJRI_ADJUSTMENT_DAYS: Final = "hijri_adjustment_days"
CONF_POLLING_INTERVAL_HOURS: Final = "polling_interval_hours"
CONF_ENABLE_FAILOVER: Final = "enable_failover"

# ---------------------------------------------------------------------------
# Calculation methods (AlAdhan API)
# Key = API method ID (int as string for Selector compat)
# Value = human-readable name (must match strings.json keys)
# ---------------------------------------------------------------------------
CALCULATION_METHODS: Final[dict[str, str]] = {
    "0": "Jafari / Ithna Ashari",
    "1": "University of Islamic Sciences, Karachi",
    "2": "Islamic Society of North America (ISNA)",
    "3": "Muslim World League (MWL)",
    "4": "Umm Al-Qura University, Makkah",
    "5": "Egyptian General Authority of Survey",
    "7": "Institute of Geophysics, University of Tehran",
    "8": "Gulf Region",
    "9": "Kuwait",
    "10": "Qatar",
    "11": "Majlis Ugama Islam Singapura, Singapore",
    "12": "Union Organization islamic de France (UOIF)",
    "13": "Diyanet İşleri Başkanlığı, Turkey",
    "14": "Spiritual Administration of Muslims of Russia",
    "15": "Moonsighting Committee Worldwide (MCW)",
    "16": "Dubai",
    "17": "Jakim (Jabatan Kemajuan Islam Malaysia)",
    "18": "Tunisia",
    "19": "Algeria",
    "20": "Kementerian Agama Republik Indonesia (KEMENAG)",
    "21": "Morocco",
    "22": "Comunidade Islâmica de Lisboa (CIL)",
    "23": "Ministry of Awqaf, Islamic Affairs and Holy Places, Palestine",
    "99": "Custom",
}

# ---------------------------------------------------------------------------
# Schools (affects Asr time)
# ---------------------------------------------------------------------------
SCHOOLS: Final[dict[str, str]] = {
    "0": "Shafi (Standard)",
    "1": "Hanafi",
}

# ---------------------------------------------------------------------------
# Latitude adjustment methods (for high-latitude regions)
# ---------------------------------------------------------------------------
LATITUDE_ADJUSTMENT_METHODS: Final[dict[str, str]] = {
    "0": "Middle of the Night",
    "1": "One Seventh of the Night",
    "2": "Angle-Based",
    "3": "Angle-Based (AlAdhan default)",
}

# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------
DEFAULT_NAME: Final = "Home"
DEFAULT_CALCULATION_METHOD: Final = "2"  # ISNA
DEFAULT_SCHOOL: Final = "0"  # Shafi
DEFAULT_LATITUDE_ADJUSTMENT_METHOD: Final = "3"  # Angle-based (AlAdhan default)
DEFAULT_HIJRI_ADJUSTMENT_DAYS: Final = 0
DEFAULT_POLLING_INTERVAL_HOURS: Final = 6
DEFAULT_ENABLE_FAILOVER: Final = True

# ---------------------------------------------------------------------------
# Provider names
# ---------------------------------------------------------------------------
PROVIDER_ALADHAN: Final = "aladhan"
PROVIDER_ISLAMIC_APP: Final = "islamic_app"

# ---------------------------------------------------------------------------
# Calendar event duration
# ---------------------------------------------------------------------------
DEFAULT_EVENT_DURATION: Final = timedelta(minutes=10)

# ---------------------------------------------------------------------------
# API retries
# ---------------------------------------------------------------------------
MAX_RETRIES: Final = 2

# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------
POLLING_INTERVAL: Final = timedelta(hours=DEFAULT_POLLING_INTERVAL_HOURS)

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
SERVICE_REFRESH: Final = "refresh"
