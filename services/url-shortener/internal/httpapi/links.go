package httpapi

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/url"
)

// maxBodyBytes caps the size of a create request body. A create payload is
// a tiny JSON object {"url":"..."}; 1 MiB is far beyond any legitimate URL
// while bounding memory exposure on the authed write path.
const maxBodyBytes = 1 << 20

type createRequest struct {
	URL string `json:"url"`
}

// createResponse is the 201 body. URL is the complete public short URL —
// the Search Bot uses this field directly and never constructs the short
// URL itself.
type createResponse struct {
	ID  string `json:"id"`
	URL string `json:"url"`
}

// createLink handles POST /api/v1/links: validate the JSON body and
// destination URL (syntactic only — no outbound fetch), persist via the
// store, and return 201 with the short URL. The destination URL is never
// logged; only the generated short ID is recorded on success.
func (srv *Server) createLink(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, maxBodyBytes)
	var req createRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		var maxErr *http.MaxBytesError
		if errors.As(err, &maxErr) {
			srv.logger.Warn("request body too large")
			srv.writeError(w, http.StatusRequestEntityTooLarge, "invalid_request", "Request body too large")
			return
		}
		// Log a stable error kind, not the raw error: json error messages
		// can include a byte from the request body (e.g. the offending
		// character). Logging the kind keeps request content out of the
		// logs; it is enough for debugging.
		srv.logger.Warn("invalid request body", "kind", jsonErrorKind(err))
		srv.writeError(w, http.StatusBadRequest, "invalid_request", "Request body must be valid JSON")
		return
	}
	if !validURL(req.URL) {
		srv.logger.Warn("invalid destination URL")
		srv.writeError(w, http.StatusBadRequest, "invalid_request", "A valid URL is required")
		return
	}
	link, err := srv.store.Create(r.Context(), req.URL)
	if err != nil {
		srv.logger.Error("store create failed", "error", err)
		srv.writeError(w, http.StatusInternalServerError, "internal_error", "Failed to create short URL")
		return
	}
	srv.logger.Info("Created short URL", "id", link.ShortID)
	srv.writeJSON(w, http.StatusCreated, createResponse{
		ID:  link.ShortID,
		URL: srv.publicBaseURL + "/" + link.ShortID,
	})
}

// validURL reports whether s is an absolute http or https URL with a
// non-empty host. Syntactic validation only — no DNS, no fetch. Rejects
// javascript:, data:, file:, ftp:, and schemeless/relative URLs.
func validURL(s string) bool {
	if s == "" {
		return false
	}
	u, err := url.Parse(s)
	if err != nil {
		return false
	}
	if u.Scheme != "http" && u.Scheme != "https" {
		return false
	}
	if u.Host == "" {
		return false
	}
	return true
}

// jsonErrorKind returns a short, stable classification of a JSON decode
// error for logging. It deliberately returns only the kind, never the raw
// error string: json error messages can include a byte of the request body,
// which should not be echoed into the logs.
func jsonErrorKind(err error) string {
	switch {
	case errors.Is(err, io.ErrUnexpectedEOF):
		return "unexpected_eof"
	case errors.Is(err, io.EOF):
		return "empty_body"
	}
	var syntaxErr *json.SyntaxError
	if errors.As(err, &syntaxErr) {
		return "syntax_error"
	}
	var typeErr *json.UnmarshalTypeError
	if errors.As(err, &typeErr) {
		return "type_error"
	}
	return "decode_error"
}
