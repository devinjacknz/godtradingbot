package pump

import (
	"context"
	"testing"
	"time"

	"go.uber.org/zap"

	"github.com/devinjacknz/tradingbot/internal/market"
)

func TestPumpProvider(t *testing.T) {
	// Create mock WebSocket server
	server, wsURL := market.MockWebSocketServer()
	defer server.Close()

	logger := zap.NewNop()
	config := Config{
		BaseURL:      server.URL,
		WebSocketURL: wsURL,
		TimeoutSec:   10,
	}

	provider := NewProvider(config, logger)
	defer provider.Close()

	t.Run("GetPrice", func(t *testing.T) {
		ctx := context.Background()
		_, err := provider.GetPrice(ctx, "TEST/SOL")
		if err == nil {
			t.Error("Expected error for non-existent symbol")
		}
	})

	t.Run("SubscribePrices", func(t *testing.T) {
		ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
		defer cancel()

		updates, err := provider.SubscribePrices(ctx, []string{"TEST/SOL"})
		if err != nil {
			t.Fatalf("Failed to subscribe: %v", err)
		}

		select {
		case <-updates:
			t.Error("Unexpected update received")
		case <-ctx.Done():
			// Expected timeout
		}
	})
}
