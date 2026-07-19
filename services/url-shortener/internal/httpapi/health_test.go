package httpapi

import (
	"net/http"
	"strings"
	"testing"
)

func TestHealth_OK(t *testing.T) {
	_, mux, _ := newTestServer(t)
	rec := doRequest(mux, "GET", "/health", "", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
	if got := strings.TrimSpace(rec.Body.String()); got != `{"status":"ok"}` {
		t.Errorf("body = %q, want {\"status\":\"ok\"}", got)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type = %q, want application/json", ct)
	}
}

func TestHealth_NoAuthenticationRequired(t *testing.T) {
	_, mux, _ := newTestServer(t)
	rec := doRequest(mux, "GET", "/health", "", "")
	if rec.Code != http.StatusOK {
		t.Errorf("status = %d, want 200 (health must be public)", rec.Code)
	}
}

func TestHealth_PrecedenceOverShortIDWildcard(t *testing.T) {
	// ServeMux must route GET /health to the literal health handler, not
	// the GET /{short_id} wildcard. Even after links exist (so the store
	// is non-empty), /health must still answer 200 ok.
	_, mux, _ := newTestServer(t)
	createOK(t, mux, "https://example.com/x")
	rec := doRequest(mux, "GET", "/health", "", "")
	if rec.Code != http.StatusOK {
		t.Errorf("status = %d, want 200 (health must win over /{short_id})", rec.Code)
	}
	if got := strings.TrimSpace(rec.Body.String()); got != `{"status":"ok"}` {
		t.Errorf("body = %q, want {\"status\":\"ok\"}", got)
	}
}

func TestRoutes_WrongMethod_405(t *testing.T) {
	// GET /api/v1/links is not registered (only POST). ServeMux must
	// return 405 Method Not Allowed, which the Search Bot treats as a
	// definitive client error (do not retry).
	_, mux, _ := newTestServer(t)
	rec := doRequest(mux, "GET", "/api/v1/links", "", "")
	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("GET /api/v1/links: status = %d, want 405", rec.Code)
	}
}
