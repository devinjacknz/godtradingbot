package market

import (
	"context"
	"sync"
	"time"

	"go.uber.org/zap"

	"github.com/kwanRoshi/B/go-migration/internal/types"
)

// Handler manages market data subscriptions and updates
type Handler struct {
	logger    *zap.Logger
	providers []types.MarketDataProvider
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
func NewHandler(providers []types.MarketDataProvider, logger *zap.Logger) *Handler {
	ctx, cancel := context.WithCancel(context.Background())

	return &Handler{
		logger:    logger,
		providers: providers,
		updates:   make(chan *types.PriceUpdate, 1000),
		subs:      make(map[string][]chan *types.PriceUpdate),
		ctx:       ctx,
		cancel:    cancel,
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
	updates := make(chan *types.PriceUpdate, len(symbols)*len(h.providers))
	
	for _, provider := range h.providers {
		providerUpdates, err := provider.SubscribePrices(ctx, symbols)
		if err != nil {
			h.logger.Error("Failed to subscribe to provider",
				zap.Error(err))
			continue
		}
		
		go func(p types.MarketDataProvider, updates chan<- *types.PriceUpdate) {
			for update := range providerUpdates {
				select {
				case updates <- update:
				case <-ctx.Done():
					return
				}
			}
		}(provider, updates)
	}
	
	return updates, nil
}

// GetPrice gets the current price for a symbol
func (h *Handler) GetPrice(ctx context.Context, symbol string) (float64, error) {
	for _, provider := range h.providers {
		price, err := provider.GetPrice(ctx, symbol)
		if err == nil {
			return price, nil
		}
		h.logger.Debug("Provider failed to get price",
			zap.Error(err))
	}
	return 0, fmt.Errorf("no provider available for symbol %s", symbol)
}

// GetHistoricalPrices gets historical prices for a symbol
func (h *Handler) GetHistoricalPrices(ctx context.Context, symbol string, interval string, limit int) ([]types.PriceUpdate, error) {
	for _, provider := range h.providers {
		prices, err := provider.GetHistoricalPrices(ctx, symbol, interval, limit)
		if err == nil {
			return prices, nil
		}
		h.logger.Debug("Provider failed to get historical prices",
			zap.Error(err))
	}
	return nil, fmt.Errorf("no provider available for symbol %s historical data", symbol)
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
