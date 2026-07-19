package httpapi

import (
	"bytes"
	"net/http"
	"strings"
	"testing"
)

// wantUnauthorized is the exact 401 body every auth failure must produce.
// All failure modes (missing header, wrong scheme, wrong token, empty
// token) render this identical body so the response leaks nothing about
// how close a supplied key was.
const wantUnauthorized = `{"error":{"code":"unauthorized","message":"Authentication required"}}`

func TestAuth_MissingAuthorization_401(t *testing.T) {
	_, mux, _ := newTestServer(t)
	rec := doRequest(mux, "POST", "/api/v1/links", createBody("https://example.com"), "")
	if rec.Code != http.StatusUnauthorized {
		t.Errorf("status = %d, want 401", rec.Code)
	}
	if got := strings.TrimSpace(rec.Body.String()); got != wantUnauthorized {
		t.Errorf("body = %q, want %q", got, wantUnauthorized)
	}
}

func TestAuth_WrongKey_401(t *testing.T) {
	_, mux, _ := newTestServer(t)
	rec := doRequest(mux, "POST", "/api/v1/links", createBody("https://example.com"), "Bearer wrong-key")
	if rec.Code != http.StatusUnauthorized {
		t.Errorf("status = %d, want 401", rec.Code)
	}
	if got := strings.TrimSpace(rec.Body.String()); got != wantUnauthorized {
		t.Errorf("body = %q, want %q", got, wantUnauthorized)
	}
}

func TestAuth_WrongScheme_401(t *testing.T) {
	_, mux, _ := newTestServer(t)
	rec := doRequest(mux, "POST", "/api/v1/links", createBody("https://example.com"), "Basic dXNlcjpwYXNz")
	if rec.Code != http.StatusUnauthorized {
		t.Errorf("status = %d, want 401 (wrong scheme must not authenticate)", rec.Code)
	}
}

func TestAuth_EmptyToken_401(t *testing.T) {
	_, mux, _ := newTestServer(t)
	// "Bearer " with no token must not match a configured key (and must not
	// match an empty configured key — guarded by New, but tested anyway).
	rec := doRequest(mux, "POST", "/api/v1/links", createBody("https://example.com"), "Bearer ")
	if rec.Code != http.StatusUnauthorized {
		t.Errorf("status = %d, want 401 (empty bearer token must not authenticate)", rec.Code)
	}
}

func TestAuth_NearMiss_401(t *testing.T) {
	// A key sharing a long common prefix with the real key must still
	// fail and produce the identical body — no partial-match signal.
	_, mux, _ := newTestServer(t)
	near := testAPIKey + "extra"
	rec := doRequest(mux, "POST", "/api/v1/links", createBody("https://example.com"), "Bearer "+near)
	if rec.Code != http.StatusUnauthorized {
		t.Errorf("status = %d, want 401 (near-miss must not authenticate)", rec.Code)
	}
	if got := strings.TrimSpace(rec.Body.String()); got != wantUnauthorized {
		t.Errorf("body = %q, want identical generic body", got)
	}
}

func TestAuth_MissingAndWrongKey_ProduceIdenticalResponses(t *testing.T) {
	// Security: the response must not distinguish missing from wrong key
	// in either status or body. A timing difference is not asserted here
	// (hard to test reliably), but byte-identity of the bodies is.
	_, mux, _ := newTestServer(t)
	recMissing := doRequest(mux, "POST", "/api/v1/links", createBody("https://example.com"), "")
	recWrong := doRequest(mux, "POST", "/api/v1/links", createBody("https://example.com"), "Bearer wrong-key")
	if recMissing.Code != recWrong.Code {
		t.Errorf("status differs: missing=%d wrong=%d (must be identical)", recMissing.Code, recWrong.Code)
	}
	if !bytes.Equal(recMissing.Body.Bytes(), recWrong.Body.Bytes()) {
		t.Errorf("body differs between missing and wrong key (must be identical):\nmissing=%s\nwrong=%s",
			recMissing.Body, recWrong.Body)
	}
}

func TestAuth_ValidKey_PassesToHandler(t *testing.T) {
	// A valid key must reach the handler and (with a valid URL) produce
	// 201, not 401. This confirms requireAuth forwards on success.
	_, mux, _ := newTestServer(t)
	rec := doRequest(mux, "POST", "/api/v1/links", createBody("https://example.com"), testBearer)
	if rec.Code == http.StatusUnauthorized {
		t.Fatal("valid key was rejected (401); want handler to run")
	}
	if rec.Code != http.StatusCreated {
		t.Errorf("status = %d, want 201 (valid key + valid URL)", rec.Code)
	}
}
