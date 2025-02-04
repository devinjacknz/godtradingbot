package pump

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"

	"go.uber.org/zap"

	"github.com/devinjacknz/tradingbot/internal/types"
)

// Provider implements MarketDataProvider interface for Pump.fun
type Provider struct {
	logger   *zap.Logger
	client   *http.Client
	baseURL  string
	wsClient *WSClient
	mu       sync.RWMutex
}

// Config represents Pump.fun provider configuration
type Config struct {
	BaseURL      string `json:"base_url"`
	WebSocketURL string `json:"websocket_url"`
	TimeoutSec   int    `json:"timeout_sec"`
}

// NewProvider creates a new Pump.fun provider
func NewProvider(config Config, logger *zap.Logger) *Provider {
	return &Provider{
		logger: logger,
		client: &http.Client{
			Timeout: time.Duration(config.TimeoutSec) * time.Second,
		},
		baseURL:  config.BaseURL,
		wsClient: NewWSClient(config.WebSocketURL, logger),
	}
}

// GetPrice implements MarketDataProvider interface
func (p *Provider) GetPrice(ctx context.Context, symbol string) (float64, error) {
	url := fmt.Sprintf("%s/api/v1/price/%s", p.baseURL, symbol)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return 0, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := p.client.Do(req)
	if err != nil {
		return 0, fmt.Errorf("failed to get price: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return 0, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	var result struct {
		Price  float64 `json:"price"`
		Volume float64 `json:"volume"`
		Time   int64   `json:"time"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return 0, fmt.Errorf("failed to decode response: %w", err)
	}

	return result.Price, nil
}

// SubscribePrices implements MarketDataProvider interface
func (p *Provider) SubscribePrices(ctx context.Context, symbols []string) (<-chan *types.PriceUpdate, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	// Connect WebSocket client if not connected
	if err := p.wsClient.Connect(ctx); err != nil {
		return nil, fmt.Errorf("failed to connect WebSocket: %w", err)
	}

	// Subscribe to symbols
	if err := p.wsClient.Subscribe(symbols); err != nil {
		return nil, fmt.Errorf("failed to subscribe: %w", err)
	}

	// Return updates channel
	return p.wsClient.GetUpdates(), nil
}

// GetHistoricalPrices implements MarketDataProvider interface
func (p *Provider) GetHistoricalPrices(ctx context.Context, symbol string, interval string, limit int) ([]types.PriceUpdate, error) {
	url := fmt.Sprintf("%s/api/v1/historical/%s?interval=%s&limit=%d",
		p.baseURL, symbol, interval, limit)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := p.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to get historical prices: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	var result []struct {
		Time   int64   `json:"time"`
		Price  float64 `json:"price"`
		Volume float64 `json:"volume"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	updates := make([]types.PriceUpdate, len(result))
	for i, item := range result {
		updates[i] = types.PriceUpdate{
			Symbol:    symbol,
			Price:     item.Price,
			Volume:    item.Volume,
			Timestamp: time.Unix(item.Time, 0),
		}
	}

	return updates, nil
}

// Close closes the provider and its WebSocket client
func (p *Provider) Close() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	if p.wsClient != nil {
		return p.wsClient.Close()
	}
	return nil
}
