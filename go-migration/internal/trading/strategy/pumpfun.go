package strategy

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/shopspring/decimal"
	"go.uber.org/zap"

	"github.com/kwanRoshi/B/go-migration/internal/config"
	"github.com/kwanRoshi/B/go-migration/internal/market/pump"
	"github.com/kwanRoshi/B/go-migration/internal/risk"
	"github.com/kwanRoshi/B/go-migration/internal/trading"
)

type PumpFunStrategy struct {
	*BaseStrategy
	engine    *trading.Engine
	riskMgr   *risk.Manager
	provider  *pump.Provider
	secretKey string
	logger    *zap.Logger
	mu        sync.RWMutex
}

func NewPumpFunStrategy(engine *trading.Engine, riskMgr *risk.Manager, provider *pump.Provider, logger *zap.Logger) (*PumpFunStrategy, error) {
	secrets, err := config.LoadSecrets()
	if err != nil {
		return nil, fmt.Errorf("failed to load secrets: %w", err)
	}

	return &PumpFunStrategy{
		BaseStrategy: NewBaseStrategy("pump_fun"),
		engine:      engine,
		riskMgr:     riskMgr,
		provider:    provider,
		secretKey:   secrets.PumpFunKey,
		logger:      logger,
	}, nil
}

func (s *PumpFunStrategy) ExecuteTrade(ctx context.Context, signal *Signal) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if err := s.validateSignal(signal); err != nil {
		return fmt.Errorf("invalid signal: %w", err)
	}

	switch signal.Type {
	case SignalBuy:
		return s.executeBuy(ctx, signal)
	case SignalSell:
		return s.executeSell(ctx, signal)
	default:
		return fmt.Errorf("unknown signal type: %s", signal.Type)
	}
}

func (s *PumpFunStrategy) validateSignal(signal *Signal) error {
	if signal.MarketCap.GreaterThan(s.config.EntryThresholds.MaxMarketCap) {
		return fmt.Errorf("market cap %s exceeds threshold %s", 
			signal.MarketCap, s.config.EntryThresholds.MaxMarketCap)
	}

	if signal.Volume.LessThan(s.config.EntryThresholds.MinVolume) {
		return fmt.Errorf("volume %s below threshold %s",
			signal.Volume, s.config.EntryThresholds.MinVolume)
	}

	return nil
}

func (s *PumpFunStrategy) executeBuy(ctx context.Context, signal *Signal) error {
	position, err := s.engine.GetPosition(ctx, signal.Symbol)
	if err != nil {
		return fmt.Errorf("failed to get position: %w", err)
	}

	if !position.Size.IsZero() {
		return fmt.Errorf("position already exists for %s", signal.Symbol)
	}

	size := s.calculatePositionSize(signal)
	if err := s.riskMgr.ValidateNewPosition(ctx, signal.Symbol, size, signal.Price); err != nil {
		return fmt.Errorf("position validation failed: %w", err)
	}

	order := &trading.Order{
		Symbol:    signal.Symbol,
		Side:      trading.OrderSideBuy,
		Type:      trading.OrderTypeLimit,
		Price:     signal.Price,
		Size:      size,
		Timestamp: time.Now(),
	}

	if err := s.engine.PlaceOrder(ctx, order); err != nil {
		return fmt.Errorf("failed to place buy order: %w", err)
	}

	s.setupProfitTakingOrders(ctx, signal.Symbol, signal.Price, size)
	return nil
}

func (s *PumpFunStrategy) executeSell(ctx context.Context, signal *Signal) error {
	position, err := s.engine.GetPosition(ctx, signal.Symbol)
	if err != nil {
		return fmt.Errorf("failed to get position: %w", err)
	}

	if position.Size.IsZero() {
		return fmt.Errorf("no position exists for %s", signal.Symbol)
	}

	order := &trading.Order{
		Symbol:    signal.Symbol,
		Side:      trading.OrderSideSell,
		Type:      trading.OrderTypeLimit,
		Price:     signal.Price,
		Size:      position.Size,
		Timestamp: time.Now(),
	}

	if err := s.engine.PlaceOrder(ctx, order); err != nil {
		return fmt.Errorf("failed to place sell order: %w", err)
	}

	return nil
}

func (s *PumpFunStrategy) calculatePositionSize(signal *Signal) decimal.Decimal {
	maxSize := s.config.RiskLimits.MaxPositionSize
	suggestedSize := signal.Price.Mul(decimal.NewFromInt(1000))
	
	if suggestedSize.GreaterThan(maxSize) {
		return maxSize
	}
	return suggestedSize
}

func (s *PumpFunStrategy) setupProfitTakingOrders(ctx context.Context, symbol string, entryPrice, size decimal.Decimal) {
	for _, level := range s.config.ProfitTaking.Levels {
		takeProfit := entryPrice.Mul(level.Multiplier)
		partialSize := size.Mul(level.Percentage)

		order := &trading.Order{
			Symbol:    symbol,
			Side:      trading.OrderSideSell,
			Type:      trading.OrderTypeTakeProfit,
			Price:     takeProfit,
			Size:      partialSize,
			Timestamp: time.Now(),
		}

		if err := s.engine.PlaceOrder(ctx, order); err != nil {
			s.logger.Error("failed to place take-profit order",
				zap.String("symbol", symbol),
				zap.String("price", takeProfit.String()),
				zap.String("size", partialSize.String()),
				zap.Error(err))
		}
	}
}
