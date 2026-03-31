import pytest

from weather.exceptions import ProviderError
from weather.models import LocationResult, LocationType
from weather.providers.ambient import AmbientProvider
from weather.providers.aprs import AprsProvider
from weather.providers.avwx import AvWxProvider
from weather.providers.weatherapi import WeatherAPIProvider
from weather.router import ProviderRouter


@pytest.fixture
def router():
    ambient = AmbientProvider()
    aprs = AprsProvider()
    avwx = AvWxProvider()
    wapi = WeatherAPIProvider()
    return ProviderRouter([wapi, avwx, aprs, ambient])


def test_router_metar_prefers_avwx(router):
    loc = LocationResult(type=LocationType.ICAO, query="KSFO", raw="KSFO")
    selected = router.route(loc, metar=True)
    assert isinstance(selected, AvWxProvider)


def test_router_icao_without_metar_raises(router):
    """ICAO codes without --metar are rejected with an actionable error."""
    loc = LocationResult(type=LocationType.ICAO, query="KSFO", raw="KSFO")
    with pytest.raises(ProviderError, match="--metar"):
        router.route(loc, metar=False)


def test_router_metar_without_icao_raises(router):
    """--metar without ICAO codes are rejected with an actionable error."""
    loc = LocationResult(type=LocationType.CITY_STATE, query="0S9", raw="0S9")
    with pytest.raises(ProviderError, match="requires 3-digit ICAO codes"):
        router.route(loc, metar=True)


def test_router_no_metar_prefers_weatherapi(router):
    loc = LocationResult(type=LocationType.ZIP, query="94025", raw="94025")
    selected = router.route(loc, metar=False)
    assert isinstance(selected, WeatherAPIProvider)


def test_router_ambientslug_prefers_awn(router):
    slug = "aaaabbbbccccddddaaaabbbbccccdddd"
    loc = LocationResult(type=LocationType.AMBIENT_SLUG, query=slug, raw=slug)
    selected = router.route(loc, metar=False)
    assert isinstance(selected, AmbientProvider)


def test_router_ambienturl_prefers_awn(router):
    url = "https://ambientweather.net/dashboard/aaaabbbbccccddddaaaabbbbccccdddd"
    loc = LocationResult(type=LocationType.AMBIENT_URL, query=url, raw=url)
    selected = router.route(loc, metar=False)
    assert isinstance(selected, AmbientProvider)


def test_router_no_ambienturl_provider_raises():
    avwx = AvWxProvider()
    router = ProviderRouter([avwx])
    url = "https://ambientweather.net/dashboard/aaaabbbbccccddddaaaabbbbccccdddd"
    loc = LocationResult(type=LocationType.AMBIENT_SLUG, query=url, raw=url)
    with pytest.raises(ProviderError, match="No provider available"):
        router.route(loc)


def test_router_no_ambientslug_provider_raises():
    avwx = AvWxProvider()
    router = ProviderRouter([avwx])
    slug = "aaaabbbbccccddddaaaabbbbccccdddd"
    loc = LocationResult(type=LocationType.AMBIENT_SLUG, query=slug, raw=slug)
    with pytest.raises(ProviderError, match="No provider available"):
        router.route(loc)


def test_router_aprs_prefers_aprs(router):
    loc = LocationResult(type=LocationType.APRS, query="KK8MPO-13", raw="KK8MPO-13")
    selected = router.route(loc, metar=False)
    assert isinstance(selected, AprsProvider)


def test_router_no_aprs_provider_raises():
    avwx = AvWxProvider()
    router = ProviderRouter([avwx])
    loc = LocationResult(type=LocationType.APRS, query="N3TVP-13", raw="N3TVP-13")
    with pytest.raises(ProviderError, match="No provider available"):
        router.route(loc)


def test_router_no_wapi_provider_raises():
    avwx = AvWxProvider()
    router = ProviderRouter([avwx])  # only avwx, which only handles ICAO
    loc = LocationResult(type=LocationType.ZIP, query="94025", raw="94025")
    with pytest.raises(ProviderError, match="No provider available"):
        router.route(loc)
