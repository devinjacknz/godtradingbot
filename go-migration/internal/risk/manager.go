package risk

import (
	"context"
	"fmt"
	"math"
	"time"

	"go.uber.org/zap"

	"github.com/kwanRoshi/B/go-migration/internal/types"
)

// Limits defines risk management limits
type Limits struct {
	MaxPositionSize  float64 `json:"max_position_size"`
	MaxDrawdown      float64 `json:"max_drawdown"`
	MaxDailyLoss     float64 `json:"max_daily_loss"`
	MaxLeverage      float64 `json:"max_leverage"`
	MinMarginLevel   float64 `json:"min_margin_level"`
	MaxConcentration float64 `json:"max_concentration"`
}

// Manager handles risk management
type Manager struct {
	logger *zap.Logger
	limits Limits
}

// NewManager creates a new risk manager
func NewManager(limits Limits, logger *zap.Logger) *Manager {
	return &Manager{
		logger: logger,
		limits: limits,
	}
}

// CheckOrderRisk checks if an order complies with risk limits
func (m *Manager) CheckOrderRisk(ctx context.Context, order *types.Order) error {
	// Check order size
	if order.Quantity > m.limits.MaxPositionSize {
		return fmt.Errorf("order size exceeds limit: %f > %f",
			order.Quantity, m.limits.MaxPositionSize)
	}

	// TODO: Implement more order risk checks
	// - Check margin requirements
	// - Check concentration limits
	// - Check daily loss limits

	return nil
}

// CheckPositionRisk checks if a position complies with risk limits
func (m *Manager) CheckPositionRisk(ctx context.Context, position *types.Position) error {
	// Check position size
	if math.Abs(position.Quantity) > m.limits.MaxPositionSize {
		return fmt.Errorf("position size exceeds limit: %f > %f",
			math.Abs(position.Quantity), m.limits.MaxPositionSize)
	}

	// Check drawdown
	if position.UnrealizedPnL < 0 {
		drawdown := math.Abs(position.UnrealizedPnL) /
			(math.Abs(position.AvgPrice * position.Quantity))
		if drawdown > m.limits.MaxDrawdown {
			return fmt.Errorf("drawdown exceeds limit: %f > %f",
				drawdown, m.limits.MaxDrawdown)
		}
	}

	// TODO: Implement more position risk checks
	// - Check leverage
	// - Check margin level
	// - Check concentration

	return nil
}

// CheckAccountRisk checks overall account risk
func (m *Manager) CheckAccountRisk(ctx context.Context, metrics *types.RiskMetrics) error {
	// Check daily loss
	if metrics.DailyPnL < -m.limits.MaxDailyLoss {
		return fmt.Errorf("daily loss exceeds limit: %f < -%f",
			metrics.DailyPnL, m.limits.MaxDailyLoss)
	}

	// Check margin level
	if metrics.MarginLevel < m.limits.MinMarginLevel {
		return fmt.Errorf("margin level below limit: %f < %f",
			metrics.MarginLevel, m.limits.MinMarginLevel)
	}

	// TODO: Implement more account risk checks
	// - Check total exposure
	// - Check portfolio concentration
	// - Check correlation risk

	return nil
}

// CalculateMetrics calculates risk metrics
func (m *Manager) CalculateMetrics(ctx context.Context, positions []*types.Position) (*types.RiskMetrics, error) {
	metrics := &types.RiskMetrics{
		UserID:     "",
		UpdateTime: time.Now(),
	}

	// Calculate metrics from positions
	for _, pos := range positions {
		positionValue := math.Abs(pos.Quantity * pos.AvgPrice)
		metrics.UsedMargin += positionValue * 0.1 // Example margin requirement
		metrics.TotalEquity += positionValue + pos.UnrealizedPnL
		metrics.DailyPnL += pos.UnrealizedPnL + pos.RealizedPnL
	}

	metrics.AvailableMargin = metrics.TotalEquity - metrics.UsedMargin
	if metrics.UsedMargin > 0 {
		metrics.MarginLevel = metrics.TotalEquity / metrics.UsedMargin * 100
	}

	return metrics, nil
}
