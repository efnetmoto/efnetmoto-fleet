// Command url-shortener is a lightweight URL-shortening service.
//
// It exposes an authenticated create API (POST /api/v1/links) for trusted
// clients and a public redirect endpoint (GET /{short_id}) for resolving
// short URLs. Mappings are persisted in a SQLite database.
package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/efnetmoto/efnetmoto-fleet/services/url-shortener/internal/config"
	"github.com/efnetmoto/efnetmoto-fleet/services/url-shortener/internal/httpapi"
	"github.com/efnetmoto/efnetmoto-fleet/services/url-shortener/internal/store"
)

func main() {
	logger := slog.New(slog.NewTextHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	if err := run(); err != nil {
		logger.Error("fatal error", "error", err)
		os.Exit(1)
	}
}

// run returns an error for main to log and exit on; a nil return is a
// clean shutdown.
func run() error {
	cfg, err := config.Load()
	if err != nil {
		return fmt.Errorf("load config: %w", err)
	}
	logger := slog.Default()
	logger.Info("starting url-shortener",
		"port", cfg.Port,
		"database", cfg.DatabasePath,
		"public_base_url", cfg.PublicBaseURL,
	)

	st, err := store.Open(cfg.DatabasePath)
	if err != nil {
		return fmt.Errorf("open store: %w", err)
	}
	defer func() {
		if cerr := st.Close(); cerr != nil {
			logger.Error("close store", "error", cerr)
		}
	}()

	srv, err := httpapi.New(st, cfg.PublicBaseURL, cfg.APIKey, logger)
	if err != nil {
		return fmt.Errorf("build http server: %w", err)
	}

	addr := fmt.Sprintf(":%d", cfg.Port)
	httpServer := &http.Server{
		Addr:              addr,
		Handler:           srv.Routes(),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	// http.ErrServerClosed is expected on clean shutdown and filtered
	// out; a bind failure (e.g. port in use) surfaces on errCh.
	errCh := make(chan error, 1)
	go func() {
		logger.Info("listening", "addr", addr)
		if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
		}
	}()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT)

	select {
	case err := <-errCh:
		return fmt.Errorf("http server: %w", err)
	case sig := <-sigCh:
		logger.Info("shutdown signal received", "signal", sig.String())
	}

	// Give in-flight requests up to 10s to complete before forcing close.
	// The store is closed by the deferred call after run returns.
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := httpServer.Shutdown(ctx); err != nil {
		return fmt.Errorf("http shutdown: %w", err)
	}
	logger.Info("shutdown complete")
	return nil
}
