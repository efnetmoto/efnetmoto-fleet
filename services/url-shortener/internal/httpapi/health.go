package httpapi

import "net/http"

type healthResponse struct {
	Status string `json:"status"`
}

// health handles GET /health, returning 200 with {"status":"ok"}. This is a
// liveness probe: if the process answers, it is alive. A deeper readiness
// check (e.g. pinging the database) is intentionally not implemented for
// the initial service — the store is opened at startup, so a responding
// process implies a usable database.
func (srv *Server) health(w http.ResponseWriter, r *http.Request) {
	srv.writeJSON(w, http.StatusOK, healthResponse{Status: "ok"})
}
