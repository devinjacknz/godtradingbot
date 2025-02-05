package solana

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"sync"
	"time"

	"go.uber.org/zap"

	"github.com/kwanRoshi/B/go-migration/internal/types"
)

// Provider implements MarketDataProvider interface for Solana DEXs
type Provider struct {
	logger     *zap.Logger
	client     *http.Client
	baseURL    string
	wsClient   *WSClient
	mu         sync.RWMutex
	dexSources []string // List of supported DEXs (e.g. "jupiter", "raydium", "orca")
}

// Config represents Solana provider configuration
type Config struct {
	BaseURL      string   `json:"base_url"`
	WebSocketURL string   `json:"websocket_url"`
	DexSources   []string `json:"dex_sources"`
	TimeoutSec   int      `json:"timeout_sec"`
}

// NewProvider creates a new Solana provider
func NewProvider(config Config, logger *zap.Logger) *Provider {
	return &Provider{
		logger: logger,
		client: &http.Client{
			Timeout: time.Duration(config.TimeoutSec) * time.Second,
		},
		baseURL:    config.BaseURL,
		dexSources: config.DexSources,
		wsClient:   NewWSClient(config.WebSocketURL, logger),
	}
}

// GetPrice implements MarketDataProvider interface
func (p *Provider) GetPrice(ctx context.Context, symbol string) (float64, error) {
	// Query multiple DEXs for best price
	var bestPrice float64
	var bestDEX string

	for _, dex := range p.dexSources {
		price, err := p.getPriceFromDEX(ctx, dex, symbol)
		if err != nil {
			p.logger.Warn("Failed to get price from DEX",
				zap.String("dex", dex),
				zap.Error(err))
			continue
		}

		if price > bestPrice {
			bestPrice = price
			bestDEX = dex
		}
	}

	if bestPrice == 0 {
		return 0, fmt.Errorf("no valid price found for %s", symbol)
	}

	p.logger.Debug("Got best price",
		zap.String("symbol", symbol),
		zap.String("dex", bestDEX),
		zap.Float64("price", bestPrice))

	return bestPrice, nil
}

// SubscribePrices implements MarketDataProvider interface
func (p *Provider) SubscribePrices(ctx context.Context, symbols []string) (<-chan *types.PriceUpdate, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	// Connect WebSocket client if not connected
	if err := p.wsClient.Connect(ctx); err != nil {
		return nil, fmt.Errorf("failed to connect WebSocket: %w", err)
	}

	// Subscribe to symbols on all DEXs
	for _, dex := range p.dexSources {
		if err := p.wsClient.Subscribe(dex, symbols); err != nil {
			return nil, fmt.Errorf("failed to subscribe to %s: %w", dex, err)
		}
	}

	// Return updates channel
	return p.wsClient.GetUpdates(), nil
}

// GetHistoricalPrices implements MarketDataProvider interface
func (p *Provider) GetHistoricalPrices(ctx context.Context, symbol string, interval string, limit int) ([]types.PriceUpdate, error) {
	// Query historical prices from each DEX
	var allUpdates []types.PriceUpdate

	for _, dex := range p.dexSources {
		updates, err := p.getHistoricalPricesFromDEX(ctx, dex, symbol, interval, limit)
		if err != nil {
			p.logger.Warn("Failed to get historical prices from DEX",
				zap.String("dex", dex),
				zap.Error(err))
			continue
		}
		allUpdates = append(allUpdates, updates...)
	}

	if len(allUpdates) == 0 {
		return nil, fmt.Errorf("no historical prices found for %s", symbol)
	}

	// Sort updates by timestamp and remove duplicates
	sortAndDedupUpdates(allUpdates)

	return allUpdates, nil
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

// Internal methods

func (p *Provider) getPriceFromDEX(ctx context.Context, dex, symbol string) (float64, error) {
	url := fmt.Sprintf("%s/v1/price/%s/%s", p.baseURL, dex, symbol)

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
		Price float64 `json:"price"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return 0, fmt.Errorf("failed to decode response: %w", err)
	}

	return result.Price, nil
}

func (p *Provider) getHistoricalPricesFromDEX(ctx context.Context, dex, symbol, interval string, limit int) ([]types.PriceUpdate, error) {
	url := fmt.Sprintf("%s/v1/history/%s/%s?interval=%s&limit=%d",
		p.baseURL, dex, symbol, interval, limit)

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

// Helper functions

func sortAndDedupUpdates(updates []types.PriceUpdate) {
	// Sort by timestamp
	sort.Slice(updates, func(i, j int) bool {
		return updates[i].Timestamp.Before(updates[j].Timestamp)
	})

	// Remove duplicates
	j := 0
	for i := 1; i < len(updates); i++ {
		if updates[i].Timestamp.Equal(updates[j].Timestamp) {
			// Keep the higher price in case of duplicates
			if updates[i].Price > updates[j].Price {
				updates[j] = updates[i]
			}
		} else {
			j++
			updates[j] = updates[i]
		}
	}
	updates = updates[:j+1]
}
