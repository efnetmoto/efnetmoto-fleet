package httpapi

import (
	"errors"
	"net/http"

	"github.com/efnetmoto/efnetmoto-fleet/services/url-shortener/internal/store"
)

// redirect handles GET /{short_id}: 302 to the stored destination on a
// hit, 404 on a miss. No outbound request is made to the destination —
// the stored URL is emitted verbatim in Location.
func (srv *Server) redirect(w http.ResponseWriter, r *http.Request) {
	shortID := r.PathValue("short_id")
	link, err := srv.store.Lookup(r.Context(), shortID)
	if err != nil {
		if errors.Is(err, store.ErrNotFound) {
			srv.logger.Info("redirect miss", "id", shortID)
			srv.writeError(w, http.StatusNotFound, "not_found", "Short URL not found")
			return
		}
		srv.logger.Error("store lookup failed", "error", err, "id", shortID)
		srv.writeError(w, http.StatusInternalServerError, "internal_error", "Failed to resolve short URL")
		return
	}
	http.Redirect(w, r, link.DestinationURL, http.StatusFound)
}
