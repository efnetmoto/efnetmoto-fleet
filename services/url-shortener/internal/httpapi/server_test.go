package httpapi

import (
	"io"
	"log/slog"
	"net/http"
	"path/filepath"
	"testing"

	"github.com/efnetmoto/efnetmoto-fleet/services/url-shortener/internal/store"
)

func TestNew_RejectsNilStore(t *testing.T) {
	if _, err := New(nil, testBaseURL, testAPIKey, nil); err == nil {
		t.Fatal("New(nil store) succeeded; want error")
	}
}

func TestNew_RejectsInvalidBaseURL(t *testing.T) {
	// The base URL prefixes every returned short URL, so a typoed or
	// scheme-less value must fail loudly at startup rather than silently
	// emit broken URLs.
	st, err := store.Open(filepath.Join(t.TempDir(), "test.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = st.Close() })
	for _, base := range []string{"", "   ", "\t\n", "go.example.com", "ftp://example.com", "https:///path"} {
		if _, err := New(st, base, testAPIKey, nil); err == nil {
			t.Errorf("New(baseURL=%q) succeeded; want error", base)
		}
	}
}

func TestNew_RejectsEmptyAPIKey(t *testing.T) {
	// Security guard: an empty configured API key would authenticate a
	// request carrying an empty bearer token ("Bearer "). New must refuse
	// to construct such a Server so the footgun cannot exist at runtime.
	st, err := store.Open(filepath.Join(t.TempDir(), "test.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = st.Close() })
	if _, err := New(st, testBaseURL, "", nil); err == nil {
		t.Fatal("New(empty apiKey) succeeded; want error")
	}
}

func TestNew_TrimsTrailingSlashFromBaseURL(t *testing.T) {
	// A trailing slash on PUBLIC_BASE_URL must not produce a double slash
	// ("//id") in the returned short URL.
	st, err := store.Open(filepath.Join(t.TempDir(), "test.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = st.Close() })
	srv, err := New(st, "https://go.example.com/", testAPIKey, nil)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if want := "https://go.example.com"; srv.publicBaseURL != want {
		t.Errorf("publicBaseURL = %q, want %q (trailing slash trimmed)", srv.publicBaseURL, want)
	}
}

// newServerWithClosedStore builds a Server whose underlying store is
// already closed, so Create/Lookup return a database error. Used to
// exercise the 500 branches of the create and redirect handlers without
// a mock — a closed real store surfaces a real driver error.
func newServerWithClosedStore(t *testing.T) http.Handler {
	t.Helper()
	st, err := store.Open(filepath.Join(t.TempDir(), "test.db"))
	if err != nil {
		t.Fatalf("store.Open: %v", err)
	}
	if err := st.Close(); err != nil {
		t.Fatalf("store.Close: %v", err)
	}
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	srv, err := New(st, testBaseURL, testAPIKey, logger)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return srv.Routes()
}
