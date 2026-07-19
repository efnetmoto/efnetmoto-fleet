package httpapi

import (
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"github.com/efnetmoto/efnetmoto-fleet/services/url-shortener/internal/store"
)

const (
	testAPIKey  = "test-secret-key-not-for-production"
	testBaseURL = "https://go.example.com"
	testBearer  = "Bearer " + testAPIKey
)

// newTestServer builds a Server backed by a fresh temp-file SQLite store
// and returns the wired mux for use with httptest.NewRecorder. Using a real
// store (not a mock) exercises the actual persistence contract end to end.
func newTestServer(t *testing.T) (*Server, http.Handler, *store.Store) {
	t.Helper()
	st, err := store.Open(filepath.Join(t.TempDir(), "test.db"))
	if err != nil {
		t.Fatalf("store.Open: %v", err)
	}
	t.Cleanup(func() {
		if err := st.Close(); err != nil {
			t.Errorf("store.Close: %v", err)
		}
	})
	// Discard logs so tests stay quiet.
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	srv, err := New(st, testBaseURL, testAPIKey, logger)
	if err != nil {
		t.Fatalf("httpapi.New: %v", err)
	}
	return srv, srv.Routes(), st
}

// doRequest issues a request against mux and returns the recorder.
// authHeader, if non-empty, is sent verbatim as the Authorization header.
func doRequest(mux http.Handler, method, path, body, authHeader string) *httptest.ResponseRecorder {
	var r *http.Request
	if body != "" {
		r = httptest.NewRequest(method, path, strings.NewReader(body))
	} else {
		r = httptest.NewRequest(method, path, nil)
	}
	r.Header.Set("Content-Type", "application/json")
	if authHeader != "" {
		r.Header.Set("Authorization", authHeader)
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, r)
	return rec
}

// createBody JSON-encodes a create request body for the given URL. Using
// json.Marshal (rather than string concatenation) keeps tests safe against
// URLs containing characters that would break hand-built JSON.
func createBody(u string) string {
	b, err := json.Marshal(struct {
		URL string `json:"url"`
	}{URL: u})
	if err != nil {
		panic(err)
	}
	return string(b)
}

// createOK creates a short URL via the API and returns the decoded
// response, failing the test if the create did not succeed.
func createOK(t *testing.T, mux http.Handler, dest string) createResponse {
	t.Helper()
	rec := doRequest(mux, "POST", "/api/v1/links", createBody(dest), testBearer)
	if rec.Code != http.StatusCreated {
		t.Fatalf("create %q: status %d, body %s", dest, rec.Code, rec.Body.String())
	}
	var resp createResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("decode create response: %v", err)
	}
	return resp
}
