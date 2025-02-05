package strategy

import (
	"context"
	"testing"
	"time"

	"github.com/shopspring/decimal"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"go.uber.org/zap"

	"github.com/kwanRoshi/B/go-migration/internal/market/pump"
	"github.com/kwanRoshi/B/go-migration/internal/risk"
	"github.com/kwanRoshi/B/go-migration/internal/trading"
)

type MockEngine struct {
	mock.Mock
}

func (m *MockEngine) PlaceOrder(ctx context.Context, order *trading.Order) error {
	args := m.Called(ctx, order)
	return args.Error(0)
}

func (m *MockEngine) GetPosition(ctx context.Context, symbol string) (*trading.Position, error) {
	args := m.Called(ctx, symbol)
	return args.Get(0).(*trading.Position), args.Error(1)
}

type MockRiskManager struct {
	mock.Mock
}

func (m *MockRiskManager) ValidateNewPosition(ctx context.Context, symbol string, size, price decimal.Decimal) error {
	args := m.Called(ctx, symbol, size, price)
	return args.Error(0)
}

func TestPumpFunStrategy_ExecuteTrade_Buy(t *testing.T) {
	// Setup
	ctx := context.Background()
	mockEngine := new(MockEngine)
	mockRiskMgr := new(MockRiskManager)
	logger, _ := zap.NewDevelopment()

	strategy := &PumpFunStrategy{
		BaseStrategy: NewBaseStrategy("pump_fun_test"),
		engine:      mockEngine,
		riskMgr:     mockRiskMgr,
		logger:      logger,
	}

	config := Config{
		EntryThresholds: struct {
			MaxMarketCap decimal.Decimal `json:"max_market_cap"`
			MinVolume    decimal.Decimal `json:"min_volume"`
		}{
			MaxMarketCap: decimal.NewFromInt(30000),
			MinVolume:    decimal.NewFromInt(1000),
		},
		RiskLimits: struct {
			MaxPositionSize decimal.Decimal `json:"max_position_size"`
			MaxDrawdown     decimal.Decimal `json:"max_drawdown"`
			MaxDailyLoss    decimal.Decimal `json:"max_daily_loss"`
		}{
			MaxPositionSize: decimal.NewFromInt(1000),
		},
	}
	strategy.Initialize(config)

	// Test data
	symbol := "TEST"
	price := decimal.NewFromInt(100)
	size := decimal.NewFromInt(10)
	marketCap := decimal.NewFromInt(25000)
	volume := decimal.NewFromInt(2000)

	signal := &Signal{
		Symbol:    symbol,
		Price:     price,
		MarketCap: marketCap,
		Volume:    volume,
		Type:      SignalBuy,
		Timestamp: time.Now(),
	}

	// Mock expectations
	mockEngine.On("GetPosition", ctx, symbol).Return(&trading.Position{
		Symbol: symbol,
		Size:   decimal.Zero,
	}, nil)

	mockRiskMgr.On("ValidateNewPosition", ctx, symbol, mock.Anything, price).Return(nil)

	mockEngine.On("PlaceOrder", ctx, mock.MatchedBy(func(order *trading.Order) bool {
		return order.Symbol == symbol &&
			order.Side == trading.OrderSideBuy &&
			order.Type == trading.OrderTypeLimit &&
			order.Price.Equal(price)
	})).Return(nil)

	// Execute test
	err := strategy.ExecuteTrade(ctx, signal)

	// Verify
	assert.NoError(t, err)
	mockEngine.AssertExpectations(t)
	mockRiskMgr.AssertExpectations(t)
}

func TestPumpFunStrategy_ExecuteTrade_Sell(t *testing.T) {
	// Setup
	ctx := context.Background()
	mockEngine := new(MockEngine)
	mockRiskMgr := new(MockRiskManager)
	logger, _ := zap.NewDevelopment()

	strategy := &PumpFunStrategy{
		BaseStrategy: NewBaseStrategy("pump_fun_test"),
		engine:      mockEngine,
		riskMgr:     mockRiskMgr,
		logger:      logger,
	}

	// Test data
	symbol := "TEST"
	price := decimal.NewFromInt(100)
	size := decimal.NewFromInt(10)
	marketCap := decimal.NewFromInt(25000)
	volume := decimal.NewFromInt(2000)

	signal := &Signal{
		Symbol:    symbol,
		Price:     price,
		MarketCap: marketCap,
		Volume:    volume,
		Type:      SignalSell,
		Timestamp: time.Now(),
	}

	// Mock expectations
	mockEngine.On("GetPosition", ctx, symbol).Return(&trading.Position{
		Symbol: symbol,
		Size:   size,
	}, nil)

	mockEngine.On("PlaceOrder", ctx, mock.MatchedBy(func(order *trading.Order) bool {
		return order.Symbol == symbol &&
			order.Side == trading.OrderSideSell &&
			order.Type == trading.OrderTypeLimit &&
			order.Price.Equal(price) &&
			order.Size.Equal(size)
	})).Return(nil)

	// Execute test
	err := strategy.ExecuteTrade(ctx, signal)

	// Verify
	assert.NoError(t, err)
	mockEngine.AssertExpectations(t)
}

func TestPumpFunStrategy_ExecuteTrade_InvalidMarketCap(t *testing.T) {
	// Setup
	ctx := context.Background()
	mockEngine := new(MockEngine)
	mockRiskMgr := new(MockRiskManager)
	logger, _ := zap.NewDevelopment()

	strategy := &PumpFunStrategy{
		BaseStrategy: NewBaseStrategy("pump_fun_test"),
		engine:      mockEngine,
		riskMgr:     mockRiskMgr,
		logger:      logger,
	}

	config := Config{
		EntryThresholds: struct {
			MaxMarketCap decimal.Decimal `json:"max_market_cap"`
			MinVolume    decimal.Decimal `json:"min_volume"`
		}{
			MaxMarketCap: decimal.NewFromInt(30000),
			MinVolume:    decimal.NewFromInt(1000),
		},
	}
	strategy.Initialize(config)

	// Test data with market cap exceeding threshold
	signal := &Signal{
		Symbol:    "TEST",
		Price:     decimal.NewFromInt(100),
		MarketCap: decimal.NewFromInt(35000), // Exceeds max
		Volume:    decimal.NewFromInt(2000),
		Type:      SignalBuy,
		Timestamp: time.Now(),
	}

	// Execute test
	err := strategy.ExecuteTrade(ctx, signal)

	// Verify
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "market cap")
}
