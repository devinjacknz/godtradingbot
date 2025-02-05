package backtest

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"

	"github.com/kwanRoshi/B/go-migration/internal/backtest/testutil"
	"github.com/kwanRoshi/B/go-migration/internal/pricing"
)

func setupTestStorage(t *testing.T) (*MongoStorage, func()) {
	testutil.SkipIfNoDocker(t)

	logger, _ := zap.NewDevelopment()
	uri, cleanup := testutil.StartMongoContainer(t)

	config := MongoConfig{
		URI:      uri,
		Database: "tradingbot_test",
	}

	storage, err := NewMongoStorage(config, logger)
	require.NoError(t, err)

	// Clean up test database
	ctx := context.Background()
	err = storage.client.Database(config.Database).Drop(ctx)
	require.NoError(t, err)

	return storage, cleanup
}

func TestMongoStorage_SaveAndLoadResult(t *testing.T) {
	storage, cleanup := setupTestStorage(t)
	defer cleanup()
	ctx := context.Background()

	// Create test data
	now := time.Now()
	result := &Result{
		TotalTrades:      10,
		WinningTrades:    7,
		LosingTrades:     3,
		WinRate:          0.7,
		ProfitFactor:     2.5,
		SharpeRatio:      1.8,
		MaxDrawdown:      0.15,
		FinalBalance:     11000,
		TotalReturn:      0.1,
		AnnualizedReturn: 0.2,
		Trades: []*Trade{
			{
				Symbol:     "BTC/USD",
				Direction:  "long",
				EntryTime:  now,
				ExitTime:   now.Add(time.Hour),
				EntryPrice: 50000,
				ExitPrice:  52000,
				Quantity:   1,
				PnL:        2000,
				Commission: 10,
				Slippage:   0.001,
			},
		},
		Metrics: &Metrics{
			DailyReturns:    []float64{0.01, 0.02, -0.01},
			MonthlyReturns:  []float64{0.05, 0.03},
			ReturnsBySymbol: map[string]float64{"BTC/USD": 0.1},
			DrawdownSeries:  []float64{0.05, 0.15, 0.1},
		},
	}

	// Test SaveResult
	err := storage.SaveResult(ctx, result)
	assert.NoError(t, err)

	// Test LoadResult
	loaded, err := storage.LoadResult(ctx, "test_result")
	assert.NoError(t, err)
	assert.Equal(t, result.TotalTrades, loaded.TotalTrades)
	assert.Equal(t, result.WinRate, loaded.WinRate)
	assert.Equal(t, len(result.Trades), len(loaded.Trades))
	assert.Equal(t, result.Trades[0].Symbol, loaded.Trades[0].Symbol)
}

func TestMongoStorage_SaveAndLoadSignals(t *testing.T) {
	storage, cleanup := setupTestStorage(t)
	defer cleanup()
	ctx := context.Background()

	// Create test data
	now := time.Now()
	signals := []*pricing.Signal{
		{
			Symbol:     "BTC/USD",
			Type:      "entry",
			Direction: "long",
			Price:     50000,
			Confidence: 0.8,
			Timestamp: now,
			Indicators: []pricing.Indicator{
				{
					Name:  "RSI",
					Value: 70,
					Params: map[string]interface{}{
						"period": 14,
					},
				},
			},
		},
		{
			Symbol:     "BTC/USD",
			Type:      "exit",
			Direction: "long",
			Price:     52000,
			Confidence: 0.9,
			Timestamp: now.Add(time.Hour),
			Indicators: []pricing.Indicator{
				{
					Name:  "RSI",
					Value: 80,
					Params: map[string]interface{}{
						"period": 14,
					},
				},
			},
		},
	}

	// Test SaveSignals
	err := storage.SaveSignals(ctx, signals)
	assert.NoError(t, err)

	// Test LoadSignals
	loaded, err := storage.LoadSignals(ctx, "BTC/USD", now.Add(-time.Hour), now.Add(2*time.Hour))
	assert.NoError(t, err)
	assert.Equal(t, len(signals), len(loaded))
	assert.Equal(t, signals[0].Symbol, loaded[0].Symbol)
	assert.Equal(t, signals[0].Direction, loaded[0].Direction)
	assert.Equal(t, signals[0].Price, loaded[0].Price)
	assert.Equal(t, len(signals[0].Indicators), len(loaded[0].Indicators))
}

func TestMongoStorage_SaveSignals_Empty(t *testing.T) {
	storage, cleanup := setupTestStorage(t)
	defer cleanup()
	ctx := context.Background()

	// Test SaveSignals with empty slice
	err := storage.SaveSignals(ctx, []*pricing.Signal{})
	assert.NoError(t, err)
}

func TestMongoStorage_LoadSignals_NoResults(t *testing.T) {
	storage, cleanup := setupTestStorage(t)
	defer cleanup()
	ctx := context.Background()

	now := time.Now()
	signals, err := storage.LoadSignals(ctx, "NONEXISTENT", now, now.Add(time.Hour))
	assert.NoError(t, err)
	assert.Empty(t, signals)
}

func TestMongoStorage_LoadResult_NotFound(t *testing.T) {
	storage, cleanup := setupTestStorage(t)
	defer cleanup()
	ctx := context.Background()

	result, err := storage.LoadResult(ctx, "nonexistent_id")
	assert.Error(t, err)
	assert.Nil(t, result)
	assert.Contains(t, err.Error(), "not found")
}

func TestMongoStorage_Close(t *testing.T) {
	storage, cleanup := setupTestStorage(t)
	defer cleanup()
	ctx := context.Background()

	err := storage.Close(ctx)
	assert.NoError(t, err)

	// Verify connection is closed by attempting an operation
	err = storage.SaveResult(ctx, &Result{})
	assert.Error(t, err)
}
