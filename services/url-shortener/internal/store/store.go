// Package store provides a SQLite-backed persistence layer for short URL
// mappings.
//
// The store owns schema initialization, short-ID generation with
// collision-retry (uniqueness enforced by a database UNIQUE constraint,
// not an application-level check-then-act), and lookups. It is the only
// component that knows about the storage technology; the HTTP layer
// depends on this package's typed errors and Link type rather than on
// SQLite directly.
package store

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"

	_ "modernc.org/sqlite" // pure-Go SQLite driver; CGO-free build

	"github.com/efnetmoto/efnetmoto-fleet/services/url-shortener/internal/shortid"
)

// ErrNotFound is returned by Lookup when no stored link matches the
// requested short ID. Callers should use errors.Is to test for it.
var ErrNotFound = errors.New("store: link not found")

// ErrExhaustedRetries is returned by Create when the short-ID generator
// could not produce a unique ID within the configured attempt budget.
// Under normal operation this should be effectively unobserved — the
// 62^7 (~3.5 trillion) space is many orders of magnitude larger than the
// expected workload. The bounded retry is a safety net for the
// pathological case (e.g. a near-full ID space), not an expectation.
var ErrExhaustedRetries = errors.New("store: exhausted retries generating unique short ID")

// maxAttempts is five: generous for a 7-char base62 space, tight enough
// to fail fast in a test that fills a tiny ID space.
const maxAttempts = 5

// defaultIDLen is the short ID length used when WithIDLength is not
// applied. Seven base62 characters give 62^7 (~3.5 trillion) possible IDs,
// ample for this service's lifetime at the expected scale.
const defaultIDLen = 7

// schema creates the links table if missing; re-running Open on an
// existing database is idempotent. created_at is stored as RFC3339 text
// and set by the application, not by SQLite defaults.
//
// No secondary index on short_id is needed: the UNIQUE constraint on
// short_id already creates the B-tree that serves every WHERE short_id = ?
// lookup, so a separate index would only add per-insert write cost for no
// query benefit. DROP INDEX converges databases created by an earlier
// schema (which carried a redundant explicit index) onto the intended
// state.
const schema = `
CREATE TABLE IF NOT EXISTS links (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    short_id        TEXT NOT NULL UNIQUE,
    destination_url TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
DROP INDEX IF EXISTS idx_links_short_id;
`

type Link struct {
	ID             int64
	ShortID        string
	DestinationURL string
	CreatedAt      time.Time
}

// Store is opened with Open and must be Closed when done.
type Store struct {
	db    *sql.DB
	idLen int
	// generate produces a candidate short ID. It defaults to
	// shortid.Generate and is overridable via the WithGenerator option
	// (primarily by tests, to force deterministic collision behavior).
	generate func(int) (string, error)
}

type Option func(*Store)

// WithIDLength overrides the default short ID length (7). Useful for
// tests that need a small ID space to exercise collision behavior. This
// constrains the *real* generator's space (probabilistic collisions);
// WithGenerator instead injects a fake generator for deterministic
// collision/retry behavior — the two are complementary, not redundant.
func WithIDLength(n int) Option {
	return func(s *Store) { s.idLen = n }
}

// WithGenerator overrides the short-ID generator. It defaults to
// shortid.Generate; tests pass a deterministic generator to force
// collision/retry behavior without depending on randomness. This is the
// public seam for varying ID generation — construction and test paths
// share it, so there is no divergence between them.
func WithGenerator(fn func(int) (string, error)) Option {
	return func(s *Store) { s.generate = fn }
}

// Open creates and initializes a Store backed by a SQLite database file
// at path. The schema is created if missing; calling Open on an existing
// database is idempotent.
//
// A single underlying connection is used to serialize writes cleanly and
// avoid SQLITE_BUSY under the single-client (Pompone) workload — this
// service's redirect reads and occasional inserts are well within what
// one connection handles, and the simplicity is preferable to WAL mode
// or a connection pool for the expected workload.
func Open(path string, opts ...Option) (*Store, error) {
	db, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, fmt.Errorf("store: open %q: %w", path, err)
	}
	db.SetMaxOpenConns(1)

	s := &Store{
		db:       db,
		idLen:    defaultIDLen,
		generate: shortid.Generate,
	}
	for _, opt := range opts {
		opt(s)
	}

	if err := s.initSchema(context.Background()); err != nil {
		_ = db.Close()
		return nil, err
	}
	return s, nil
}

func (s *Store) initSchema(ctx context.Context) error {
	if _, err := s.db.ExecContext(ctx, schema); err != nil {
		return fmt.Errorf("store: init schema: %w", err)
	}
	return nil
}

// Close is safe to call on a Store whose Open failed after partial setup.
func (s *Store) Close() error {
	if s.db == nil {
		return nil
	}
	return s.db.Close()
}

// Create persists a new short URL mapping for destinationURL, generating
// a unique short ID with retry on collision. It returns the stored Link,
// including the database-assigned ID, the generated ShortID, and the
// CreatedAt timestamp.
//
// Uniqueness is enforced by the UNIQUE constraint on links.short_id. On a
// collision the insert fails with a UNIQUE-constraint error and Create
// retries with a fresh ID, up to maxAttempts times. Any other database
// error (not a collision) is returned immediately without retry, and a
// generator failure is surfaced directly rather than treated as a
// collision.
func (s *Store) Create(ctx context.Context, destinationURL string) (*Link, error) {
	var lastErr error
	for attempt := 0; attempt < maxAttempts; attempt++ {
		id, err := s.generate(s.idLen)
		if err != nil {
			return nil, fmt.Errorf("store: generate short id: %w", err)
		}
		now := time.Now().UTC().Truncate(time.Second)
		result, err := s.db.ExecContext(ctx,
			`INSERT INTO links (short_id, destination_url, created_at) VALUES (?, ?, ?)`,
			id, destinationURL, now.Format(time.RFC3339),
		)
		if err != nil {
			if isUniqueConstraintErr(err) {
				lastErr = err
				continue
			}
			return nil, fmt.Errorf("store: insert: %w", err)
		}
		// Populate ID so Create returns a record consistent with
		// Lookup's, without a follow-up query.
		insertID, idErr := result.LastInsertId()
		if idErr != nil {
			return nil, fmt.Errorf("store: read insert id: %w", idErr)
		}
		return &Link{
			ID:             insertID,
			ShortID:        id,
			DestinationURL: destinationURL,
			CreatedAt:      now,
		}, nil
	}
	return nil, fmt.Errorf("%w: last error: %v", ErrExhaustedRetries, lastErr)
}

// Lookup returns the stored Link for shortID, or ErrNotFound if no link
// matches.
func (s *Store) Lookup(ctx context.Context, shortID string) (*Link, error) {
	var (
		l       Link
		created string
	)
	err := s.db.QueryRowContext(ctx,
		`SELECT id, short_id, destination_url, created_at FROM links WHERE short_id = ?`,
		shortID,
	).Scan(&l.ID, &l.ShortID, &l.DestinationURL, &created)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("store: lookup %q: %w", shortID, err)
	}
	l.CreatedAt, err = time.Parse(time.RFC3339, created)
	if err != nil {
		return nil, fmt.Errorf("store: parse created_at %q: %w", created, err)
	}
	return &l, nil
}

// isUniqueConstraintErr detects a SQLite UNIQUE-constraint violation by
// matching the stable phrase "UNIQUE constraint failed" in the error
// text. Both modernc.org/sqlite (the chosen pure-Go driver) and
// mattn/go-sqlite3 surface SQLite's own error message, so matching the
// text keeps the store agnostic to the driver's typed error API and
// allows swapping drivers later.
func isUniqueConstraintErr(err error) bool {
	if err == nil {
		return false
	}
	return strings.Contains(err.Error(), "UNIQUE constraint failed")
}
