package pricing

import (
	"context"
	"fmt"
	"sync"
	"time"

	"go.uber.org/zap"

	"github.com/kwanRoshi/B/go-migration/internal/analysis"
	"github.com/kwanRoshi/B/go-migration/internal/types"
)

// Config represents pricing engine configuration
type Config struct {
	Symbols        []string      `json:"symbols"`
	UpdateInterval time.Duration `json:"update_interval"`
	HistorySize    int           `json:"history_size"`
	Indicators     []string      `json:"indicators"`
	SignalParams   SignalParams  `json:"signal_params"`
}

// SignalParams represents signal generation parameters
type SignalParams struct {
	MinConfidence float64 `json:"min_confidence"`
	MaxVolatility float64 `json:"max_volatility"`
	TimeRange     struct {
		Start string `json:"start"`
		End   string `json:"end"`
	} `json:"time_range"`
}

// Engine manages price updates and signal generation
type Engine struct {
	logger     *zap.Logger
	config     Config
	validator  *Validator
	indicators []analysis.IndicatorCalculator
	history    map[string]*types.PriceHistory
	signals    chan *types.Signal
	mu         sync.RWMutex
}

// IndicatorFunc defines a function that calculates an indicator
type IndicatorFunc func(history *PriceHistory) (*Indicator, error)

// NewEngine creates a new pricing engine
func NewEngine(config Config, logger *zap.Logger) *Engine {
	e := &Engine{
		logger:     logger,
		config:     config,
		validator:  NewValidator(),
		indicators: make([]analysis.IndicatorCalculator, 0),
		history:    make(map[string]*types.PriceHistory),
		signals:    make(chan *types.Signal, 100),
	}

	// Initialize indicators
	for _, name := range config.Indicators {
		if indicator := e.createIndicator(name); indicator != nil {
			e.indicators = append(e.indicators, indicator)
		}
	}

	// Initialize price history
	for _, symbol := range config.Symbols {
		e.history[symbol] = types.NewPriceHistory(config.HistorySize)
	}

	return e
}

// Start starts the pricing engine
func (e *Engine) Start(ctx context.Context) error {
	// Start signal generation
	go e.generateSignals(ctx)

	return nil
}

// ProcessUpdate processes a price update
func (e *Engine) ProcessUpdate(update *types.PriceUpdate) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	// Get price history
	history, ok := e.history[update.Symbol]
	if !ok {
		return fmt.Errorf("unknown symbol: %s", update.Symbol)
	}

	// Add price to history
	history.Add(&types.PriceLevel{
		Symbol:    update.Symbol,
		Price:     update.Price,
		Volume:    update.Volume,
		Timestamp: update.Timestamp,
	})

	return nil
}

// GetSignals returns the signal channel
func (e *Engine) GetSignals() <-chan *types.Signal {
	return e.signals
}

// Internal methods

func (e *Engine) generateSignals(ctx context.Context) {
	ticker := time.NewTicker(e.config.UpdateInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			e.mu.RLock()
			for symbol, history := range e.history {
				// Calculate indicators
				for _, indicator := range e.indicators {
					if err := indicator.Calculate(history); err != nil {
						e.logger.Error("Failed to calculate indicator",
							zap.Error(err),
							zap.String("symbol", symbol),
							zap.String("indicator", indicator.Name()))
						continue
					}
				}

				// Generate signals
				if signal := e.analyzeIndicators(symbol, history); signal != nil {
					if e.validator.Validate(signal) {
						select {
						case e.signals <- signal:
						default:
							e.logger.Warn("Signal channel full")
						}
					}
				}
			}
			e.mu.RUnlock()
		}
	}
}

func (e *Engine) analyzeIndicators(symbol string, history *types.PriceHistory) *types.Signal {
	// Get current price level
	current := history.Last()
	if current == nil {
		return nil
	}

	// Convert indicators to signal format
	indicators := make([]types.Indicator, len(e.indicators))
	for i, ind := range e.indicators {
		indicators[i] = types.Indicator{
			Name:   ind.Name(),
			Value:  ind.Value(),
			Params: ind.Params(),
		}
	}

	// Analyze RSI
	for _, ind := range e.indicators {
		if ind.Name() == "RSI" {
			value := ind.Value()
			if value <= 30 {
				return &types.Signal{
					Symbol:     symbol,
					Type:       "entry",
					Direction:  "long",
					Price:      current.Price,
					Confidence: (30 - value) / 30,
					Timestamp:  current.Timestamp,
					Indicators: indicators,
				}
			}
			if value >= 70 {
				return &types.Signal{
					Symbol:     symbol,
					Type:       "entry",
					Direction:  "short",
					Price:      current.Price,
					Confidence: (value - 70) / 30,
					Timestamp:  current.Timestamp,
					Indicators: indicators,
				}
			}
		}
	}

	// Analyze MACD
	for _, ind := range e.indicators {
		if ind.Name() == "MACD" {
			value := ind.Value()
			params := ind.Params().(map[string]interface{})
			signal := params["signal"].(float64)

			if value > signal {
				return &types.Signal{
					Symbol:     symbol,
					Type:       "entry",
					Direction:  "long",
					Price:      current.Price,
					Confidence: (value - signal) / (0.001 * current.Price),
					Timestamp:  current.Timestamp,
					Indicators: indicators,
				}
			}
			if value < signal {
				return &types.Signal{
					Symbol:     symbol,
					Type:       "entry",
					Direction:  "short",
					Price:      current.Price,
					Confidence: (signal - value) / (0.001 * current.Price),
					Timestamp:  current.Timestamp,
					Indicators: indicators,
				}
			}
		}
	}

	// Analyze Bollinger Bands
	for _, ind := range e.indicators {
		if ind.Name() == "BB" {
			params := ind.Params().(map[string]interface{})
			upper := params["upper"].(float64)
			lower := params["lower"].(float64)
			middle := params["middle"].(float64)

			if current.Price <= lower {
				return &types.Signal{
					Symbol:     symbol,
					Type:       "entry",
					Direction:  "long",
					Price:      current.Price,
					Confidence: (lower - current.Price) / (lower - middle),
					Timestamp:  current.Timestamp,
					Indicators: indicators,
				}
			}
			if current.Price >= upper {
				return &types.Signal{
					Symbol:     symbol,
					Type:       "entry",
					Direction:  "short",
					Price:      current.Price,
					Confidence: (current.Price - upper) / (upper - middle),
					Timestamp:  current.Timestamp,
					Indicators: indicators,
				}
			}
		}
	}

	return nil
}

func (e *Engine) createIndicator(name string) analysis.IndicatorCalculator {
	switch name {
	case "RSI":
		return analysis.NewRSIIndicator(14)
	case "MACD":
		return analysis.NewMACDIndicator(12, 26, 9)
	case "BB":
		return analysis.NewBollingerBandsIndicator(20, 2)
	default:
		e.logger.Warn("Unknown indicator", zap.String("name", name))
		return nil
	}
}
