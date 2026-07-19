package config

import (
	"strings"
	"testing"
)

// validEnv sets all config env vars to valid values. Tests override
// specific vars (to "" for missing cases, or to an invalid value) after
// calling this. t.Setenv saves and restores each var automatically, so
// tests neither pollute each other nor leak into the real environment.
func validEnv(t *testing.T) {
	t.Helper()
	t.Setenv("PORT", "8080")
	t.Setenv("DATABASE_PATH", "/data/shortener.db")
	t.Setenv("PUBLIC_BASE_URL", "https://go.example.com")
	t.Setenv("API_KEY", "secret-key")
}

func TestLoad_Success(t *testing.T) {
	validEnv(t)
	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: unexpected error: %v", err)
	}
	if cfg.Port != 8080 {
		t.Errorf("Port = %d, want 8080", cfg.Port)
	}
	if cfg.DatabasePath != "/data/shortener.db" {
		t.Errorf("DatabasePath = %q, want /data/shortener.db", cfg.DatabasePath)
	}
	if cfg.PublicBaseURL != "https://go.example.com" {
		t.Errorf("PublicBaseURL = %q, want https://go.example.com", cfg.PublicBaseURL)
	}
	if cfg.APIKey != "secret-key" {
		t.Errorf("APIKey = %q, want secret-key", cfg.APIKey)
	}
}

func TestLoad_DefaultPort(t *testing.T) {
	validEnv(t)
	t.Setenv("PORT", "")
	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: unexpected error: %v", err)
	}
	if cfg.Port != defaultPort {
		t.Errorf("Port = %d, want default %d", cfg.Port, defaultPort)
	}
}

func TestLoad_MissingDatabasePath(t *testing.T) {
	validEnv(t)
	t.Setenv("DATABASE_PATH", "")
	_, err := Load()
	if err == nil {
		t.Fatal("Load succeeded with missing DATABASE_PATH; want error")
	}
	if !strings.Contains(err.Error(), "DATABASE_PATH") {
		t.Errorf("error = %q, want mention of DATABASE_PATH", err)
	}
}

func TestLoad_MissingPublicBaseURL(t *testing.T) {
	validEnv(t)
	t.Setenv("PUBLIC_BASE_URL", "")
	_, err := Load()
	if err == nil {
		t.Fatal("Load succeeded with missing PUBLIC_BASE_URL; want error")
	}
	if !strings.Contains(err.Error(), "PUBLIC_BASE_URL") {
		t.Errorf("error = %q, want mention of PUBLIC_BASE_URL", err)
	}
}

func TestLoad_MissingAPIKey(t *testing.T) {
	// Security: a missing API key must prevent startup so the service
	// never runs in a state where the create API is effectively
	// unauthenticated (New would reject an empty key, but failing at
	// config load gives a clearer, earlier error).
	validEnv(t)
	t.Setenv("API_KEY", "")
	_, err := Load()
	if err == nil {
		t.Fatal("Load succeeded with missing API_KEY; want error")
	}
	if !strings.Contains(err.Error(), "API_KEY") {
		t.Errorf("error = %q, want mention of API_KEY", err)
	}
}

func TestLoad_AllMissing_ReportsAllErrors(t *testing.T) {
	// Every required var missing: the error should mention each one so
	// the operator can fix them all in one pass.
	t.Setenv("PORT", "")
	t.Setenv("DATABASE_PATH", "")
	t.Setenv("PUBLIC_BASE_URL", "")
	t.Setenv("API_KEY", "")
	_, err := Load()
	if err == nil {
		t.Fatal("Load succeeded with all vars missing; want error")
	}
	for _, want := range []string{"DATABASE_PATH", "PUBLIC_BASE_URL", "API_KEY"} {
		if !strings.Contains(err.Error(), want) {
			t.Errorf("error = %q, missing mention of %s", err, want)
		}
	}
}

func TestLoad_InvalidPort_NonNumeric(t *testing.T) {
	validEnv(t)
	t.Setenv("PORT", "not-a-number")
	_, err := Load()
	if err == nil {
		t.Fatal("Load succeeded with non-numeric PORT; want error")
	}
	if !strings.Contains(err.Error(), "PORT") {
		t.Errorf("error = %q, want mention of PORT", err)
	}
}

func TestLoad_InvalidPort_OutOfRange(t *testing.T) {
	for _, p := range []string{"0", "-1", "65536", "99999"} {
		t.Run(p, func(t *testing.T) {
			validEnv(t)
			t.Setenv("PORT", p)
			_, err := Load()
			if err == nil {
				t.Fatalf("Load succeeded with PORT=%s; want error", p)
			}
			if !strings.Contains(err.Error(), "PORT") {
				t.Errorf("error = %q, want mention of PORT", err)
			}
		})
	}
}

func TestLoad_ValidPort_Range(t *testing.T) {
	for _, p := range []string{"1", "80", "8080", "65535"} {
		t.Run(p, func(t *testing.T) {
			validEnv(t)
			t.Setenv("PORT", p)
			if _, err := Load(); err != nil {
				t.Fatalf("Load with PORT=%s: unexpected error: %v", p, err)
			}
		})
	}
}
