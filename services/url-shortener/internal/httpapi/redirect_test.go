package httpapi

import (
	"net/http"
	"strings"
	"testing"
)

const wantNotFound = `{"error":{"code":"not_found","message":"Short URL not found"}}`

func TestRedirect_Hit_302_LocationIsDestination(t *testing.T) {
	_, mux, _ := newTestServer(t)
	const dest = "https://example.com/a/very/long/path?query=value"
	created := createOK(t, mux, dest)
	rec := doRequest(mux, "GET", "/"+created.ID, "", "")
	if rec.Code != http.StatusFound {
		t.Fatalf("status = %d, want 302", rec.Code)
	}
	if loc := rec.Header().Get("Location"); loc != dest {
		t.Errorf("Location = %q, want %q (original destination, verbatim)", loc, dest)
	}
}

func TestRedirect_Miss_404(t *testing.T) {
	_, mux, _ := newTestServer(t)
	rec := doRequest(mux, "GET", "/does-not-exist", "", "")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404", rec.Code)
	}
	if got := strings.TrimSpace(rec.Body.String()); got != wantNotFound {
		t.Errorf("body = %q, want %q", got, wantNotFound)
	}
}

func TestRedirect_NoAuthenticationRequired(t *testing.T) {
	_, mux, _ := newTestServer(t)
	created := createOK(t, mux, "https://example.com/x")
	rec := doRequest(mux, "GET", "/"+created.ID, "", "")
	if rec.Code == http.StatusUnauthorized {
		t.Fatal("redirect required auth — read path must be public")
	}
	if rec.Code != http.StatusFound {
		t.Errorf("status = %d, want 302", rec.Code)
	}
}

func TestRedirect_Miss_NoAuthenticationRequired(t *testing.T) {
	_, mux, _ := newTestServer(t)
	rec := doRequest(mux, "GET", "/nope", "", "")
	if rec.Code == http.StatusUnauthorized {
		t.Fatal("miss required auth — read path must be public")
	}
	if rec.Code != http.StatusNotFound {
		t.Errorf("status = %d, want 404", rec.Code)
	}
}

func TestRedirect_StoreError_500(t *testing.T) {
	// A non-ErrNotFound store error (here: a closed database) must surface
	// as 500, not 404 or a crash. Exercises the redirect handler's
	// internal_error branch.
	mux := newServerWithClosedStore(t)
	rec := doRequest(mux, "GET", "/some-id", "", "")
	if rec.Code != http.StatusInternalServerError {
		t.Errorf("status = %d, want 500 (store error)", rec.Code)
	}
}

func TestRedirect_CreateResponseURLResolves(t *testing.T) {
	_, mux, _ := newTestServer(t)
	const dest = "https://www.rust-lang.org/"
	created := createOK(t, mux, dest)
	if !strings.HasPrefix(created.URL, testBaseURL+"/") {
		t.Errorf("returned URL %q does not start with %s/", created.URL, testBaseURL)
	}
	rec := doRequest(mux, "GET", "/"+created.ID, "", "")
	if rec.Code != http.StatusFound {
		t.Fatalf("status = %d, want 302", rec.Code)
	}
	if rec.Header().Get("Location") != dest {
		t.Errorf("Location = %q, want %q", rec.Header().Get("Location"), dest)
	}
}
