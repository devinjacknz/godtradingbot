package backtest

import (
	"context"
	"time"

	"github.com/devinjacknz/tradingbot/internal/pricing"
)

// Config represents backtest configuration
type Config struct {
	StartTime      time.Time     `yaml:"start_time"`
	EndTime        time.Time     `yaml:"end_time"`
	InitialBalance float64       `yaml:"initial_balance"`
	Commission     float64       `yaml:"commission"`
	Slippage       float64       `yaml:"slippage"`
	DataSource     string        `yaml:"data_source"`
	Symbol         string        `yaml:"symbol"`
	Interval       time.Duration `yaml:"interval"`
}

// Result represents backtest results
type Result struct {
	TotalTrades      int      `json:"total_trades"`
	WinningTrades    int      `json:"winning_trades"`
	LosingTrades     int      `json:"losing_trades"`
	WinRate          float64  `json:"win_rate"`
	ProfitFactor     float64  `json:"profit_factor"`
	SharpeRatio      float64  `json:"sharpe_ratio"`
	MaxDrawdown      float64  `json:"max_drawdown"`
	FinalBalance     float64  `json:"final_balance"`
	TotalReturn      float64  `json:"total_return"`
	AnnualizedReturn float64  `json:"annualized_return"`
	Trades           []*Trade `json:"trades"`
	Metrics          *Metrics `json:"metrics"`
}

// Trade represents a simulated trade
type Trade struct {
	Symbol     string    `json:"symbol"`
	Direction  string    `json:"direction"`
	EntryTime  time.Time `json:"entry_time"`
	ExitTime   time.Time `json:"exit_time"`
	EntryPrice float64   `json:"entry_price"`
	ExitPrice  float64   `json:"exit_price"`
	Quantity   float64   `json:"quantity"`
	PnL        float64   `json:"pnl"`
	Commission float64   `json:"commission"`
	Slippage   float64   `json:"slippage"`
	Signal     *pricing.Signal `json:"signal"`
}

// Portfolio tracks positions and balance
type Portfolio struct {
	Balance    float64
	Positions  map[string]*Position
	Commission float64
	Slippage   float64
}

// Position represents an open position
type Position struct {
	Symbol     string
	Direction  string
	EntryPrice float64
	Quantity   float64
	EntryTime  time.Time
}

// DataFeed defines interface for historical data feeds
type DataFeed interface {
	Next() bool
	Current() *pricing.PriceLevel
	Close() error
}

// Storage defines interface for backtest data persistence
type Storage interface {
	SaveResult(ctx context.Context, result *Result) error
	SaveSignals(ctx context.Context, signals []*pricing.Signal) error
	LoadResult(ctx context.Context, id string) (*Result, error)
	LoadSignals(ctx context.Context, symbol string, start, end time.Time) ([]*pricing.Signal, error)
}
