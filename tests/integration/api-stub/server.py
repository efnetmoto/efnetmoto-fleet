"""Minimal HTTP stub for the external provider APIs exercised by the integration suite.

Serves the fixtures under ``shared/python-scripts/tests/``, so a fixture change
affects both the unit tests and the integration tests.

The brave route selects a fixture by a marker in the query so the pytest driver
controls the result count (``...zero...`` / ``...one...`` / default two). The
weather routes ignore the query and always return their single fixture — the
driver asserts the bot's formatted reply, which is derived from the fixture.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

FIXTURES = Path(os.environ.get("INTEGRATION_FIXTURES", "/fixtures"))
SEARCHBOT = FIXTURES / "searchbot"
WEATHER = FIXTURES / "weather"
PORT = int(os.environ.get("PORT", "8080"))


def _brave_fixture(q: str) -> Path:
    ql = (q or "").lower()
    if "zero" in ql or "none" in ql:
        return SEARCHBOT / "brave_zero_results.json"
    if "one" in ql or "single" in ql:
        return SEARCHBOT / "brave_one_result.json"
    return SEARCHBOT / "brave_two_results.json"


ROUTES: dict[str, object] = {
    "/res/v1/web/search": _brave_fixture,
    "/v1/current.json": lambda _q: WEATHER / "weatherapi_current.json",
    "/v1/forecast.json": lambda _q: WEATHER / "weatherapi_forecast.json",
    "/api/data/metar": lambda _q: WEATHER / "avwx_metar.json",
}


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send_json(self, status: int, body: dict | list) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        parsed = urlparse(self.path)
        resolver = ROUTES.get(parsed.path)
        if resolver is None:
            self._send_json(404, {"error": f"no stub route for {parsed.path}"})
            return
        q = (parse_qs(parsed.query).get("q") or [""])[0]
        fixture: Path = resolver(q)  # type: ignore[operator]
        if not fixture.is_file():
            self._send_json(404, {"error": f"fixture missing: {fixture}"})
            return
        self._send_json(200, json.loads(fixture.read_text()))

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}", flush=True)


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), _Handler)
    print(f"api-stub listening on :{PORT}, fixtures at {FIXTURES}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
