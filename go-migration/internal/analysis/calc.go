package analysis

import "github.com/kwanRoshi/B/go-migration/internal/types"

// SMA calculates Simple Moving Average
func SMA(history *types.PriceHistory, period int) float64 {
	var sum float64
	count := 0

	history.Range(func(level *types.PriceLevel) bool {
		if count >= period {
			return false
		}
		sum += level.Price
		count++
		return true
	})

	if count == 0 {
		return 0
	}
	return sum / float64(count)
}

// EMA calculates Exponential Moving Average
func EMA(history *types.PriceHistory, period int) float64 {
	multiplier := 2.0 / float64(period+1)
	var ema float64

	// Initialize EMA with SMA
	ema = SMA(history, period)

	// Calculate EMA
	history.Range(func(level *types.PriceLevel) bool {
		ema = (level.Price-ema)*multiplier + ema
		return true
	})

	return ema
}
