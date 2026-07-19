package httpapi

import (
	"encoding/json"
	"net/http"
)

type errorBody struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

// errorEnvelope wraps an errorBody under the "error" key, yielding the
// error response body shape used by every failure path:
//
//	{"error":{"code":"...","message":"..."}}
type errorEnvelope struct {
	Error errorBody `json:"error"`
}

// writeJSON encodes v as JSON with the given status. Content-Type is set
// before WriteHeader so clients see application/json. An encode failure
// (almost always a client disconnect) is logged at Debug level — there is
// nothing useful to do once headers are written.
func (srv *Server) writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		srv.logger.Debug("failed to write response", "error", err)
	}
}

func (srv *Server) writeError(w http.ResponseWriter, status int, code, message string) {
	srv.writeJSON(w, status, errorEnvelope{Error: errorBody{Code: code, Message: message}})
}
