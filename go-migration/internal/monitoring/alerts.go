package monitoring

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/shopspring/decimal"
	"go.uber.org/zap"

	"github.com/kwanRoshi/B/go-migration/internal/metrics"
	"github.com/kwanRoshi/B/go-migration/internal/trading"
)

type AlertType string

const (
	AlertVolumeSurge     AlertType = "volume_surge"
	AlertMarketCapLimit  AlertType = "market_cap_limit"
	AlertPositionLimit   AlertType = "position_limit"
	AlertDrawdownLimit   AlertType = "drawdown_limit"
	AlertProfitTarget    AlertType = "profit_target"
)

type Alert struct {
	Type      AlertType       `json:"type"`
	Symbol    string         `json:"symbol"`
	Threshold decimal.Decimal `json:"threshold"`
	Current   decimal.Decimal `json:"current"`
	Timestamp time.Time      `json:"timestamp"`
}

type Monitor struct {
	logger     *zap.Logger
	engine     *trading.Engine
	alerts     chan *Alert
	thresholds struct {
		volumeSurge    decimal.Decimal
		maxMarketCap   decimal.Decimal
		maxDrawdown    decimal.Decimal
		maxPositionPct decimal.Decimal
	}
	mu sync.RWMutex
}

func NewMonitor(engine *trading.Engine, logger *zap.Logger) *Monitor {
	return &Monitor{
		logger: logger,
		engine: engine,
		alerts: make(chan *Alert, 100),
		thresholds: struct {
			volumeSurge    decimal.Decimal
			maxMarketCap   decimal.Decimal
			maxDrawdown    decimal.Decimal
			maxPositionPct decimal.Decimal
		}{
			volumeSurge:    decimal.NewFromFloat(3.0),    // 300% increase
			maxMarketCap:   decimal.NewFromInt(30000),    // $30k
			maxDrawdown:    decimal.NewFromFloat(0.15),   // 15%
			maxPositionPct: decimal.NewFromFloat(0.1),    // 10%
		},
	}
}

func (m *Monitor) Start(ctx context.Context) error {
	go m.monitorMetrics(ctx)
	return nil
}

func (m *Monitor) GetAlerts() <-chan *Alert {
	return m.alerts
}

func (m *Monitor) monitorMetrics(ctx context.Context) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := m.checkThresholds(ctx); err != nil {
				m.logger.Error("failed to check thresholds", zap.Error(err))
			}
		}
	}
}

func (m *Monitor) checkThresholds(ctx context.Context) error {
	m.mu.RLock()
	defer m.mu.RUnlock()

	// Check volume surges
	volumes := metrics.GetVolumes()
	for symbol, volume := range volumes {
		prevVolume := metrics.GetPreviousVolume(symbol)
		if !prevVolume.IsZero() {
			increase := volume.Div(prevVolume)
			if increase.GreaterThan(m.thresholds.volumeSurge) {
				m.sendAlert(&Alert{
					Type:      AlertVolumeSurge,
					Symbol:    symbol,
					Threshold: m.thresholds.volumeSurge,
					Current:   increase,
					Timestamp: time.Now(),
				})
			}
		}
	}

	// Check market caps
	marketCaps := metrics.GetMarketCaps()
	for symbol, marketCap := range marketCaps {
		if marketCap.GreaterThan(m.thresholds.maxMarketCap) {
			m.sendAlert(&Alert{
				Type:      AlertMarketCapLimit,
				Symbol:    symbol,
				Threshold: m.thresholds.maxMarketCap,
				Current:   marketCap,
				Timestamp: time.Now(),
			})
		}
	}

	// Check positions
	positions, err := m.engine.GetAllPositions(ctx)
	if err != nil {
		return fmt.Errorf("failed to get positions: %w", err)
	}

	for _, pos := range positions {
		// Check drawdown
		if pos.UnrealizedPnL.LessThan(decimal.Zero) {
			drawdown := pos.UnrealizedPnL.Abs().Div(pos.Size.Mul(pos.EntryPrice))
			if drawdown.GreaterThan(m.thresholds.maxDrawdown) {
				m.sendAlert(&Alert{
					Type:      AlertDrawdownLimit,
					Symbol:    pos.Symbol,
					Threshold: m.thresholds.maxDrawdown,
					Current:   drawdown,
					Timestamp: time.Now(),
				})
			}
		}

		// Check position size
		totalValue := pos.Size.Mul(pos.CurrentPrice)
		portfolioValue := m.engine.GetPortfolioValue(ctx)
		if !portfolioValue.IsZero() {
			positionPct := totalValue.Div(portfolioValue)
			if positionPct.GreaterThan(m.thresholds.maxPositionPct) {
				m.sendAlert(&Alert{
					Type:      AlertPositionLimit,
					Symbol:    pos.Symbol,
					Threshold: m.thresholds.maxPositionPct,
					Current:   positionPct,
					Timestamp: time.Now(),
				})
			}
		}
	}

	return nil
}

func (m *Monitor) sendAlert(alert *Alert) {
	select {
	case m.alerts <- alert:
	default:
		m.logger.Warn("alert channel full, dropping alert",
			zap.String("type", string(alert.Type)),
			zap.String("symbol", alert.Symbol))
	}
}
