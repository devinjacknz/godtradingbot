package pricing

import (
	"math"
)

// IndicatorCalculator defines interface for technical indicators
type IndicatorCalculator interface {
	Calculate(history *PriceHistory) error
	Name() string
	Value() float64
	Params() interface{}
}

// RSIIndicator calculates Relative Strength Index
type RSIIndicator struct {
	period int
	value  float64
}

// NewRSIIndicator creates a new RSI indicator
func NewRSIIndicator(period int) *RSIIndicator {
	return &RSIIndicator{
		period: period,
	}
}

// Calculate implements IndicatorCalculator interface
func (i *RSIIndicator) Calculate(history *PriceHistory) error {
	if history.LastIndex < i.period {
		return nil
	}

	var gains, losses float64
	for j := 0; j < i.period; j++ {
		change := history.Levels[history.LastIndex-j].Price - history.Levels[history.LastIndex-j-1].Price
		if change > 0 {
			gains += change
		} else {
			losses -= change
		}
	}

	avgGain := gains / float64(i.period)
	avgLoss := losses / float64(i.period)

	if avgLoss == 0 {
		i.value = 100
	} else {
		rs := avgGain / avgLoss
		i.value = 100 - (100 / (1 + rs))
	}

	return nil
}

// Name implements IndicatorCalculator interface
func (i *RSIIndicator) Name() string {
	return "RSI"
}

// Value implements IndicatorCalculator interface
func (i *RSIIndicator) Value() float64 {
	return i.value
}

// Params implements IndicatorCalculator interface
func (i *RSIIndicator) Params() interface{} {
	return map[string]interface{}{
		"period": i.period,
	}
}

// MACDIndicator calculates Moving Average Convergence Divergence
type MACDIndicator struct {
	fastPeriod  int
	slowPeriod  int
	signalPeriod int
	value       float64
	signal      float64
}

// NewMACDIndicator creates a new MACD indicator
func NewMACDIndicator(fastPeriod, slowPeriod, signalPeriod int) *MACDIndicator {
	return &MACDIndicator{
		fastPeriod:   fastPeriod,
		slowPeriod:   slowPeriod,
		signalPeriod: signalPeriod,
	}
}

// Calculate implements IndicatorCalculator interface
func (i *MACDIndicator) Calculate(history *PriceHistory) error {
	if history.LastIndex < i.slowPeriod {
		return nil
	}

	// Calculate EMAs
	fastEMA := calculateEMA(history, i.fastPeriod)
	slowEMA := calculateEMA(history, i.slowPeriod)

	// Calculate MACD line
	i.value = fastEMA - slowEMA

	// Calculate signal line
	i.signal = calculateEMA(history, i.signalPeriod)

	return nil
}

// Name implements IndicatorCalculator interface
func (i *MACDIndicator) Name() string {
	return "MACD"
}

// Value implements IndicatorCalculator interface
func (i *MACDIndicator) Value() float64 {
	return i.value
}

// Params implements IndicatorCalculator interface
func (i *MACDIndicator) Params() interface{} {
	return map[string]interface{}{
		"fast_period":   i.fastPeriod,
		"slow_period":   i.slowPeriod,
		"signal_period": i.signalPeriod,
		"signal":        i.signal,
	}
}

// BollingerBandsIndicator calculates Bollinger Bands
type BollingerBandsIndicator struct {
	period       int
	deviations   float64
	middle       float64
	upper        float64
	lower        float64
}

// NewBollingerBandsIndicator creates a new Bollinger Bands indicator
func NewBollingerBandsIndicator(period int, deviations float64) *BollingerBandsIndicator {
	return &BollingerBandsIndicator{
		period:     period,
		deviations: deviations,
	}
}

// Calculate implements IndicatorCalculator interface
func (i *BollingerBandsIndicator) Calculate(history *PriceHistory) error {
	if history.LastIndex < i.period {
		return nil
	}

	// Calculate middle band (SMA)
	var sum float64
	for j := 0; j < i.period; j++ {
		sum += history.Levels[history.LastIndex-j].Price
	}
	i.middle = sum / float64(i.period)

	// Calculate standard deviation
	var variance float64
	for j := 0; j < i.period; j++ {
		diff := history.Levels[history.LastIndex-j].Price - i.middle
		variance += diff * diff
	}
	stdDev := math.Sqrt(variance / float64(i.period))

	// Calculate bands
	i.upper = i.middle + (i.deviations * stdDev)
	i.lower = i.middle - (i.deviations * stdDev)

	return nil
}

// Name implements IndicatorCalculator interface
func (i *BollingerBandsIndicator) Name() string {
	return "BB"
}

// Value implements IndicatorCalculator interface
func (i *BollingerBandsIndicator) Value() float64 {
	return i.middle
}

// Params implements IndicatorCalculator interface
func (i *BollingerBandsIndicator) Params() interface{} {
	return map[string]interface{}{
		"period":     i.period,
		"deviations": i.deviations,
		"upper":      i.upper,
		"lower":      i.lower,
		"middle":     i.middle,
	}
}

// Helper functions

func calculateEMA(history *PriceHistory, period int) float64 {
	multiplier := 2.0 / float64(period+1)
	
	var ema float64
	for i := 0; i < period; i++ {
		price := history.Levels[history.LastIndex-i].Price
		if i == 0 {
			ema = price
		} else {
			ema = (price * multiplier) + (ema * (1 - multiplier))
		}
	}
	return ema
}
