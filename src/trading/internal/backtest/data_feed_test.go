package backtest

import (
	"context"
	"os"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"
)

func TestCSVDataFeed(t *testing.T) {
	// Create test CSV file
	content := `2024-02-01 10:00:00,50000,100
2024-02-01 10:01:00,50100,150
2024-02-01 10:02:00,50200,200`

	err := os.MkdirAll("data", 0755)
	require.NoError(t, err)

	err = os.WriteFile("data/BTC_USD.csv", []byte(content), 0644)
	require.NoError(t, err)
	defer os.RemoveAll("data")

	// Create data feed
	feed, err := NewCSVDataFeed("BTC_USD")
	require.NoError(t, err)
	defer feed.Close()

	// Test Next and Current
	assert.True(t, feed.Next())
	current := feed.Current()
	assert.Equal(t, "BTC_USD", current.Symbol)
	assert.Equal(t, 50000.0, current.Price)
	assert.Equal(t, 100.0, current.Volume)

	assert.True(t, feed.Next())
	current = feed.Current()
	assert.Equal(t, 50100.0, current.Price)
	assert.Equal(t, 150.0, current.Volume)

	assert.True(t, feed.Next())
	current = feed.Current()
	assert.Equal(t, 50200.0, current.Price)
	assert.Equal(t, 200.0, current.Volume)

	// Should return false when no more data
	assert.False(t, feed.Next())
}

func TestCSVDataFeed_InvalidFile(t *testing.T) {
	_, err := NewCSVDataFeed("NONEXISTENT")
	assert.Error(t, err)
}

func TestCSVDataFeed_InvalidData(t *testing.T) {
	// Create test CSV file with invalid data
	content := `invalid,data,format
2024-02-01 10:00:00,not_a_number,100
2024-02-01 10:01:00,50100,not_a_number`

	err := os.MkdirAll("data", 0755)
	require.NoError(t, err)

	err = os.WriteFile("data/INVALID.csv", []byte(content), 0644)
	require.NoError(t, err)
	defer os.RemoveAll("data")

	feed, err := NewCSVDataFeed("INVALID")
	require.NoError(t, err)
	defer feed.Close()

	// Should return false for invalid data
	assert.False(t, feed.Next())
}

func TestPostgresDataFeed(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	ctx := context.Background()

	config := PostgresConfig{
		Host:     "localhost",
		Port:     5432,
		User:     "postgres",
		Password: "postgres",
		DBName:   "tradingbot_test",
		SSLMode:  "disable",
	}

	now := time.Now()
	symbol := "BTC/USD"

	feed, err := NewPostgresDataFeed(ctx, config, logger, symbol, now.Add(-time.Hour), now, time.Minute)
	if err != nil {
		t.Skip("Skipping PostgreSQL test - database not available")
	}
	defer feed.Close()

	// Since this is just testing the interface implementation,
	// and we don't have a test database set up, we'll just verify
	// that the methods don't panic
	_ = feed.Next()
	_ = feed.Current()
}
