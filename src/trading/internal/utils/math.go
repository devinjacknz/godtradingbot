package utils

// Abs returns the absolute value of x
func Abs(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}

// Min returns the smaller of x or y
func Min(x, y float64) float64 {
	if x < y {
		return x
	}
	return y
}

// Max returns the larger of x or y
func Max(x, y float64) float64 {
	if x > y {
		return x
	}
	return y
}

// Clamp returns x clamped to the inclusive range [min, max]
func Clamp(x, min, max float64) float64 {
	if x < min {
		return min
	}
	if x > max {
		return max
	}
	return x
}
