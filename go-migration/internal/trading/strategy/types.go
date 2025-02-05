package strategy

import (
	"context"
	"time"

	"github.com/shopspring/decimal"
)

type Signal struct {
	Symbol    string          `json:"symbol"`
	Price     decimal.Decimal `json:"price"`
	Volume    decimal.Decimal `json:"volume"`
	MarketCap decimal.Decimal `json:"market_cap"`
	Type      SignalType      `json:"type"`
	Timestamp time.Time       `json:"timestamp"`
}

type SignalType string

const (
	SignalBuy  SignalType = "buy"
	SignalSell SignalType = "sell"
)

type Metrics struct {
	TotalTrades      int64           `json:"total_trades"`
	WinningTrades    int64           `json:"winning_trades"`
	TotalPnL         decimal.Decimal `json:"total_pnl"`
	MaxDrawdown      decimal.Decimal `json:"max_drawdown"`
	LastTradeTime    time.Time       `json:"last_trade_time"`
	ActivePositions  int64           `json:"active_positions"`
	AvgTradeHolding  time.Duration   `json:"avg_trade_holding"`
	SuccessRate      decimal.Decimal `json:"success_rate"`
}

type Config struct {
	EntryThresholds struct {
		MaxMarketCap decimal.Decimal `json:"max_market_cap"`
		MinVolume    decimal.Decimal `json:"min_volume"`
	} `json:"entry_thresholds"`
	ProfitTaking struct {
		Levels []struct {
			Multiplier decimal.Decimal `json:"multiplier"`
			Percentage decimal.Decimal `json:"percentage"`
		} `json:"levels"`
	} `json:"profit_taking"`
	RiskLimits struct {
		MaxPositionSize decimal.Decimal `json:"max_position_size"`
		MaxDrawdown     decimal.Decimal `json:"max_drawdown"`
		MaxDailyLoss    decimal.Decimal `json:"max_daily_loss"`
	} `json:"risk_limits"`
}

type Strategy interface {
	Initialize(config Config) error
	ExecuteTrade(ctx context.Context, signal *Signal) error
	GetMetrics() *Metrics
	GetName() string
	GetConfig() *Config
}
