package server

import "time"

// ResultResponse represents the response for a backtest result
type ResultResponse struct {
	ID               string    `json:"id"`
	Symbol           string    `json:"symbol"`
	StartTime        time.Time `json:"start_time"`
	EndTime          time.Time `json:"end_time"`
	TotalTrades      int       `json:"total_trades"`
	WinningTrades    int       `json:"winning_trades"`
	LosingTrades     int       `json:"losing_trades"`
	WinRate          float64   `json:"win_rate"`
	ProfitFactor     float64   `json:"profit_factor"`
	SharpeRatio      float64   `json:"sharpe_ratio"`
	MaxDrawdown      float64   `json:"max_drawdown"`
	FinalBalance     float64   `json:"final_balance"`
	TotalReturn      float64   `json:"total_return"`
	AnnualizedReturn float64   `json:"annualized_return"`
	Trades           []Trade   `json:"trades"`
	Metrics          *Metrics  `json:"metrics"`
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
}

// Metrics represents performance metrics
type Metrics struct {
	DailyReturns     []float64          `json:"daily_returns"`
	MonthlyReturns   []float64          `json:"monthly_returns"`
	ReturnsBySymbol  map[string]float64 `json:"returns_by_symbol"`
	DrawdownSeries   []float64          `json:"drawdown_series"`
	VolatilitySeries []float64          `json:"volatility_series"`
}

// Point represents a time series data point
type Point struct {
	Time  time.Time `json:"time"`
	Value float64   `json:"value"`
}

// Return represents a return for a specific period
type Return struct {
	Period string  `json:"period"`
	Return float64 `json:"return"`
} 