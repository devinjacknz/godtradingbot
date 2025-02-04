package market

import (
	"context"
	"sync"
	"time"

	"go.uber.org/zap"

	"github.com/devinjacknz/tradingbot/internal/types"
)

// Handler manages market data subscriptions and updates
type Handler struct {
	logger    *zap.Logger
	provider  types.MarketDataProvider
	updates   chan *types.PriceUpdate
	subs      map[string][]chan *types.PriceUpdate
	mu        sync.RWMutex
	ctx       context.Context
	cancel    context.CancelFunc
}

// Config represents market data handler configuration
type Config struct {
	BufferSize     int           `json:"buffer_size"`
	UpdateInterval time.Duration `json:"update_interval"`
}

// NewHandler creates a new market data handler
func NewHandler(provider types.MarketDataProvider, logger *zap.Logger) *Handler {
	ctx, cancel := context.WithCancel(context.Background())

	return &Handler{
		logger:   logger,
		provider: provider,
		updates:  make(chan *types.PriceUpdate, 1000),
		subs:     make(map[string][]chan *types.PriceUpdate),
		ctx:      ctx,
		cancel:   cancel,
	}
}

// Start starts the market data handler
func (h *Handler) Start() error {
	// Start processing updates
	go h.processUpdates()

	return nil
}

// Stop stops the market data handler
func (h *Handler) Stop() {
	h.cancel()
}

// SubscribePrices subscribes to price updates for multiple symbols
func (h *Handler) SubscribePrices(ctx context.Context, symbols []string) (<-chan *types.PriceUpdate, error) {
	return h.provider.SubscribePrices(ctx, symbols)
}

// GetPrice gets the current price for a symbol
func (h *Handler) GetPrice(ctx context.Context, symbol string) (float64, error) {
	return h.provider.GetPrice(ctx, symbol)
}

// GetHistoricalPrices gets historical prices for a symbol
func (h *Handler) GetHistoricalPrices(ctx context.Context, symbol string, interval string, limit int) ([]types.PriceUpdate, error) {
	return h.provider.GetHistoricalPrices(ctx, symbol, interval, limit)
}

// Internal methods

func (h *Handler) processUpdates() {
	for {
		select {
		case <-h.ctx.Done():
			return
		case update := <-h.updates:
			h.mu.RLock()
			// Forward update to all subscribers
			for _, sub := range h.subs[update.Symbol] {
				select {
				case sub <- update:
				default:
					h.logger.Warn("Subscriber channel full",
						zap.String("symbol", update.Symbol))
				}
			}
			h.mu.RUnlock()
		}
	}
}
