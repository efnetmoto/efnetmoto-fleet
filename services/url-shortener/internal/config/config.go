// Package config loads the url-shortener's startup configuration from
// environment variables.
//
// Configuration is read once at startup (no live-reload) and validated
// eagerly — missing or invalid required values cause a non-zero exit with
// a descriptive log line before the process begins serving.
package config

import (
	"errors"
	"fmt"
	"os"
	"strconv"
)

type Config struct {
	Port          int
	DatabasePath  string
	PublicBaseURL string
	APIKey        string
}

const defaultPort = 8080

// Load reads configuration from environment variables and returns all
// validation errors together, so a misconfigured deployment reports
// every problem at once rather than one per restart.
func Load() (Config, error) {
	var errs []error

	port, err := loadPort(os.Getenv("PORT"))
	if err != nil {
		errs = append(errs, err)
	}

	dbPath := os.Getenv("DATABASE_PATH")
	if dbPath == "" {
		errs = append(errs, errors.New("DATABASE_PATH is required"))
	}

	baseURL := os.Getenv("PUBLIC_BASE_URL")
	if baseURL == "" {
		errs = append(errs, errors.New("PUBLIC_BASE_URL is required"))
	}

	apiKey := os.Getenv("API_KEY")
	if apiKey == "" {
		errs = append(errs, errors.New("API_KEY is required"))
	}

	if len(errs) > 0 {
		return Config{}, fmt.Errorf("config: %w", errors.Join(errs...))
	}

	return Config{
		Port:          port,
		DatabasePath:  dbPath,
		PublicBaseURL: baseURL,
		APIKey:        apiKey,
	}, nil
}

func loadPort(s string) (int, error) {
	if s == "" {
		return defaultPort, nil
	}
	port, err := strconv.Atoi(s)
	if err != nil {
		return 0, fmt.Errorf("PORT %q: must be an integer", s)
	}
	if port < 1 || port > 65535 {
		return 0, fmt.Errorf("PORT %d: must be between 1 and 65535", port)
	}
	return port, nil
}
