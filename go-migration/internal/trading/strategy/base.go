package strategy

import (
	"sync"
	"time"

	"github.com/shopspring/decimal"
)

type BaseStrategy struct {
	name    string
	config  Config
	metrics Metrics
	mu      sync.RWMutex
}

func NewBaseStrategy(name string) *BaseStrategy {
	return &BaseStrategy{
		name: name,
		metrics: Metrics{
			TotalPnL:    decimal.Zero,
			MaxDrawdown: decimal.Zero,
			SuccessRate: decimal.Zero,
		},
	}
}

func (s *BaseStrategy) Initialize(config Config) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.config = config
	return nil
}

func (s *BaseStrategy) GetName() string {
	return s.name
}

func (s *BaseStrategy) GetConfig() *Config {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return &s.config
}

func (s *BaseStrategy) GetMetrics() *Metrics {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return &s.metrics
}

func (s *BaseStrategy) updateMetrics(pnl decimal.Decimal, success bool) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.metrics.TotalTrades++
	s.metrics.TotalPnL = s.metrics.TotalPnL.Add(pnl)
	s.metrics.LastTradeTime = time.Now()

	if success {
		s.metrics.WinningTrades++
	}

	if s.metrics.TotalTrades > 0 {
		s.metrics.SuccessRate = decimal.NewFromInt(s.metrics.WinningTrades).
			Div(decimal.NewFromInt(s.metrics.TotalTrades))
	}

	if pnl.LessThan(decimal.Zero) {
		drawdown := pnl.Abs()
		if drawdown.GreaterThan(s.metrics.MaxDrawdown) {
			s.metrics.MaxDrawdown = drawdown
		}
	}
}
