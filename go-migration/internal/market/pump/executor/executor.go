package executor

import (
	"context"
	"fmt"
	"sync"
	"time"

	"go.uber.org/zap"

	"github.com/kwanRoshi/B/go-migration/internal/config"
	"github.com/kwanRoshi/B/go-migration/internal/types"
)

type Executor struct {
	logger   *zap.Logger
	provider types.MarketDataProvider
	secrets  *config.Secrets
	mu       sync.RWMutex
}

func NewExecutor(provider types.MarketDataProvider, logger *zap.Logger, secretKey string) (*Executor, error) {
	secrets := &config.Secrets{
		PumpFunKey: secretKey,
	}

	return &Executor{
		logger:   logger,
		provider: provider,
		secrets:  secrets,
	}, nil
}

func (e *Executor) ExecuteTrade(ctx context.Context, trade *types.Trade) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	// Prepare trade parameters
	params := map[string]interface{}{
		"symbol":    trade.Symbol,
		"side":      trade.Side,
		"quantity":  trade.Quantity,
		"price":     trade.Price,
		"timestamp": time.Now().UnixNano(),
		"key":       e.secrets.PumpFunKey,
	}

	// Execute trade through provider
	if err := e.provider.ExecuteTrade(ctx, params); err != nil {
		e.logger.Error("Failed to execute trade",
			zap.String("symbol", trade.Symbol),
			zap.String("side", string(trade.Side)),
			zap.Float64("quantity", trade.Quantity),
			zap.Error(err))
		return fmt.Errorf("failed to execute trade: %w", err)
	}

	e.logger.Info("Trade executed successfully",
		zap.String("symbol", trade.Symbol),
		zap.String("side", string(trade.Side)),
		zap.Float64("quantity", trade.Quantity))

	return nil
}
