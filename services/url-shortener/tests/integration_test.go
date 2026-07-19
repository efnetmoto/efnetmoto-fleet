// Package integration exercises the URL shortener end to end over real
// HTTP against a temp-file SQLite database. The tests assert the public
// contract a client (e.g. the IRC Search Bot) relies on: the create
// response shape, the redirect, the 404, non-idempotent creation, and
// the auth/validation failures a client must handle.
//
// No live network calls are made. The service itself never makes
// outbound requests — destination validation is syntactic only — so the
// test suite has no network dependency.
package integration

import (
	"bytes"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"github.com/efnetmoto/efnetmoto-fleet/services/url-shortener/internal/httpapi"
	"github.com/efnetmoto/efnetmoto-fleet/services/url-shortener/internal/store"
)

const (
	apiKey  = "integration-test-key"
	baseURL = "https://go.efnetmoto.com"
	bearer  = "Bearer " + apiKey
)

// createResponse mirrors the create endpoint's 201 body.
type createResponse struct {
	ID  string `json:"id"`
	URL string `json:"url"`
}

// newServer brings up a real HTTP server backed by a fresh temp-file
// SQLite store. Both the store and the server are torn down on test
// completion. Using a real store (not a mock) and a real httptest.Server
// (not a ResponseRecorder) exercises the full HTTP stack and the real
// persistence contract the search bot will rely on.
func newServer(t *testing.T) *httptest.Server {
	t.Helper()
	st, err := store.Open(filepath.Join(t.TempDir(), "integration.db"))
	if err != nil {
		t.Fatalf("store.Open: %v", err)
	}
	t.Cleanup(func() {
		if err := st.Close(); err != nil {
			t.Errorf("store.Close: %v", err)
		}
	})
	srv, err := httpapi.New(st, baseURL, apiKey, slog.New(slog.NewTextHandler(io.Discard, nil)))
	if err != nil {
		t.Fatalf("httpapi.New: %v", err)
	}
	ts := httptest.NewServer(srv.Routes())
	t.Cleanup(ts.Close)
	return ts
}

// noRedirectClient returns an http.Client that does not auto-follow
// redirects, so redirect tests can assert the 302 status and Location
// header directly rather than following the destination.
func noRedirectClient() *http.Client {
	return &http.Client{
		CheckRedirect: func(*http.Request, []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
}

// doCreate POSTs a create request with the given destination URL and
// Authorization header and returns the status code plus the decoded
// body. The body is left zero-valued for non-201 responses.
func doCreate(t *testing.T, ts *httptest.Server, dest, auth string) (int, createResponse) {
	t.Helper()
	body, err := json.Marshal(struct {
		URL string `json:"url"`
	}{URL: dest})
	if err != nil {
		t.Fatalf("marshal create body: %v", err)
	}
	req, err := http.NewRequest(http.MethodPost, ts.URL+"/api/v1/links", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("NewRequest: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if auth != "" {
		req.Header.Set("Authorization", auth)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("create Do: %v", err)
	}
	defer resp.Body.Close()
	var cr createResponse
	if resp.StatusCode == http.StatusCreated {
		if err := json.NewDecoder(resp.Body).Decode(&cr); err != nil {
			t.Fatalf("decode create response: %v", err)
		}
	}
	return resp.StatusCode, cr
}

// doCreateRaw POSTs a raw body string (for malformed-JSON cases that
// json.Marshal cannot produce) with valid auth, returning the status.
func doCreateRaw(t *testing.T, ts *httptest.Server, body string) int {
	t.Helper()
	req, err := http.NewRequest(http.MethodPost, ts.URL+"/api/v1/links", strings.NewReader(body))
	if err != nil {
		t.Fatalf("NewRequest: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", bearer)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("create Do: %v", err)
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, resp.Body)
	return resp.StatusCode
}

// doRedirect GETs /{id} without following redirects and returns the
// status code and Location header.
func doRedirect(t *testing.T, ts *httptest.Server, id string) (int, string) {
	t.Helper()
	resp, err := noRedirectClient().Get(ts.URL + "/" + id)
	if err != nil {
		t.Fatalf("redirect Get %q: %v", id, err)
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, resp.Body)
	return resp.StatusCode, resp.Header.Get("Location")
}

// createOK is doCreate that asserts a 201 and returns the decoded
// response, failing the test otherwise.
func createOK(t *testing.T, ts *httptest.Server, dest string) createResponse {
	t.Helper()
	code, cr := doCreate(t, ts, dest, bearer)
	if code != http.StatusCreated {
		t.Fatalf("create %q: status %d, want 201", dest, code)
	}
	return cr
}

// TestCreateAndRedirect exercises the full create→redirect round trip
// over real HTTP: POST a destination URL, receive 201 with the short URL,
// and GET it back as a 302 to the original destination. A client uses
// the returned url field verbatim and must not construct the short URL
// itself.
func TestCreateAndRedirect(t *testing.T) {
	ts := newServer(t)
	const dest = "https://www.rust-lang.org/"

	cr := createOK(t, ts, dest)
	if cr.ID == "" {
		t.Fatal("create returned empty id")
	}
	// A client uses the returned url field verbatim and must not
	// construct the short URL itself.
	if want := baseURL + "/" + cr.ID; cr.URL != want {
		t.Fatalf("create url = %q, want %q", cr.URL, want)
	}

	code, loc := doRedirect(t, ts, cr.ID)
	if code != http.StatusFound {
		t.Fatalf("redirect status = %d, want 302", code)
	}
	if loc != dest {
		t.Fatalf("redirect Location = %q, want %q", loc, dest)
	}
}

// TestCreate_IsNotIdempotent verifies that submitting the same destination
// URL twice produces two distinct short URLs, both resolving to the
// destination. A client must not assume a retry returns the same short
// URL and must not retry a successful request.
func TestCreate_IsNotIdempotent(t *testing.T) {
	ts := newServer(t)
	const dest = "https://example.com/article"

	first := createOK(t, ts, dest)
	second := createOK(t, ts, dest)
	if first.ID == second.ID {
		t.Fatalf("non-idempotent: two creates for %q returned the same id %q", dest, first.ID)
	}
	if first.URL == second.URL {
		t.Fatalf("non-idempotent: two creates returned the same url %q", first.URL)
	}
	// Both short URLs resolve to the same destination — the first
	// mapping is not overwritten by the second.
	for _, cr := range []createResponse{first, second} {
		code, loc := doRedirect(t, ts, cr.ID)
		if code != http.StatusFound {
			t.Fatalf("redirect %q status = %d, want 302", cr.ID, code)
		}
		if loc != dest {
			t.Fatalf("redirect %q Location = %q, want %q", cr.ID, loc, dest)
		}
	}
}

// TestCreate_RequiresAuth verifies the create API rejects requests
// without a valid bearer token. The 401 response is identical whether
// the header is missing or merely wrong — a client cannot distinguish
// the two and must treat both as a configuration error.
func TestCreate_RequiresAuth(t *testing.T) {
	ts := newServer(t)
	const dest = "https://example.com/"

	for _, tc := range []struct {
		name string
		auth string
	}{
		{"missing header", ""},
		{"wrong key", "Bearer not-the-right-key"},
		{"malformed scheme", "Token " + apiKey},
	} {
		t.Run(tc.name, func(t *testing.T) {
			code, _ := doCreate(t, ts, dest, tc.auth)
			if code != http.StatusUnauthorized {
				t.Fatalf("status = %d, want 401", code)
			}
		})
	}
}

// TestCreate_InvalidBodies covers the 400 paths a client logs and falls
// back from: the destination URL must be present and an absolute
// http/https URL; everything else is rejected without touching the store.
func TestCreate_InvalidBodies(t *testing.T) {
	ts := newServer(t)

	for _, tc := range []struct {
		name string
		body string
	}{
		{"malformed json", `{"url":`},
		{"missing url field", `{"noturl":"https://example.com/"}`},
		{"empty url", `{"url":""}`},
		{"non-http scheme", `{"url":"ftp://example.com/"}`},
		{"relative url", `{"url":"/a/relative/path"}`},
		{"javascript scheme", `{"url":"javascript:alert(1)"}`},
	} {
		t.Run(tc.name, func(t *testing.T) {
			if code := doCreateRaw(t, ts, tc.body); code != http.StatusBadRequest {
				t.Fatalf("status = %d, want 400", code)
			}
		})
	}
}

// TestRedirect_UnknownID_404 verifies the read path returns 404 JSON for
// an unknown short id. A client treats 404 from the redirect path as a
// configuration/deployment error (it only GETs short IDs it created).
func TestRedirect_UnknownID_404(t *testing.T) {
	ts := newServer(t)
	resp, err := noRedirectClient().Get(ts.URL + "/no-such-id")
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("status = %d, want 404", resp.StatusCode)
	}
	if ct := resp.Header.Get("Content-Type"); !strings.HasPrefix(ct, "application/json") {
		t.Fatalf("Content-Type = %q, want application/json", ct)
	}
	body, _ := io.ReadAll(resp.Body)
	for _, want := range []string{`"code"`, `"message"`, "not_found"} {
		if !strings.Contains(string(body), want) {
			t.Fatalf("404 body = %q, missing %q", string(body), want)
		}
	}
}

// TestHealth verifies the liveness probe returns 200 with
// {"status":"ok"}. The Dockerfile HEALTHCHECK and Docker Compose health
// status depend on this endpoint.
func TestHealth(t *testing.T) {
	ts := newServer(t)
	resp, err := http.Get(ts.URL + "/health")
	if err != nil {
		t.Fatalf("Get /health: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want 200", resp.StatusCode)
	}
	if ct := resp.Header.Get("Content-Type"); !strings.HasPrefix(ct, "application/json") {
		t.Fatalf("Content-Type = %q, want application/json", ct)
	}
	body, _ := io.ReadAll(resp.Body)
	if !strings.Contains(string(body), `"status":"ok"`) {
		t.Fatalf("health body = %q, want JSON with status ok", string(body))
	}
}

// TestCreate_PersistsAcrossStoreReopen verifies a created short URL
// survives a store close/reopen — the persistence contract that makes
// the bind-mounted SQLite database a reliable backing store across
// container restarts.
func TestCreate_PersistsAcrossStoreReopen(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "integration.db")

	st, err := store.Open(dbPath)
	if err != nil {
		t.Fatalf("store.Open: %v", err)
	}
	srv, err := httpapi.New(st, baseURL, apiKey, slog.New(slog.NewTextHandler(io.Discard, nil)))
	if err != nil {
		t.Fatalf("httpapi.New: %v", err)
	}
	ts := httptest.NewServer(srv.Routes())
	cr := createOK(t, ts, "https://example.com/persistent")
	ts.Close()
	if err := st.Close(); err != nil {
		t.Fatalf("store.Close: %v", err)
	}

	st2, err := store.Open(dbPath)
	if err != nil {
		t.Fatalf("store.Open (reopen): %v", err)
	}
	defer func() {
		if err := st2.Close(); err != nil {
			t.Errorf("store.Close (reopen): %v", err)
		}
	}()
	srv2, err := httpapi.New(st2, baseURL, apiKey, slog.New(slog.NewTextHandler(io.Discard, nil)))
	if err != nil {
		t.Fatalf("httpapi.New (reopen): %v", err)
	}
	ts2 := httptest.NewServer(srv2.Routes())
	defer ts2.Close()

	code, loc := doRedirect(t, ts2, cr.ID)
	if code != http.StatusFound {
		t.Fatalf("redirect after reopen status = %d, want 302", code)
	}
	if loc != "https://example.com/persistent" {
		t.Fatalf("redirect after reopen Location = %q, want the original destination", loc)
	}
}
