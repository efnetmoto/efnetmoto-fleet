package httpapi

import (
	"encoding/json"
	"net/http"
	"strings"
	"testing"
)

func TestValidURL(t *testing.T) {
	cases := []struct {
		url  string
		want bool
	}{
		// Acceptable absolute http/https URLs with a host.
		{"https://example.com/path", true},
		{"http://example.com", true},
		{"https://example.com:8080/a?b=c#d", true},
		{"http://localhost:8080", true},
		{"https://192.168.1.1/x", true},
		{"https://www.rust-lang.org/", true},

		// Rejected: empty, non-http scheme, no host, relative.
		{"", false},
		{"javascript:alert(1)", false},
		{"data:text/html,<x>", false},
		{"file:///etc/passwd", false},
		{"ftp://example.com", false},
		{"https:///path", false}, // scheme present, host empty
		{"http://", false},       // scheme present, host empty
		{"/relative/path", false},
		{"//example.com/x", false}, // scheme-relative, no scheme
		{"not a url", false},       // no scheme/host

		// Non-absolute strings that url.Parse accepts but with empty scheme.
		{"example.com", false},

		// Triggers the url.Parse error branch (invalid percent-escape), not
		// just a wrong-scheme branch.
		{"https://example.com/%zz", false},
	}
	for _, c := range cases {
		got := validURL(c.url)
		if got != c.want {
			t.Errorf("validURL(%q) = %v, want %v", c.url, got, c.want)
		}
	}
}

func TestCreate_ValidURL_201(t *testing.T) {
	_, mux, _ := newTestServer(t)
	rec := doRequest(mux, "POST", "/api/v1/links", createBody("https://example.com/a/long/path"), testBearer)
	if rec.Code != http.StatusCreated {
		t.Fatalf("status = %d, want 201; body = %s", rec.Code, rec.Body.String())
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type = %q, want application/json", ct)
	}
	var resp createResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if resp.ID == "" {
		t.Error("ID is empty")
	}
	if len(resp.ID) != 7 {
		t.Errorf("ID length = %d, want 7 (default short ID length)", len(resp.ID))
	}
	wantURL := testBaseURL + "/" + resp.ID
	if resp.URL != wantURL {
		t.Errorf("URL = %q, want %q (PUBLIC_BASE_URL + \"/\" + id)", resp.URL, wantURL)
	}
}

func TestCreate_ResponseContainsCompletePublicURL(t *testing.T) {
	// The response url field must be the complete public short URL the
	// Search Bot uses directly, not a bare ID.
	_, mux, _ := newTestServer(t)
	rec := doRequest(mux, "POST", "/api/v1/links", createBody("https://example.com"), testBearer)
	var resp createResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if resp.URL != "https://go.example.com/"+resp.ID {
		t.Errorf("URL = %q, want https://go.example.com/%s", resp.URL, resp.ID)
	}
}

func TestCreate_TwoCreates_DistinctIDs(t *testing.T) {
	_, mux, _ := newTestServer(t)
	a := createOK(t, mux, "https://example.com/a")
	b := createOK(t, mux, "https://example.com/b")
	if a.ID == b.ID {
		t.Errorf("duplicate ID %q across two creates (must be unique)", a.ID)
	}
}

func TestCreate_MissingURLField_400(t *testing.T) {
	_, mux, _ := newTestServer(t)
	rec := doRequest(mux, "POST", "/api/v1/links", `{}`, testBearer)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400; body = %s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"invalid_request"`) {
		t.Errorf("body = %q, want code invalid_request", rec.Body.String())
	}
}

func TestCreate_EmptyURL_400(t *testing.T) {
	_, mux, _ := newTestServer(t)
	rec := doRequest(mux, "POST", "/api/v1/links", createBody(""), testBearer)
	if rec.Code != http.StatusBadRequest {
		t.Errorf("status = %d, want 400", rec.Code)
	}
}

func TestCreate_NonHTTPScheme_400(t *testing.T) {
	cases := []string{
		"javascript:alert(1)",
		"data:text/html,<script>x</script>",
		"file:///etc/passwd",
		"ftp://example.com",
	}
	_, mux, _ := newTestServer(t)
	for _, u := range cases {
		rec := doRequest(mux, "POST", "/api/v1/links", createBody(u), testBearer)
		if rec.Code != http.StatusBadRequest {
			t.Errorf("url=%q: status = %d, want 400; body = %s", u, rec.Code, rec.Body.String())
		}
	}
}

func TestCreate_NoHost_400(t *testing.T) {
	cases := []string{"https:///path", "http://"}
	_, mux, _ := newTestServer(t)
	for _, u := range cases {
		rec := doRequest(mux, "POST", "/api/v1/links", createBody(u), testBearer)
		if rec.Code != http.StatusBadRequest {
			t.Errorf("url=%q: status = %d, want 400", u, rec.Code)
		}
	}
}

func TestCreate_RelativeURL_400(t *testing.T) {
	cases := []string{"/relative", "//example.com/x", "example.com", "not a url"}
	_, mux, _ := newTestServer(t)
	for _, u := range cases {
		rec := doRequest(mux, "POST", "/api/v1/links", createBody(u), testBearer)
		if rec.Code != http.StatusBadRequest {
			t.Errorf("url=%q: status = %d, want 400", u, rec.Code)
		}
	}
}

func TestCreate_MalformedJSON_400(t *testing.T) {
	_, mux, _ := newTestServer(t)
	rec := doRequest(mux, "POST", "/api/v1/links", `{not json`, testBearer)
	if rec.Code != http.StatusBadRequest {
		t.Errorf("status = %d, want 400 (malformed JSON)", rec.Code)
	}
}

func TestCreate_BodyTooLarge_413(t *testing.T) {
	// A body exceeding maxBodyBytes must be rejected as 413, not 400, so
	// the failure mode is distinguishable from a JSON parse error. The
	// body must be *valid JSON* — a syntactically invalid body fails the
	// decoder (→400) before it ever reads enough bytes to trip the limit.
	// A huge but well-formed url string forces the decoder to keep reading
	// until MaxBytesReader denies the next read and returns MaxBytesError.
	_, mux, _ := newTestServer(t)
	bigURL := "https://example.com/" + strings.Repeat("a", maxBodyBytes)
	rec := doRequest(mux, "POST", "/api/v1/links", createBody(bigURL), testBearer)
	if rec.Code != http.StatusRequestEntityTooLarge {
		t.Errorf("status = %d, want 413 (body exceeds %d bytes); body = %q", rec.Code, maxBodyBytes, rec.Body.String())
	}
}

func TestCreate_StoreError_500(t *testing.T) {
	// A store failure (here: a closed database) must surface as 500, not
	// crash or 4xx. Exercises the create handler's internal_error branch.
	mux := newServerWithClosedStore(t)
	rec := doRequest(mux, "POST", "/api/v1/links", createBody("https://example.com"), testBearer)
	if rec.Code != http.StatusInternalServerError {
		t.Errorf("status = %d, want 500 (store error); body = %s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"internal_error"`) {
		t.Errorf("body = %q, want code internal_error", rec.Body.String())
	}
}

func TestCreate_PersistsAndIsRedirectable(t *testing.T) {
	// A created link must be resolvable by the redirect path immediately,
	// proving the create actually stored the mapping.
	_, mux, _ := newTestServer(t)
	const dest = "https://example.com/persisted"
	created := createOK(t, mux, dest)
	rec := doRequest(mux, "GET", "/"+created.ID, "", "")
	if rec.Code != http.StatusFound {
		t.Fatalf("redirect after create: status = %d, want 302", rec.Code)
	}
	if rec.Header().Get("Location") != dest {
		t.Errorf("Location = %q, want %q", rec.Header().Get("Location"), dest)
	}
}
