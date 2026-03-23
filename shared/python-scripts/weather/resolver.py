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


def _load_iata_codes() -> frozenset[str]:
    path = os.path.join(_DATA_DIR, "iata_codes.txt")
    with open(path) as f:
        return frozenset(line.strip() for line in f if line.strip())


_IATA_CODES = _load_iata_codes()


def classify(raw: str) -> LocationResult:
    stripped = raw.strip()
    normalized = stripped.upper()

    if not normalized:
        raise ResolverError("no_input")

    if _ZIP_RE.match(normalized):
        return LocationResult(type=LocationType.ZIP, query=normalized, raw=stripped)

    if len(normalized) == 4 and normalized.isalpha() and normalized[0] in _ICAO_PREFIXES:
        return LocationResult(type=LocationType.ICAO, query=normalized, raw=stripped)

    if len(normalized) == 3 and normalized.isalpha() and normalized in _IATA_CODES:
        return LocationResult(type=LocationType.IATA, query=normalized, raw=stripped)

    return LocationResult(type=LocationType.CITY_STATE, query=normalized, raw=stripped)
