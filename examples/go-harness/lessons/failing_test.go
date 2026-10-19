//go:build failing

// This file is compiled only with `-tags failing`. It asserts something that is
// deliberately wrong so you can see the harness report a failed check.
// Never register the tagged command as a required check in a real project.

package lessons

import "testing"

func TestIntentionallyFailing(t *testing.T) {
	// A lesson is due ON its review date, so this expectation is wrong on purpose.
	if IsDue(day("2026-12-01"), day("2026-12-01")) {
		t.Fatal("intentional failure: demonstrates a nonzero check result")
	}
}
