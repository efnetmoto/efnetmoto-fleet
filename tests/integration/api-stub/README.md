# api-stub

A zero-dependency (Python stdlib only) HTTP stub that stands in for the
external provider APIs the bots call during the integration suite. It routes by
request path + query to the **existing** test fixtures under
`shared/python-scripts/tests/`, so the suite makes no live network calls and
burns no API quota, with deterministic assertions.

## Routes

| Route | Fixture | Notes |
| --- | --- | --- |
| `GET /res/v1/web/search?q=...` | `searchbot/brave_{one,two,zero}_results.json` | Selected by a marker in `q` (`...zero...`→0, `...one...`→1, else 2) so the driver controls the result count. |
| `GET /v1/current.json?...` | `weather/weatherapi_current.json` | Query ignored; driver asserts the bot's formatted reply. |
| `GET /v1/forecast.json?...` | `weather/weatherapi_forecast.json` | Query ignored. |
| `GET /api/data/metar?...` | `weather/avwx_metar.json` | Query ignored. |

The aprs (`/api/get`) and ambient (`/devices`) providers have no route yet; add
them when a test needs those providers.

## Build & run

Build context is the repo root (the fixtures are COPYed in):

```bash
docker build -f tests/integration/api-stub/Dockerfile -t efnetmoto/api-stub:integration .
docker run --rm -p 8089:8080 --user 65534:65534 efnetmoto/api-stub:integration
```

In the suite it runs on the shared `integration` network as container name `api-stub`.
The bots reach it at `http://api-stub:8080/...` via the provider URL overrides
(see `tests/integration/render.yml` and the generated `overrides.yml`).
