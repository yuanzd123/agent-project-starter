package lessons

import (
	"testing"
	"time"
)

func day(s string) time.Time {
	t, err := time.Parse("2006-01-02", s)
	if err != nil {
		panic(err)
	}
	return t
}

func TestIsDue(t *testing.T) {
	cases := []struct {
		name     string
		reviewBy string
		today    string
		want     bool
	}{
		{"before review date", "2026-12-01", "2026-11-30", false},
		{"on review date", "2026-12-01", "2026-12-01", true},
		{"after review date", "2026-12-01", "2026-12-02", true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := IsDue(day(tc.reviewBy), day(tc.today)); got != tc.want {
				t.Fatalf("IsDue(%s, %s) = %v, want %v", tc.reviewBy, tc.today, got, tc.want)
			}
		})
	}
}
