package analysis

import (
	"fmt"
	"math"

	"github.com/kwanRoshi/B/go-migration/internal/types"
)

// IndicatorCalculator represents a technical indicator calculator
type IndicatorCalculator interface {
	Name() string
	Value() float64
	Params() interface{}
	Calculate(history *types.PriceHistory) error
}

// BaseIndicator provides common functionality for indicators
type BaseIndicator struct {
	name  string
	value float64
}

func (i *BaseIndicator) Name() string {
	return i.name
}

func (i *BaseIndicator) Value() float64 {
	return i.value
}

// RSIIndicator implements RSI calculation
type RSIIndicator struct {
	BaseIndicator
	period int
}

// NewRSIIndicator creates a new RSI indicator
func NewRSIIndicator(period int) *RSIIndicator {
	return &RSIIndicator{
		BaseIndicator: BaseIndicator{name: "RSI"},
		period:        period,
	}
}

func (i *RSIIndicator) Params() interface{} {
	return map[string]interface{}{
		"period": i.period,
	}
}

func (i *RSIIndicator) Calculate(history *types.PriceHistory) error {
	if history.Len() < i.period {
		return fmt.Errorf("insufficient data for RSI calculation")
	}

	var gains, losses float64
	var prevPrice float64
	firstPrice := true
	count := 0

	history.Range(func(level *types.PriceLevel) bool {
		if count >= i.period {
			return false
		}

		if firstPrice {
			prevPrice = level.Price
			firstPrice = false
			return true
		}

		change := level.Price - prevPrice
		if change > 0 {
			gains += change
		} else {
			losses -= change
		}
		count++
		prevPrice = level.Price
		return true
	})

	avgGain := gains / float64(i.period)
	avgLoss := losses / float64(i.period)

	if avgLoss == 0 {
		i.value = 100
		return nil
	}

	rs := avgGain / avgLoss
	i.value = 100 - (100 / (1 + rs))

	return nil
}

// MACDIndicator implements MACD calculation
type MACDIndicator struct {
	BaseIndicator
	fastPeriod   int
	slowPeriod   int
	signalPeriod int
	signal       float64
}

// NewMACDIndicator creates a new MACD indicator
func NewMACDIndicator(fastPeriod, slowPeriod, signalPeriod int) *MACDIndicator {
	return &MACDIndicator{
		BaseIndicator: BaseIndicator{name: "MACD"},
		fastPeriod:    fastPeriod,
		slowPeriod:    slowPeriod,
		signalPeriod:  signalPeriod,
	}
}

func (i *MACDIndicator) Params() interface{} {
	return map[string]interface{}{
		"fast_period":   i.fastPeriod,
		"slow_period":   i.slowPeriod,
		"signal_period": i.signalPeriod,
		"signal":        i.signal,
	}
}

func (i *MACDIndicator) Calculate(history *types.PriceHistory) error {
	if history.Len() < i.slowPeriod {
		return fmt.Errorf("insufficient data for MACD calculation")
	}

	// Calculate EMAs
	fastEMA := EMA(history, i.fastPeriod)
	slowEMA := EMA(history, i.slowPeriod)

	// Calculate MACD line
	i.value = fastEMA - slowEMA

	// Calculate signal line
	i.signal = EMA(history, i.signalPeriod)

	return nil
}

// BollingerBandsIndicator implements Bollinger Bands calculation
type BollingerBandsIndicator struct {
	BaseIndicator
	period     int
	deviations float64
	upper      float64
	lower      float64
}

// NewBollingerBandsIndicator creates a new Bollinger Bands indicator
func NewBollingerBandsIndicator(period int, deviations float64) *BollingerBandsIndicator {
	return &BollingerBandsIndicator{
		BaseIndicator: BaseIndicator{name: "BB"},
		period:        period,
		deviations:    deviations,
	}
}

func (i *BollingerBandsIndicator) Params() interface{} {
	return map[string]interface{}{
		"period":     i.period,
		"deviations": i.deviations,
		"middle":     i.value,
		"upper":      i.upper,
		"lower":      i.lower,
	}
}

func (i *BollingerBandsIndicator) Calculate(history *types.PriceHistory) error {
	if history.Len() < i.period {
		return fmt.Errorf("insufficient data for Bollinger Bands calculation")
	}

	// Calculate SMA
	i.value = SMA(history, i.period)

	// Calculate standard deviation
	var sumSquares float64
	count := 0

	history.Range(func(level *types.PriceLevel) bool {
		if count >= i.period {
			return false
		}
		diff := level.Price - i.value
		sumSquares += diff * diff
		count++
		return true
	})

	stdDev := math.Sqrt(sumSquares / float64(i.period))

	// Calculate bands
	i.upper = i.value + (stdDev * i.deviations)
	i.lower = i.value - (stdDev * i.deviations)

	return nil
}
