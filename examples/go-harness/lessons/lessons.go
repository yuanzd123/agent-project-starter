// Package lessons is a tiny stand-in for application code. It mirrors the
// starter's idea that a lesson has a review date: once that date is reached,
// the lesson is "due" and should be revalidated instead of trusted blindly.
package lessons

import "time"

// IsDue reports whether a lesson reviewed-by date has been reached.
// A lesson is due on its review date, not only after it.
func IsDue(reviewBy, today time.Time) bool {
	return !today.Before(reviewBy)
}
