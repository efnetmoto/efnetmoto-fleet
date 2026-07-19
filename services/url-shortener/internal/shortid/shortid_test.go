package shortid

import (
	"strings"
	"testing"
)

// validChars reports whether every rune of s is in the base62 alphabet.
func validChars(s string) bool {
	for _, r := range s {
		if !strings.ContainsRune(alphabet, r) {
			return false
		}
	}
	return true
}

func TestGenerate_Length(t *testing.T) {
	cases := []int{1, 7, 16, 1000}
	for _, n := range cases {
		got, err := Generate(n)
		if err != nil {
			t.Fatalf("Generate(%d): unexpected error: %v", n, err)
		}
		if len(got) != n {
			t.Errorf("Generate(%d): length = %d, want %d", n, len(got), n)
		}
	}
}

func TestGenerate_NonPositiveReturnsEmpty(t *testing.T) {
	for _, n := range []int{0, -1, -100} {
		got, err := Generate(n)
		if err != nil {
			t.Fatalf("Generate(%d): unexpected error: %v", n, err)
		}
		if got != "" {
			t.Errorf("Generate(%d): got %q, want empty string", n, got)
		}
	}
}

func TestGenerate_AlphabetMembership(t *testing.T) {
	// A large output makes it statistically near-certain that a broken
	// modulo mapping would surface a character outside the alphabet.
	const n = 10000
	got, err := Generate(n)
	if err != nil {
		t.Fatalf("Generate(%d): unexpected error: %v", n, err)
	}
	if !validChars(got) {
		t.Errorf("Generate(%d): output contains characters outside the base62 alphabet", n)
	}
}

func TestGenerate_Coverage(t *testing.T) {
	// Over many short IDs, the generator should produce almost entirely
	// distinct values. This is a smoke test of the distribution, not a
	// statistical assertion: a broken (constant or badly biased) generator
	// would fail it, while a correct one never will at this workload.
	const runs = 2000
	const n = 7
	seen := make(map[string]struct{}, runs)
	for i := 0; i < runs; i++ {
		got, err := Generate(n)
		if err != nil {
			t.Fatalf("Generate(%d) run %d: unexpected error: %v", n, i, err)
		}
		if !validChars(got) {
			t.Fatalf("Generate(%d) run %d: invalid character in %q", n, i, got)
		}
		seen[got] = struct{}{}
	}
	// 2000 draws from a 62^7 (~3.5e12) space produce ~0 collisions, so
	// require at least 1990 distinct to catch a stuck/biased generator
	// without risking a flaky statistical floor.
	if got := len(seen); got < 1990 {
		t.Errorf("Generate(%d): only %d distinct values in %d runs, want >= 1990", n, got, runs)
	}
}

func TestGenerate_TwoConsecutiveCallsDiffer(t *testing.T) {
	// Two large generations should essentially never be equal; a
	// constant-returning generator would fail this immediately.
	const n = 32
	a, err := Generate(n)
	if err != nil {
		t.Fatalf("Generate(%d) first: unexpected error: %v", n, err)
	}
	b, err := Generate(n)
	if err != nil {
		t.Fatalf("Generate(%d) second: unexpected error: %v", n, err)
	}
	if a == b {
		t.Errorf("Generate(%d): two consecutive calls both returned %q", n, a)
	}
}
