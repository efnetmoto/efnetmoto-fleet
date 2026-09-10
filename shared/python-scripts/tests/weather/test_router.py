import pytest

from weather.exceptions import ProviderError
from weather.models import LocationResult, LocationType
from weather.providers.ambient import AmbientProvider
from weather.providers.aprs import AprsProvider
from weather.providers.avwx import AvWxProvider
from weather.providers.nws import NationalWeatherServiceProvider
from weather.providers.weatherapi import WeatherAPIProvider
from weather.router import ProviderRouter


@pytest.fixture
def router():
    ambient = AmbientProvider()
    aprs = AprsProvider()
    avwx = AvWxProvider()
    wapi = WeatherAPIProvider()
    nws = NationalWeatherServiceProvider()
    return ProviderRouter([wapi, avwx, aprs, ambient, nws])


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


def test_router_manual_override_awn_bypasses_guards(router):
    """--awn forces Ambient even for an ICAO-like location, bypassing metar guard."""
    slug = "aaaabbbbccccddddaaaabbbbccccdddd"
    loc = LocationResult(type=LocationType.AMBIENT_SLUG, query=slug, raw=slug)
    selected = router.route(loc, provider_id="awn")
    assert isinstance(selected, AmbientProvider)


def test_router_manual_override_avwx_bypasses_metar_guard(router):
    """--avwx on an ICAO code works without --metar, bypassing the ICAO guard."""
    loc = LocationResult(type=LocationType.ICAO, query="KSFO", raw="KSFO")
    selected = router.route(loc, metar=False, provider_id="avwx")
    assert isinstance(selected, AvWxProvider)


def test_router_manual_override_weatherapi_on_icao(router):
    """--weatherapi on ICAO bypasses the guard and forces WeatherAPI."""
    loc = LocationResult(type=LocationType.ICAO, query="KSFO", raw="KSFO")
    selected = router.route(loc, metar=False, provider_id="weatherapi")
    assert isinstance(selected, WeatherAPIProvider)


def test_router_manual_override_aprs(router):
    loc = LocationResult(type=LocationType.APRS, query="KK8MPO-13", raw="KK8MPO-13")
    selected = router.route(loc, provider_id="aprs")
    assert isinstance(selected, AprsProvider)


def test_router_manual_override_unsupported_location_raises(router):
    """Forcing a provider on a location it can't handle gives a clear error."""
    loc = LocationResult(type=LocationType.ZIP, query="94025", raw="94025")
    with pytest.raises(ProviderError, match="can't handle that location"):
        router.route(loc, provider_id="awn")


def test_router_manual_override_unknown_id_raises(router):
    """Unknown provider id lists available options."""
    loc = LocationResult(type=LocationType.ZIP, query="94025", raw="94025")
    with pytest.raises(ProviderError, match="Unknown provider"):
        router.route(loc, provider_id="bogus")


def test_router_manual_override_unknown_id_lists_available(router):
    """Error message lists all available provider ids."""
    loc = LocationResult(type=LocationType.ZIP, query="94025", raw="94025")
    try:
        router.route(loc, provider_id="bogus")
    except ProviderError as e:
        msg = str(e)
        assert "--weatherapi" in msg
        assert "--avwx" in msg
        assert "--aprs" in msg
        assert "--awn" in msg
        assert "--nws" in msg


def test_router_nws_never_wins_autodiscovery(router):
    """NWS has empty preferred_types — CITY_STATE routes to WeatherAPI."""
    loc = LocationResult(type=LocationType.CITY_STATE, query="94025", raw="94025")
    selected = router.route(loc, metar=False)
    assert isinstance(selected, WeatherAPIProvider)


def test_router_nws_station_auto_discovers_to_weatherapi(router):
    """NWS has empty preferred_types — NWS_STATION falls through to WeatherAPI."""
    loc = LocationResult(type=LocationType.NWS_STATION, query="BNDC1", raw="BNDC1")
    selected = router.route(loc, metar=False)
    assert isinstance(selected, WeatherAPIProvider)


def test_router_manual_override_nws_icao(router):
    """--nws on an ICAO code bypasses the metar guard and routes to NWS."""
    loc = LocationResult(type=LocationType.ICAO, query="KSFO", raw="KSFO")
    selected = router.route(loc, metar=False, provider_id="nws")
    assert isinstance(selected, NationalWeatherServiceProvider)


def test_router_manual_override_nws_station(router):
    """--nws on a non-ICAO station ID routes to NWS."""
    loc = LocationResult(type=LocationType.NWS_STATION, query="BNDC1", raw="BNDC1")
    selected = router.route(loc, provider_id="nws")
    assert isinstance(selected, NationalWeatherServiceProvider)


def test_router_manual_override_nws_rejects_city_state(router):
    """--nws can't handle city/state locations."""
    loc = LocationResult(
        type=LocationType.CITY_STATE, query="San Francisco, CA", raw="San Francisco, CA"
    )
    with pytest.raises(ProviderError, match="can't handle"):
        router.route(loc, provider_id="nws")


def test_router_manual_override_ignores_metar(router):
    """When provider_id is set, metar flag is ignored — no metar/ICAO guard."""
    loc = LocationResult(type=LocationType.ZIP, query="94025", raw="94025")
    selected = router.route(loc, metar=True, provider_id="weatherapi")
    assert isinstance(selected, WeatherAPIProvider)


def test_router_available_ids(router):
    """available_ids returns all provider ids in registration order."""
    assert router.available_ids() == ["weatherapi", "avwx", "aprs", "awn", "nws"]


def test_router_duplicate_id_raises():
    """Two providers with the same id fail fast at construction."""

    class FakeProvider(WeatherAPIProvider):
        id = "weatherapi"  # duplicate of the real one

    with pytest.raises(ValueError, match="duplicate provider id"):
        ProviderRouter([WeatherAPIProvider(), FakeProvider()])
