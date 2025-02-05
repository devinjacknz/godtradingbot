package types

import (
	"context"
	"sync"
	"time"
)

// PriceLevel represents a price level with additional metadata
type PriceLevel struct {
	Symbol    string                 `json:"symbol"`
	Price     float64                `json:"price"`
	Volume    float64                `json:"volume"`
	Bid       float64                `json:"bid"`
	Ask       float64                `json:"ask"`
	Spread    float64                `json:"spread"`
	VWAP      float64                `json:"vwap"`
	Timestamp time.Time              `json:"timestamp"`
	Extra     map[string]interface{} `json:"extra,omitempty"`
}

// PriceHistory maintains a circular buffer of price levels
type PriceHistory struct {
	Symbol    string
	Levels    []*PriceLevel
	Size      int
	LastIndex int
	mu        sync.RWMutex
}

// NewPriceHistory creates a new price history
func NewPriceHistory(size int) *PriceHistory {
	return &PriceHistory{
		Levels: make([]*PriceLevel, size),
		Size:   size,
	}
}

// Add adds a new price level to the history
func (h *PriceHistory) Add(level *PriceLevel) {
	h.mu.Lock()
	defer h.mu.Unlock()

	h.LastIndex = (h.LastIndex + 1) % h.Size
	h.Levels[h.LastIndex] = level
}

// Last returns the most recent price level
func (h *PriceHistory) Last() *PriceLevel {
	h.mu.RLock()
	defer h.mu.RUnlock()

	return h.Levels[h.LastIndex]
}

// Get returns the price level at the given index
func (h *PriceHistory) Get(index int) *PriceLevel {
	h.mu.RLock()
	defer h.mu.RUnlock()

	if index < 0 || index >= h.Size {
		return nil
	}
	return h.Levels[index]
}

// Len returns the number of valid price levels
func (h *PriceHistory) Len() int {
	h.mu.RLock()
	defer h.mu.RUnlock()

	count := 0
	for _, level := range h.Levels {
		if level != nil {
			count++
		}
	}
	return count
}

// Range iterates over price levels from newest to oldest
func (h *PriceHistory) Range(fn func(level *PriceLevel) bool) {
	h.mu.RLock()
	defer h.mu.RUnlock()

	for i := 0; i < h.Size; i++ {
		index := (h.LastIndex - i + h.Size) % h.Size
		level := h.Levels[index]
		if level == nil {
			continue
		}
		if !fn(level) {
			break
		}
	}
}

// Clear removes all price levels
func (h *PriceHistory) Clear() {
	h.mu.Lock()
	defer h.mu.Unlock()

	for i := range h.Levels {
		h.Levels[i] = nil
	}
	h.LastIndex = 0
}

// Signal represents a trading signal
type Signal struct {
	Symbol     string      `json:"symbol"`
	Type       string      `json:"type"`
	Direction  string      `json:"direction"`
	Price      float64     `json:"price"`
	Confidence float64     `json:"confidence"`
	Indicators []Indicator `json:"indicators"`
	Timestamp  time.Time   `json:"timestamp"`
}

// Indicator represents a technical indicator
type Indicator struct {
	Name   string      `json:"name"`
	Value  float64     `json:"value"`
	Params interface{} `json:"params"`
}

// PriceUpdate represents a price update
type PriceUpdate struct {
	Symbol      string    `json:"symbol"`
	TokenName   string    `json:"token_name,omitempty"`
	Price       float64   `json:"price"`
	Volume      float64   `json:"volume"`
	MarketCap   float64   `json:"market_cap,omitempty"`
	TotalSupply float64   `json:"total_supply,omitempty"`
	Timestamp   time.Time `json:"timestamp"`
}

// MarketDataProvider defines the market data provider interface
type MarketDataProvider interface {
	// GetPrice returns the current price for a symbol
	GetPrice(ctx context.Context, symbol string) (float64, error)

	// SubscribePrices subscribes to price updates for a list of symbols
	SubscribePrices(ctx context.Context, symbols []string) (<-chan *PriceUpdate, error)

	// GetHistoricalPrices returns historical price data for a symbol
	GetHistoricalPrices(ctx context.Context, symbol string, interval string, limit int) ([]PriceUpdate, error)

	// GetBondingCurve returns the bonding curve information for a token
	GetBondingCurve(ctx context.Context, symbol string) (*BondingCurve, error)

	// SubscribeNewTokens subscribes to new token listings
	SubscribeNewTokens(ctx context.Context) (<-chan *TokenInfo, error)

	// ExecuteTrade executes a trade with the given parameters
	ExecuteTrade(ctx context.Context, params map[string]interface{}) error
}

// TokenInfo represents information about a token
type TokenInfo struct {
	Symbol     string    `json:"symbol"`
	Name       string    `json:"name"`
	MarketCap  float64   `json:"market_cap"`
	Volume     float64   `json:"volume"`
	Supply     int64     `json:"supply"`
	MaxSupply  int64     `json:"max_supply"`
	LaunchTime time.Time `json:"launch_time"`
}

// BondingCurve represents the bonding curve information for a token
type BondingCurve struct {
	Symbol       string    `json:"symbol"`
	CurrentPrice float64   `json:"current_price"`
	BasePrice    float64   `json:"base_price"`
	Slope        float64   `json:"slope"`
	Supply       int64     `json:"supply"`
	MaxSupply    int64     `json:"max_supply"`
	UpdateTime   time.Time `json:"update_time"`
}

// Interval represents a time interval for historical data
type Interval string

const (
	Interval1m  Interval = "1m"  // 1 minute
	Interval5m  Interval = "5m"  // 5 minutes
	Interval15m Interval = "15m" // 15 minutes
	Interval30m Interval = "30m" // 30 minutes
	Interval1h  Interval = "1h"  // 1 hour
	Interval4h  Interval = "4h"  // 4 hours
	Interval1d  Interval = "1d"  // 1 day
	Interval1w  Interval = "1w"  // 1 week
	Interval1M  Interval = "1M"  // 1 month
)
