package httpapi

import (
	"crypto/sha256"
	"crypto/subtle"
	"net/http"
	"strings"
)

// bearerPrefix is the Bearer scheme (RFC 6750) the create API accepts.
// Matching is exact (case-sensitive) rather than case-insensitive: the
// only client is the Search Bot, which follows the contract, and
// strictness is simpler and safer here.
const bearerPrefix = "Bearer "

// authorized reports whether r carries a valid bearer token matching the
// configured API key. Comparison is constant-time via SHA-256 hashing of
// both the supplied token and the configured key, so the response leaks
// neither the key's length nor a near-miss. A missing header, a wrong
// scheme, or a wrong token all return false; the caller renders the
// identical generic 401 body for every false case.
func (srv *Server) authorized(r *http.Request) bool {
	h := r.Header.Get("Authorization")
	if !strings.HasPrefix(h, bearerPrefix) {
		return false
	}
	token := h[len(bearerPrefix):]
	tokenHash := sha256.Sum256([]byte(token))
	return subtle.ConstantTimeCompare(tokenHash[:], srv.apiKeyHash[:]) == 1
}

// requireAuth wraps next with bearer-token auth. On failure it logs the
// path (never the Authorization value) and writes the generic 401 body
// used for every failure mode.
func (srv *Server) requireAuth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !srv.authorized(r) {
			srv.logger.Warn("authentication failed", "path", r.URL.Path)
			srv.writeError(w, http.StatusUnauthorized, "unauthorized", "Authentication required")
			return
		}
		next(w, r)
	}
}
