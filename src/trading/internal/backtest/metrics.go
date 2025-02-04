package backtest

import (
	"time"
)

// Metrics represents performance metrics
type Metrics struct {
	DailyReturns     []float64          `json:"daily_returns"`
	MonthlyReturns   []float64          `json:"monthly_returns"`
	ReturnsBySymbol  map[string]float64 `json:"returns_by_symbol"`
	DrawdownSeries   []float64          `json:"drawdown_series"`
	VolatilitySeries []float64          `json:"volatility_series"`
}

// NewMetrics creates a new metrics instance
func NewMetrics() *Metrics {
	return &Metrics{
		DailyReturns:    make([]float64, 0),
		MonthlyReturns:  make([]float64, 0),
		ReturnsBySymbol: make(map[string]float64),
		DrawdownSeries:  make([]float64, 0),
	}
}

// UpdateMetrics updates performance metrics
func (e *Engine) updateMetrics() {
	if len(e.results.Trades) == 0 {
		return
	}

	// Sort trades by exit time
	trades := make([]*Trade, len(e.results.Trades))
	copy(trades, e.results.Trades)
	sortTradesByExitTime(trades)

	// Calculate running balance and drawdown
	currentBalance := e.config.InitialBalance
	peak := currentBalance
	var prevDate time.Time
	dailyPnL := 0.0

	// Track balance history for accurate drawdown calculation
	balanceHistory := make([]float64, 0)
	balanceHistory = append(balanceHistory, currentBalance)

	for _, trade := range trades {
		date := trade.ExitTime.Truncate(24 * time.Hour)

		// If we've moved to a new day, record the previous day's metrics
		if !date.Equal(prevDate) && !prevDate.IsZero() {
			// Calculate daily return
			dailyReturn := dailyPnL / currentBalance
			e.results.Metrics.DailyReturns = append(e.results.Metrics.DailyReturns, dailyReturn)

			// Reset daily PnL
			dailyPnL = 0
		}

		// Update running totals
		currentBalance += trade.PnL
		dailyPnL += trade.PnL
		balanceHistory = append(balanceHistory, currentBalance)

		// Update peak if we have a new high
		if currentBalance > peak {
			peak = currentBalance
		}

		// Calculate drawdown from peak
		drawdown := (peak - currentBalance) / peak
		e.results.Metrics.DrawdownSeries = append(e.results.Metrics.DrawdownSeries, drawdown)

		prevDate = date
	}

	// Record metrics for the last day
	if dailyPnL != 0 {
		dailyReturn := dailyPnL / currentBalance
		e.results.Metrics.DailyReturns = append(e.results.Metrics.DailyReturns, dailyReturn)
	}

	// Calculate returns by symbol
	symbolPnL := make(map[string]float64)
	for _, trade := range trades {
		symbolPnL[trade.Symbol] += trade.PnL
	}
	for symbol, pnl := range symbolPnL {
		e.results.Metrics.ReturnsBySymbol[symbol] = pnl / e.config.InitialBalance
	}
}

// Helper functions

func sortTradesByExitTime(trades []*Trade) {
	for i := 0; i < len(trades)-1; i++ {
		for j := i + 1; j < len(trades); j++ {
			if trades[j].ExitTime.Before(trades[i].ExitTime) {
				trades[i], trades[j] = trades[j], trades[i]
			}
		}
	}
}
