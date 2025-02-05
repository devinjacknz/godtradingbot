package backtest

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"go.uber.org/zap"

	"github.com/kwanRoshi/B/go-migration/internal/pricing"
)

func TestAnalyzeSignals(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	analyzer := NewSignalAnalyzer(logger)

	// Create test data
	now := time.Now()
	signals := []*pricing.Signal{
		{
			Symbol:     "BTC/USD",
			Direction:  "long",
			Price:     50000,
			Confidence: 0.8,
			Timestamp: now,
			Indicators: []pricing.Indicator{
				{Name: "RSI", Value: 70},
			},
		},
		{
			Symbol:     "BTC/USD",
			Direction:  "short",
			Price:     55000,
			Confidence: 0.9,
			Timestamp: now.Add(1 * time.Hour),
			Indicators: []pricing.Indicator{
				{Name: "RSI", Value: 30},
			},
		},
	}

	trades := []*Trade{
		{
			Symbol:     "BTC/USD",
			Direction:  "long",
			EntryTime:  now,
			ExitTime:   now.Add(30 * time.Minute),
			EntryPrice: 50000,
			ExitPrice:  52000,
			Quantity:   1,
		},
		{
			Symbol:     "BTC/USD",
			Direction:  "short",
			EntryTime:  now.Add(1 * time.Hour),
			ExitTime:   now.Add(90 * time.Minute),
			EntryPrice: 55000,
			ExitPrice:  53000,
			Quantity:   1,
		},
	}

	// Test AnalyzeSignals
	stats, err := analyzer.AnalyzeSignals(signals, trades)
	assert.NoError(t, err)
	assert.Equal(t, 2, stats.TotalSignals)
	assert.Equal(t, 2, stats.AccurateSignals)
	assert.Equal(t, 0, stats.InaccurateSignals)
	assert.InDelta(t, 0.5, stats.Accuracy, 0.0001)
	assert.InDelta(t, 0.85, stats.AvgConfidence, 0.0001)

	// Test AnalyzeIndicators
	indicatorAccuracy := analyzer.AnalyzeIndicators(signals)
	assert.InDelta(t, 1.0, indicatorAccuracy["RSI"], 0.0001)

	// Test AnalyzeTimeDistribution
	distribution := analyzer.AnalyzeTimeDistribution(signals)
	hour1 := now.Format("15:00")
	hour2 := now.Add(1 * time.Hour).Format("15:00")
	assert.Equal(t, 1, distribution[hour1])
	assert.Equal(t, 1, distribution[hour2])

	// Test AnalyzeConfidenceLevels
	confidenceLevels := analyzer.AnalyzeConfidenceLevels(signals, trades)
	assert.InDelta(t, 0.5, confidenceLevels["high"], 0.0001)
}

func TestCalculateTradeReturn(t *testing.T) {
	tests := []struct {
		name     string
		trade    *Trade
		expected float64
	}{
		{
			name: "Long profitable trade",
			trade: &Trade{
				Direction:  "long",
				EntryPrice: 100,
				ExitPrice:  110,
			},
			expected: 0.1, // 10% profit
		},
		{
			name: "Long losing trade",
			trade: &Trade{
				Direction:  "long",
				EntryPrice: 100,
				ExitPrice:  90,
			},
			expected: -0.1, // 10% loss
		},
		{
			name: "Short profitable trade",
			trade: &Trade{
				Direction:  "short",
				EntryPrice: 100,
				ExitPrice:  90,
			},
			expected: 0.1, // 10% profit
		},
		{
			name: "Short losing trade",
			trade: &Trade{
				Direction:  "short",
				EntryPrice: 100,
				ExitPrice:  110,
			},
			expected: -0.1, // 10% loss
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := calculateTradeReturn(tt.trade)
			assert.InDelta(t, tt.expected, result, 0.0001)
		})
	}
}

func TestIsSignalAccurate(t *testing.T) {
	tests := []struct {
		name     string
		signal   *pricing.Signal
		trade    *Trade
		expected bool
	}{
		{
			name: "Accurate long signal",
			signal: &pricing.Signal{
				Direction: "long",
			},
			trade: &Trade{
				Direction:  "long",
				EntryPrice: 100,
				ExitPrice:  110,
			},
			expected: true,
		},
		{
			name: "Inaccurate long signal",
			signal: &pricing.Signal{
				Direction: "long",
			},
			trade: &Trade{
				Direction:  "long",
				EntryPrice: 100,
				ExitPrice:  90,
			},
			expected: false,
		},
		{
			name: "Accurate short signal",
			signal: &pricing.Signal{
				Direction: "short",
			},
			trade: &Trade{
				Direction:  "short",
				EntryPrice: 100,
				ExitPrice:  90,
			},
			expected: true,
		},
		{
			name: "Inaccurate short signal",
			signal: &pricing.Signal{
				Direction: "short",
			},
			trade: &Trade{
				Direction:  "short",
				EntryPrice: 100,
				ExitPrice:  110,
			},
			expected: false,
		},
		{
			name: "Direction mismatch",
			signal: &pricing.Signal{
				Direction: "long",
			},
			trade: &Trade{
				Direction:  "short",
				EntryPrice: 100,
				ExitPrice:  90,
			},
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := isSignalAccurate(tt.signal, tt.trade)
			assert.Equal(t, tt.expected, result)
		})
	}
}
