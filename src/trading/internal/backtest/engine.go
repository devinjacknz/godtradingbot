package backtest

import (
	"context"
	"fmt"
	"math"
	"sync"
	"time"

	"go.uber.org/zap"

	"github.com/devinjacknz/tradingbot/internal/pricing"
	"github.com/devinjacknz/tradingbot/internal/types"
)

// Engine manages backtesting process
type Engine struct {
	config    Config
	logger    *zap.Logger
	engine    *pricing.Engine
	portfolio *Portfolio
	results   *Result
	dataFeed  DataFeed
	storage   Storage
	analyzer  *SignalAnalyzer
	mu        sync.RWMutex
}

// NewEngine creates a new backtest engine
func NewEngine(config Config, logger *zap.Logger, engine *pricing.Engine, storage Storage) *Engine {
	return &Engine{
		config:  config,
		logger:  logger,
		engine:  engine,
		storage: storage,
		portfolio: &Portfolio{
			Balance:    config.InitialBalance,
			Positions:  make(map[string]*Position),
			Commission: config.Commission,
			Slippage:   config.Slippage,
		},
		results: &Result{
			Trades:  make([]*Trade, 0),
			Metrics: NewMetrics(),
		},
	}
}

// Run executes the backtest
func (e *Engine) Run(ctx context.Context) (*Result, error) {
	// Initialize data feed
	feed, err := e.initDataFeed(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize data feed: %w", err)
	}
	e.dataFeed = feed
	defer e.dataFeed.Close()

	// Subscribe to signals
	signals := e.engine.GetSignals()
	var collectedSignals []*pricing.Signal

	// Process historical data
	for e.dataFeed.Next() {
		select {
		case <-ctx.Done():
			return e.results, nil
		default:
			// Process next price update
			update := e.dataFeed.Current()
			if err := e.handleUpdate(update); err != nil {
				e.logger.Error("Failed to process update",
					zap.Error(err))
				continue
			}

			// Process signals
			select {
			case signal := <-signals:
				// Convert types.Signal to pricing.Signal
				pricingSignal := convertSignal(signal)
				
				// Collect signal for analysis
				collectedSignals = append(collectedSignals, pricingSignal)

				// Process signal
				if err := e.handleSignal(pricingSignal); err != nil {
					e.logger.Error("Failed to process signal",
						zap.Error(err))
				}
			default:
			}

			// Update metrics
			e.updateMetrics()
		}
	}

	// Calculate final results
	e.calculateResults()

	// Save results
	if err := e.storage.SaveResult(ctx, e.results); err != nil {
		e.logger.Error("Failed to save results", zap.Error(err))
	}

	// Save signals
	if err := e.storage.SaveSignals(ctx, collectedSignals); err != nil {
		e.logger.Error("Failed to save signals", zap.Error(err))
	}

	return e.results, nil
}

// Helper methods

func convertSignal(signal *types.Signal) *pricing.Signal {
	// Convert indicators
	indicators := make([]pricing.Indicator, len(signal.Indicators))
	for i, ind := range signal.Indicators {
		indicators[i] = pricing.Indicator{
			Name:   ind.Name,
			Value:  ind.Value,
			Params: ind.Params,
		}
	}

	return &pricing.Signal{
		Symbol:     signal.Symbol,
		Type:      signal.Type,
		Direction: signal.Direction,
		Price:     signal.Price,
		Confidence: signal.Confidence,
		Timestamp: signal.Timestamp,
		Indicators: indicators,
	}
}

func (e *Engine) initDataFeed(ctx context.Context) (DataFeed, error) {
	switch e.config.DataSource {
	case "csv":
		return NewCSVDataFeed(e.config.Symbol)
	case "postgres":
		config := PostgresConfig{
			Host:     "localhost",
			Port:     5432,
			User:     "postgres",
			Password: "postgres",
			DBName:   "tradingbot",
			SSLMode:  "disable",
		}
		return NewPostgresDataFeed(ctx, config, e.logger, e.config.Symbol, e.config.StartTime, e.config.EndTime, e.config.Interval)
	default:
		return nil, fmt.Errorf("unsupported data source: %s", e.config.DataSource)
	}
}

func (e *Engine) handleUpdate(update *pricing.PriceLevel) error {
	// Update positions P&L
	for symbol, pos := range e.portfolio.Positions {
		if symbol == update.Symbol {
			// Calculate unrealized P&L
			pnl := e.calculatePnL(pos, update.Price)

			// Check for stop loss / take profit
			if e.shouldClosePosition(pos, pnl) {
				if err := e.closePosition(pos, update); err != nil {
					return fmt.Errorf("failed to close position: %w", err)
				}
			}
		}
	}
	return nil
}

func (e *Engine) handleSignal(signal *pricing.Signal) error {
	// Check if we have an open position for this symbol
	if pos, exists := e.portfolio.Positions[signal.Symbol]; exists {
		// Check if signal suggests closing position
		if e.shouldReversePosition(pos, signal) {
			if err := e.closePosition(pos, &pricing.PriceLevel{
				Symbol:    signal.Symbol,
				Price:     signal.Price,
				Timestamp: signal.Timestamp,
			}); err != nil {
				return err
			}
		}
	} else {
		// Open new position
		if err := e.openPosition(signal); err != nil {
			return err
		}
	}
	return nil
}

func (e *Engine) calculatePnL(pos *Position, currentPrice float64) float64 {
	if pos.Direction == "long" {
		return (currentPrice - pos.EntryPrice) * pos.Quantity
	}
	return (pos.EntryPrice - currentPrice) * pos.Quantity
}

func (e *Engine) shouldClosePosition(pos *Position, pnl float64) bool {
	// Implement stop loss / take profit logic
	stopLoss := -pos.EntryPrice * 0.02  // 2% stop loss
	takeProfit := pos.EntryPrice * 0.05 // 5% take profit
	return pnl <= stopLoss || pnl >= takeProfit
}

func (e *Engine) shouldReversePosition(pos *Position, signal *pricing.Signal) bool {
	return (pos.Direction == "long" && signal.Direction == "short") ||
		(pos.Direction == "short" && signal.Direction == "long")
}

func (e *Engine) openPosition(signal *pricing.Signal) error {
	// Calculate position size
	size := e.calculatePositionSize(signal)
	if size <= 0 {
		return fmt.Errorf("invalid position size")
	}

	// Apply slippage
	entryPrice := signal.Price * (1 + e.portfolio.Slippage)
	commission := entryPrice * size * e.portfolio.Commission

	// Check if we have enough balance
	cost := entryPrice*size + commission
	if cost > e.portfolio.Balance {
		return fmt.Errorf("insufficient balance")
	}

	// Open position
	e.portfolio.Positions[signal.Symbol] = &Position{
		Symbol:     signal.Symbol,
		Direction:  signal.Direction,
		EntryPrice: entryPrice,
		Quantity:   size,
		EntryTime:  signal.Timestamp,
	}

	// Update balance
	e.portfolio.Balance -= cost

	return nil
}

func (e *Engine) closePosition(pos *Position, update *pricing.PriceLevel) error {
	// Apply slippage
	exitPrice := update.Price * (1 - e.portfolio.Slippage)
	commission := exitPrice * pos.Quantity * e.portfolio.Commission

	// Calculate P&L
	pnl := e.calculatePnL(pos, exitPrice)

	// Record trade
	e.results.Trades = append(e.results.Trades, &Trade{
		Symbol:     pos.Symbol,
		Direction:  pos.Direction,
		EntryTime:  pos.EntryTime,
		ExitTime:   update.Timestamp,
		EntryPrice: pos.EntryPrice,
		ExitPrice:  exitPrice,
		Quantity:   pos.Quantity,
		PnL:        pnl,
		Commission: commission,
		Slippage:   e.portfolio.Slippage,
	})

	// Update balance
	e.portfolio.Balance += exitPrice*pos.Quantity - commission

	// Remove position
	delete(e.portfolio.Positions, pos.Symbol)

	return nil
}

func (e *Engine) calculatePositionSize(signal *pricing.Signal) float64 {
	// Implement position sizing logic (e.g., fixed fractional)
	riskPerTrade := 0.02 // 2% risk per trade
	availableBalance := e.portfolio.Balance

	return (availableBalance * riskPerTrade) / signal.Price
}

func (e *Engine) calculateResults() {
	// Calculate basic metrics
	var totalPnL, grossProfit, grossLoss float64

	for _, trade := range e.results.Trades {
		if trade.PnL > 0 {
			e.results.WinningTrades++
			grossProfit += trade.PnL
		} else {
			e.results.LosingTrades++
			grossLoss += -trade.PnL
		}
		totalPnL += trade.PnL
	}

	e.results.TotalTrades = len(e.results.Trades)
	if e.results.TotalTrades > 0 {
		e.results.WinRate = float64(e.results.WinningTrades) / float64(e.results.TotalTrades)
	}
	if grossLoss > 0 {
		e.results.ProfitFactor = grossProfit / grossLoss
	}

	e.results.FinalBalance = e.portfolio.Balance
	e.results.TotalReturn = (e.portfolio.Balance - e.config.InitialBalance) / e.config.InitialBalance
	e.results.AnnualizedReturn = calculateAnnualizedReturn(e.results.TotalReturn, e.config.StartTime, e.config.EndTime)

	// Calculate max drawdown
	if len(e.results.Metrics.DrawdownSeries) > 0 {
		maxDrawdown := e.results.Metrics.DrawdownSeries[0]
		for _, dd := range e.results.Metrics.DrawdownSeries {
			if dd > maxDrawdown {
				maxDrawdown = dd
			}
		}
		e.results.MaxDrawdown = maxDrawdown
	}
}

// Helper functions

func calculateAnnualizedReturn(totalReturn float64, start, end time.Time) float64 {
	years := end.Sub(start).Hours() / (24 * 365)
	if years == 0 {
		return 0
	}
	return math.Pow(1+totalReturn, 1/years) - 1
}
