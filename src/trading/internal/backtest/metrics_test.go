package backtest

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestMetrics_UpdateMetrics(t *testing.T) {
	// Create test data
	now := time.Now()
	engine := &Engine{
		config: Config{
			InitialBalance: 10000,
		},
		results: &Result{
			Trades:  make([]*Trade, 0),
			Metrics: NewMetrics(),
		},
	}

	trades := []*Trade{
		{
			Symbol:     "BTC/USD",
			Direction:  "long",
			EntryTime:  now,
			ExitTime:   now.Add(time.Hour),
			EntryPrice: 50000,
			ExitPrice:  52000,
			Quantity:   0.1,
			PnL:        200,
		},
		{
			Symbol:     "ETH/USD",
			Direction:  "short",
			EntryTime:  now.Add(2 * time.Hour),
			ExitTime:   now.Add(3 * time.Hour),
			EntryPrice: 3000,
			ExitPrice:  2900,
			Quantity:   1,
			PnL:        100,
		},
		{
			Symbol:     "BTC/USD",
			Direction:  "long",
			EntryTime:  now.Add(4 * time.Hour),
			ExitTime:   now.Add(5 * time.Hour),
			EntryPrice: 51000,
			ExitPrice:  50500,
			Quantity:   0.1,
			PnL:        -50,
		},
	}

	engine.results.Trades = trades

	// Update metrics
	engine.updateMetrics()

	// Verify daily returns
	assert.NotEmpty(t, engine.results.Metrics.DailyReturns)

	// Verify returns by symbol
	assert.Contains(t, engine.results.Metrics.ReturnsBySymbol, "BTC/USD")
	assert.Contains(t, engine.results.Metrics.ReturnsBySymbol, "ETH/USD")

	// Verify drawdown series
	assert.NotEmpty(t, engine.results.Metrics.DrawdownSeries)
}

func TestMetrics_CalculateResults(t *testing.T) {
	// Create test data
	now := time.Now()
	engine := &Engine{
		config: Config{
			InitialBalance: 10000,
			StartTime:     now.Add(-24 * time.Hour),
			EndTime:       now,
		},
		results: &Result{
			Trades:  make([]*Trade, 0),
			Metrics: NewMetrics(),
		},
	}

	trades := []*Trade{
		{
			Symbol:     "BTC/USD",
			Direction:  "long",
			EntryTime:  now.Add(-23 * time.Hour),
			ExitTime:   now.Add(-22 * time.Hour),
			EntryPrice: 50000,
			ExitPrice:  52000,
			Quantity:   0.1,
			PnL:        200,
		},
		{
			Symbol:     "ETH/USD",
			Direction:  "short",
			EntryTime:  now.Add(-21 * time.Hour),
			ExitTime:   now.Add(-20 * time.Hour),
			EntryPrice: 3000,
			ExitPrice:  2900,
			Quantity:   1,
			PnL:        100,
		},
		{
			Symbol:     "BTC/USD",
			Direction:  "long",
			EntryTime:  now.Add(-19 * time.Hour),
			ExitTime:   now.Add(-18 * time.Hour),
			EntryPrice: 51000,
			ExitPrice:  50500,
			Quantity:   0.1,
			PnL:        -50,
		},
	}

	engine.results.Trades = trades
	engine.portfolio = &Portfolio{
		Balance: 10250, // Initial balance + total PnL
	}

	// Calculate results
	engine.calculateResults()

	// Verify metrics
	assert.Equal(t, 3, engine.results.TotalTrades)
	assert.Equal(t, 2, engine.results.WinningTrades)
	assert.Equal(t, 1, engine.results.LosingTrades)
	assert.InDelta(t, 0.67, engine.results.WinRate, 0.01)
	assert.InDelta(t, 6.0, engine.results.ProfitFactor, 0.01) // (200 + 100) / 50
	assert.Equal(t, 10250.0, engine.results.FinalBalance)
	assert.InDelta(t, 0.025, engine.results.TotalReturn, 0.001) // (10250 - 10000) / 10000
}

func TestMetrics_NewMetrics(t *testing.T) {
	metrics := NewMetrics()

	assert.NotNil(t, metrics)
	assert.Empty(t, metrics.DailyReturns)
	assert.Empty(t, metrics.MonthlyReturns)
	assert.NotNil(t, metrics.ReturnsBySymbol)
	assert.Empty(t, metrics.DrawdownSeries)
}

func TestMetrics_DrawdownCalculation(t *testing.T) {
	// Create test data with a known drawdown pattern
	now := time.Now()
	engine := &Engine{
		config: Config{
			InitialBalance: 10000,
		},
		results: &Result{
			Trades:  make([]*Trade, 0),
			Metrics: NewMetrics(),
		},
	}

	trades := []*Trade{
		{
			EntryTime: now,
			ExitTime:  now.Add(time.Hour),
			PnL:      500, // Peak at 10500
		},
		{
			EntryTime: now.Add(2 * time.Hour),
			ExitTime:  now.Add(3 * time.Hour),
			PnL:      -300, // Drawdown to 10200
		},
		{
			EntryTime: now.Add(4 * time.Hour),
			ExitTime:  now.Add(5 * time.Hour),
			PnL:      -200, // Further drawdown to 10000
		},
		{
			EntryTime: now.Add(6 * time.Hour),
			ExitTime:  now.Add(7 * time.Hour),
			PnL:      600, // New peak at 10600
		},
	}

	engine.results.Trades = trades
	engine.portfolio = &Portfolio{
		Balance: 10600, // Final balance after all trades
	}

	// Update metrics
	engine.updateMetrics()

	// Verify drawdown series
	assert.NotEmpty(t, engine.results.Metrics.DrawdownSeries)

	// The maximum drawdown should be around 4.76% ((10500 - 10000) / 10500)
	maxDrawdown := 0.0
	for _, dd := range engine.results.Metrics.DrawdownSeries {
		if dd > maxDrawdown {
			maxDrawdown = dd
		}
	}
	assert.InDelta(t, 0.0476, maxDrawdown, 0.001)
}
