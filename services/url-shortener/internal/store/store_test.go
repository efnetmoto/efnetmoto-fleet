package store

import (
	"context"
	"errors"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"
)

// newTestStore opens a Store backed by a fresh temp-file SQLite database.
// The DB file lives under t.TempDir() and is removed when the test ends.
// Using a real temp file (rather than :memory:) exercises file-based
// persistence, which is what the service uses in production.
func newTestStore(t *testing.T, opts ...Option) *Store {
	t.Helper()
	path := filepath.Join(t.TempDir(), "test.db")
	s, err := Open(path, opts...)
	if err != nil {
		t.Fatalf("Open(%q): %v", path, err)
	}
	t.Cleanup(func() {
		if err := s.Close(); err != nil {
			t.Errorf("Close: %v", err)
		}
	})
	return s
}

func TestOpen_SchemaIdempotent(t *testing.T) {
	// Opening a fresh path creates the schema; reopening the same path
	// (CREATE TABLE IF NOT EXISTS) must not error and the DB must remain
	// usable.
	path := filepath.Join(t.TempDir(), "test.db")
	s1, err := Open(path)
	if err != nil {
		t.Fatalf("Open (first): %v", err)
	}
	if err := s1.Close(); err != nil {
		t.Fatalf("Close (first): %v", err)
	}
	s2, err := Open(path)
	if err != nil {
		t.Fatalf("Open (second): %v", err)
	}
	t.Cleanup(func() {
		if err := s2.Close(); err != nil {
			t.Errorf("Close (second): %v", err)
		}
	})

	link, err := s2.Create(context.Background(), "https://example.com/a")
	if err != nil {
		t.Fatalf("Create after reopen: %v", err)
	}
	if _, err := s2.Lookup(context.Background(), link.ShortID); err != nil {
		t.Fatalf("Lookup after reopen: %v", err)
	}
}

func TestCreate_Lookup_RoundTrip(t *testing.T) {
	s := newTestStore(t)
	ctx := context.Background()

	const url = "https://example.com/a/very/long/path?query=value"
	link, err := s.Create(ctx, url)
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if link.ShortID == "" {
		t.Fatal("Create returned empty ShortID")
	}
	if link.DestinationURL != url {
		t.Errorf("DestinationURL = %q, want %q", link.DestinationURL, url)
	}
	if link.CreatedAt.IsZero() {
		t.Error("CreatedAt is zero")
	}

	got, err := s.Lookup(ctx, link.ShortID)
	if err != nil {
		t.Fatalf("Lookup(%q): %v", link.ShortID, err)
	}
	if got.ShortID != link.ShortID {
		t.Errorf("Lookup ShortID = %q, want %q", got.ShortID, link.ShortID)
	}
	if got.DestinationURL != url {
		t.Errorf("Lookup DestinationURL = %q, want %q", got.DestinationURL, url)
	}
	if got.ID == 0 {
		t.Error("Lookup ID is zero")
	}
	// Create must populate the DB-assigned ID, matching what Lookup reads
	// back, so both return a consistent record.
	if link.ID == 0 {
		t.Error("Create returned zero ID; want the DB-assigned autoincrement")
	}
	if link.ID != got.ID {
		t.Errorf("Create ID = %d, Lookup ID = %d (must match)", link.ID, got.ID)
	}
	// RFC3339 has second precision; the round-trip should match within
	// a second of the in-memory value returned by Create.
	if diff := got.CreatedAt.Sub(link.CreatedAt); diff > time.Second || diff < -time.Second {
		t.Errorf("Lookup CreatedAt = %v, want ~%v (diff %v)", got.CreatedAt, link.CreatedAt, diff)
	}
}

func TestCreate_GeneratesDistinctIDs(t *testing.T) {
	s := newTestStore(t)
	ctx := context.Background()

	const n = 50
	seen := make(map[string]struct{}, n)
	for i := 0; i < n; i++ {
		link, err := s.Create(ctx, "https://example.com/"+strconv.Itoa(i))
		if err != nil {
			t.Fatalf("Create #%d: %v", i, err)
		}
		if _, dup := seen[link.ShortID]; dup {
			t.Fatalf("duplicate ShortID %q at iteration %d", link.ShortID, i)
		}
		seen[link.ShortID] = struct{}{}
	}
}

func TestCreate_CollisionRetry_Succeeds(t *testing.T) {
	// Deterministic collision test: the generator returns three IDs that
	// are already present (each colliding once), then a unique one. Create
	// must retry past the collisions and return the unique ID, having
	// invoked the generator exactly four times.
	s := newTestStore(t)
	ctx := context.Background()

	calls := 0
	collisions := []string{"collide1", "collide2", "collide3"}
	const unique = "unique1"
	s.generate = func(int) (string, error) {
		calls++
		if calls <= len(collisions) {
			return collisions[calls-1], nil
		}
		return unique, nil
	}

	// Pre-insert the collision IDs so the generator's repeated values hit
	// the UNIQUE constraint and force a retry.
	for _, c := range collisions {
		if _, err := s.db.ExecContext(ctx,
			`INSERT INTO links (short_id, destination_url, created_at) VALUES (?, ?, ?)`,
			c, "https://example.com/seed/"+c, time.Now().UTC().Format(time.RFC3339),
		); err != nil {
			t.Fatalf("seed insert %q: %v", c, err)
		}
	}

	link, err := s.Create(ctx, "https://example.com/x")
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if link.ShortID != unique {
		t.Errorf("ShortID = %q, want %q (after retrying past collisions)", link.ShortID, unique)
	}
	if calls != 4 {
		t.Errorf("generator called %d times, want 4 (3 collisions + 1 unique)", calls)
	}

	// The persisted link must be retrievable by the returned ID.
	if _, err := s.Lookup(ctx, unique); err != nil {
		t.Errorf("Lookup(%q) after retry: %v", unique, err)
	}
}

func TestCreate_CollisionExhaustedRetries(t *testing.T) {
	// Generator always returns the same ID, which is already present, so
	// every attempt collides. Create must give up with ErrExhaustedRetries
	// rather than overwriting the existing mapping.
	s := newTestStore(t)
	ctx := context.Background()

	const dup = "dup-id"
	if _, err := s.db.ExecContext(ctx,
		`INSERT INTO links (short_id, destination_url, created_at) VALUES (?, ?, ?)`,
		dup, "https://example.com/pre", time.Now().UTC().Format(time.RFC3339),
	); err != nil {
		t.Fatalf("seed insert: %v", err)
	}
	s.generate = func(int) (string, error) { return dup, nil }

	_, err := s.Create(ctx, "https://example.com/y")
	if !errors.Is(err, ErrExhaustedRetries) {
		t.Fatalf("Create err = %v, want ErrExhaustedRetries", err)
	}

	// The pre-existing mapping must be untouched — never overwritten due
	// to a short-ID collision.
	got, err := s.Lookup(ctx, dup)
	if err != nil {
		t.Fatalf("Lookup(%q) after exhaustion: %v", dup, err)
	}
	if got.DestinationURL != "https://example.com/pre" {
		t.Errorf("existing mapping overwritten: DestinationURL = %q, want %q",
			got.DestinationURL, "https://example.com/pre")
	}
}

func TestCreate_GeneratorError(t *testing.T) {
	// A generator failure is not a collision; Create must surface it
	// immediately without retrying.
	s := newTestStore(t)
	ctx := context.Background()

	calls := 0
	s.generate = func(int) (string, error) {
		calls++
		return "", errors.New("generator broken")
	}
	_, err := s.Create(ctx, "https://example.com/z")
	if err == nil {
		t.Fatal("Create: expected error from generator failure, got nil")
	}
	if !strings.Contains(err.Error(), "generator broken") {
		t.Errorf("Create err = %q, want it to wrap the generator error", err)
	}
	if calls != 1 {
		t.Errorf("generator called %d times, want 1 (generator failure must not retry)", calls)
	}
}

func TestLookup_NotFound(t *testing.T) {
	s := newTestStore(t)
	ctx := context.Background()

	_, err := s.Lookup(ctx, "does-not-exist")
	if !errors.Is(err, ErrNotFound) {
		t.Errorf("Lookup err = %v, want ErrNotFound", err)
	}
}

func TestLookup_EmptyShortID(t *testing.T) {
	s := newTestStore(t)
	ctx := context.Background()

	_, err := s.Lookup(ctx, "")
	if !errors.Is(err, ErrNotFound) {
		t.Errorf("Lookup(\"\") err = %v, want ErrNotFound", err)
	}
}
