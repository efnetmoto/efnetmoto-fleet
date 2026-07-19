// Package httpapi wires the URL shortener's HTTP routes onto the store.
//
// Three routes are exposed via Go 1.22+ ServeMux method+pattern matching:
//
//	POST /api/v1/links  — create a short URL (bearer-auth required)
//	GET  /{short_id}    — redirect to the stored destination (public)
//	GET  /health        — liveness probe (public)
//
// Auth wraps the create route only. The redirect and health routes are
// intentionally public.
package httpapi

import (
	"crypto/sha256"
	"errors"
	"log/slog"
	"net/http"
	"strings"

	"github.com/efnetmoto/efnetmoto-fleet/services/url-shortener/internal/store"
)

// Server holds the dependencies shared across handlers. Construct one
// with New and expose its routes via Routes.
type Server struct {
	store         *store.Store
	publicBaseURL string
	apiKeyHash    [sha256.Size]byte
	logger        *slog.Logger
}

// New builds a Server. publicBaseURL must be an absolute http or https URL
// with a host — it prefixes every returned short URL, so an invalid base
// fails loudly here rather than emitting broken URLs — and is trimmed of
// surrounding whitespace and any trailing slash. apiKey must be non-empty;
// it is hashed once so per-request comparison is constant-time and does not
// leak the key's length or a near-miss. A nil logger falls back to
// slog.Default.
func New(s *store.Store, publicBaseURL, apiKey string, logger *slog.Logger) (*Server, error) {
	if s == nil {
		return nil, errors.New("httpapi: store is required")
	}
	trimmed := strings.TrimSpace(publicBaseURL)
	if !validURL(trimmed) {
		return nil, errors.New("httpapi: public base URL must be an absolute http or https URL")
	}
	if apiKey == "" {
		return nil, errors.New("httpapi: API key is required")
	}
	if logger == nil {
		logger = slog.Default()
	}
	return &Server{
		store:         s,
		publicBaseURL: strings.TrimRight(trimmed, "/"),
		apiKeyHash:    sha256.Sum256([]byte(apiKey)),
		logger:        logger,
	}, nil
}

// Routes returns the HTTP handler with all routes wired. The returned
// *http.ServeMux uses Go 1.22+ method+pattern matching:
//
//	POST /api/v1/links  → requireAuth → createLink
//	GET  /{short_id}    → redirect
//	GET  /health        → health
//
// ServeMux precedence ensures GET /health (a literal) wins over
// GET /{short_id} (a wildcard) for the path /health, and the
// multi-segment /api/v1/links path never collides with the single-
// segment /{short_id} pattern. A path that matches a registered pattern
// but with the wrong method yields 405 Method Not Allowed automatically.
func (srv *Server) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/v1/links", srv.requireAuth(srv.createLink))
	mux.HandleFunc("GET /{short_id}", srv.redirect)
	mux.HandleFunc("GET /health", srv.health)
	return mux
}
