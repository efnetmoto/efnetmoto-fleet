// Package shortid generates short, URL-safe identifiers using a base62
// alphabet backed by crypto/rand.
//
// Generate is a pure utility — it knows nothing about persistence or
// uniqueness. Collision handling (retry-on-duplicate) is a persistence
// concern and lives in the store package, which relies on a UNIQUE database
// constraint rather than an application-level check-then-act pre-check.
package shortid

import (
	"crypto/rand"
	"errors"
	"fmt"
)

const alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

// alphabetLen is the base62 size. A byte has 256 values; 256 = 4*62 + 8,
// so a modulo mapping biases slightly toward the first eight characters;
// see Generate for why that is acceptable here.
const alphabetLen = 62

// ErrGenerationFailed is returned by Generate when the system's secure
// random source cannot be read. crypto/rand failure indicates a broken
// host and has no safe fallback for identifiers that must be unique and
// not easily guessable; callers should treat this as a hard failure
// rather than degrading to an insecure source.
var ErrGenerationFailed = errors.New("shortid: secure random source unavailable")

// Generate returns a random base62 string of length n backed by
// crypto/rand. It does not guarantee uniqueness — uniqueness is enforced
// by the caller (the store) via a database UNIQUE constraint with retry.
//
// A modulo mapping selects each character from a random byte. Because 62
// does not divide 256 evenly, this introduces a slight (~3%) bias toward
// the leading alphabet characters. This is acceptable for this service:
// short IDs are public and non-secret, uniqueness is enforced at the
// database layer, and the 62^7 (~3.5 trillion) space is many orders of
// magnitude larger than the expected workload. Cryptographic uniformity
// is not a property this system requires; predictable uniqueness is.
func Generate(n int) (string, error) {
	if n <= 0 {
		return "", nil
	}
	buf := make([]byte, n)
	if _, err := rand.Read(buf); err != nil {
		return "", fmt.Errorf("%w: %v", ErrGenerationFailed, err)
	}
	out := make([]byte, n)
	for i, b := range buf {
		out[i] = alphabet[b%alphabetLen]
	}
	return string(out), nil
}
