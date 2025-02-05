package analysis

import (
	"fmt"
	"math"

	"github.com/shopspring/decimal"
)

type Indicators struct {
	RSI           decimal.Decimal
	MovingAverage struct {
		MA30 decimal.Decimal
		MA60 decimal.Decimal
	}
	LastPrice decimal.Decimal
}

func CalculateRSI(prices []decimal.Decimal, period int) (decimal.Decimal, error) {
	if len(prices) < period+1 {
		return decimal.Zero, fmt.Errorf("insufficient data points for RSI calculation")
	}

	var gains, losses decimal.Decimal
	for i := 1; i <= period; i++ {
		change := prices[i].Sub(prices[i-1])
		if change.IsPositive() {
			gains = gains.Add(change)
		} else {
			losses = losses.Add(change.Abs())
		}
	}

	avgGain := gains.Div(decimal.NewFromInt(int64(period)))
	avgLoss := losses.Div(decimal.NewFromInt(int64(period)))

	if avgLoss.IsZero() {
		return decimal.NewFromInt(100), nil
	}

	rs := avgGain.Div(avgLoss)
	rsi := decimal.NewFromInt(100).Sub(decimal.NewFromInt(100).Div(decimal.NewFromInt(1).Add(rs)))

	return rsi, nil
}

func CalculateMA(prices []decimal.Decimal, period int) (decimal.Decimal, error) {
	if len(prices) < period {
		return decimal.Zero, fmt.Errorf("insufficient data points for MA calculation")
	}

	sum := decimal.Zero
	for i := 0; i < period; i++ {
		sum = sum.Add(prices[i])
	}

	return sum.Div(decimal.NewFromInt(int64(period))), nil
}

func CalculateIndicators(prices []decimal.Decimal) (*Indicators, error) {
	if len(prices) < 60 {
		return nil, fmt.Errorf("insufficient data points for indicators calculation")
	}

	indicators := &Indicators{
		LastPrice: prices[0],
	}

	rsi, err := CalculateRSI(prices[:15], 14)
	if err != nil {
		return nil, fmt.Errorf("failed to calculate RSI: %w", err)
	}
	indicators.RSI = rsi

	ma30, err := CalculateMA(prices[:30], 30)
	if err != nil {
		return nil, fmt.Errorf("failed to calculate MA30: %w", err)
	}
	indicators.MovingAverage.MA30 = ma30

	ma60, err := CalculateMA(prices[:60], 60)
	if err != nil {
		return nil, fmt.Errorf("failed to calculate MA60: %w", err)
	}
	indicators.MovingAverage.MA60 = ma60

	return indicators, nil
}

func IsBullishCrossover(ma30, ma60 []decimal.Decimal) bool {
	if len(ma30) < 2 || len(ma60) < 2 {
		return false
	}

	prevMA30 := ma30[1]
	prevMA60 := ma60[1]
	currMA30 := ma30[0]
	currMA60 := ma60[0]

	return prevMA30.LessThanOrEqual(prevMA60) && currMA30.GreaterThan(currMA60)
}

func IsBearishCrossover(ma30, ma60 []decimal.Decimal) bool {
	if len(ma30) < 2 || len(ma60) < 2 {
		return false
	}

	prevMA30 := ma30[1]
	prevMA60 := ma60[1]
	currMA30 := ma30[0]
	currMA60 := ma60[0]

	return prevMA30.GreaterThanOrEqual(prevMA60) && currMA30.LessThan(currMA60)
}
