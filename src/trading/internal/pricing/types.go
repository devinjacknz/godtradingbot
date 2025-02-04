package pricing

import (
	"sync"
	"time"
)

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

// PriceLevel represents a price level with additional metadata
type PriceLevel struct {
	Symbol    string                 `json:"symbol"`
	Price     float64                `json:"price"`
	Volume    float64                `json:"volume"`
	Bid       float64                `json:"bid"`
	Ask       float64                `json:"ask"`
	Spread    float64                `json:"spread"`
	VWAP      float64               `json:"vwap"`
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
