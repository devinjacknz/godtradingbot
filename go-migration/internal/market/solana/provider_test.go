package solana

import (
	"context"
	"testing"
	"time"

	"go.uber.org/zap"

	"github.com/kwanRoshi/B/go-migration/internal/market"
)

func TestSolanaProvider(t *testing.T) {
	// Create mock WebSocket server
	server, wsURL := market.MockWebSocketServer()
	defer server.Close()

	logger := zap.NewNop()
	config := Config{
		BaseURL:      server.URL,
		WebSocketURL: wsURL,
		DexSources:   []string{"jupiter", "raydium"},
		TimeoutSec:   10,
	}

	provider := NewProvider(config, logger)
	defer provider.Close()

	t.Run("GetPrice", func(t *testing.T) {
		ctx := context.Background()
		_, err := provider.GetPrice(ctx, "SOL/USDC")
		if err == nil {
			t.Error("Expected error for non-existent symbol")
		}
	})

	t.Run("SubscribePrices", func(t *testing.T) {
		ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
		defer cancel()

		updates, err := provider.SubscribePrices(ctx, []string{"SOL/USDC"})
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
