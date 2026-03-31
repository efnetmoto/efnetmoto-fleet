# iata_codes.txt is sourced from OurAirports airports.csv (https://ourairports.com/data/).
# To regenerate: download airports.csv, extract the iata_code column,
# filter non-empty, strip whitespace, sort, deduplicate, write one code per line.

import os
import re

from weather.exceptions import ResolverError
from weather.models import LocationResult, LocationType

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

_ICAO_PREFIXES = frozenset("KPTELHUFORSVYWZ")

_ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")
_AMBIENT_URL_RE = re.compile(r"^https?://ambientweather\.net/dashboard/([0-9a-f]{32})$")
_AMBIENT_SLUG_RE = re.compile(r"^[0-9a-f]{32}$")
# APRS supports HAM call signs with the SSID 13 suffixed
_APRS_RE = re.compile(r"^(?:[KNW][0-9][A-Z]{1,3}|[KNW][A-Z][0-9][A-Z]{1,3})-13$")


def _load_iata_codes() -> frozenset[str]:
    path = os.path.join(_DATA_DIR, "iata_codes.txt")
    with open(path) as f:
        return frozenset(line.strip() for line in f if line.strip())


_IATA_CODES = _load_iata_codes()


def classify(raw: str) -> LocationResult:
    stripped = raw.strip()

    if not stripped:
        raise ResolverError("no_input")

    # Ambient URL must be checked on the original-cased stripped input before uppercasing
    m = _AMBIENT_URL_RE.match(stripped)
    if m:
        slug = m.group(1)
        return LocationResult(type=LocationType.AMBIENT_URL, query=slug, raw=stripped)

    # Ambient slug must be checked before uppercasing (slugs are lowercase hex)
    if _AMBIENT_SLUG_RE.match(stripped):
        return LocationResult(type=LocationType.AMBIENT_SLUG, query=stripped, raw=stripped)

    normalized = stripped.upper()

    if _ZIP_RE.match(normalized):
        return LocationResult(type=LocationType.ZIP, query=normalized, raw=stripped)

    if _APRS_RE.match(normalized):
        return LocationResult(type=LocationType.APRS, query=normalized, raw=stripped)

    if len(normalized) == 4 and normalized.isalnum() and normalized[0] in _ICAO_PREFIXES:
        return LocationResult(type=LocationType.ICAO, query=normalized, raw=stripped)

    if len(normalized) == 3 and normalized.isalpha() and normalized in _IATA_CODES:
        return LocationResult(type=LocationType.IATA, query=normalized, raw=stripped)

    return LocationResult(type=LocationType.CITY_STATE, query=normalized, raw=stripped)
