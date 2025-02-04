package risk

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"time"

	"go.uber.org/zap"

	"github.com/devinjacknz/tradingbot/internal/types"
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

// TradingMode represents different trading modes
type TradingMode string

const (
	ModeDEXSwap TradingMode = "dex_swap"
	ModePumpFun TradingMode = "pump_fun"
)

// DEXLimits defines risk limits for DEX trading
type DEXLimits struct {
	MaxSlippage     float64 `json:"max_slippage"`
	MinLiquidity    float64 `json:"min_liquidity"`
	MaxImpact       float64 `json:"max_impact"`
	MaxSpread       float64 `json:"max_spread"`
	MinPoolSize     float64 `json:"min_pool_size"`
}

// PumpFunLimits defines risk limits for meme trading
type PumpFunLimits struct {
	MinMarketCap    float64 `json:"min_market_cap"`
	MinVolume       float64 `json:"min_volume"`
	MinHolders      int     `json:"min_holders"`
	MaxVolatility   float64 `json:"max_volatility"`
	MinSocialScore  float64 `json:"min_social_score"`
}

// Limits defines risk management limits
type Limits struct {
	MaxPositionSize  float64 `json:"max_position_size"`
	MaxDrawdown      float64 `json:"max_drawdown"`
	MaxDailyLoss     float64 `json:"max_daily_loss"`
	MaxLeverage      float64 `json:"max_leverage"`
	MinMarginLevel   float64 `json:"min_margin_level"`
	MaxConcentration float64 `json:"max_concentration"`
	DEX             DEXLimits    `json:"dex_limits"`
	PumpFun         PumpFunLimits `json:"pump_fun_limits"`
}

// Manager handles risk management
type Manager struct {
	logger *zap.Logger
	limits Limits
	mode   TradingMode
	aiClient *AIClient
}

// AIClient handles AI-driven risk analysis
type AIClient struct {
	baseURL string
	client  *http.Client
}

// NewManager creates a new risk manager
func NewManager(limits Limits, mode TradingMode, logger *zap.Logger) *Manager {
	if logger == nil {
		logger = zap.NewNop()
	}

	return &Manager{
		logger: logger,
		limits: limits,
		mode:   mode,
		aiClient: &AIClient{
			baseURL: "http://localhost:8000",
			client: &http.Client{
				Timeout: 10 * time.Second,
				Transport: &http.Transport{
					MaxIdleConns:        100,
					MaxIdleConnsPerHost: 100,
					IdleConnTimeout:     90 * time.Second,
				},
			},
		},
	}
}

// CheckOrderRisk checks if an order complies with risk limits
func (m *Manager) CheckOrderRisk(ctx context.Context, order *types.Order) error {
	// Check base limits
	if order.Quantity > m.limits.MaxPositionSize {
		return fmt.Errorf("order size exceeds limit: %f > %f",
			order.Quantity, m.limits.MaxPositionSize)
	}

	// Check mode-specific limits
	switch m.mode {
	case ModeDEXSwap:
		if err := m.checkDEXOrderRisk(ctx, order); err != nil {
			return err
		}
	case ModePumpFun:
		if err := m.checkPumpFunOrderRisk(ctx, order); err != nil {
			return err
		}
	}

	// Get AI-driven risk assessment
	riskScore, err := m.getAIRiskScore(ctx, order)
	if err != nil {
		m.logger.Warn("Failed to get AI risk score", zap.Error(err))
	} else if riskScore > 0.7 {
		return fmt.Errorf("AI risk score too high: %f > 0.7", riskScore)
	}

	return nil
}

// CheckPositionRisk checks if a position complies with risk limits
func (m *Manager) CheckPositionRisk(ctx context.Context, position *types.Position) error {
	// Check base position limits
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

	// Check mode-specific position limits
	switch m.mode {
	case ModeDEXSwap:
		if err := m.checkDEXPositionRisk(ctx, position); err != nil {
			return err
		}
	case ModePumpFun:
		if err := m.checkPumpFunPositionRisk(ctx, position); err != nil {
			return err
		}
	}

	// Get AI risk assessment for position
	riskScore, err := m.getAIRiskScore(ctx, &types.Order{
		Symbol:    position.Symbol,
		Quantity:  position.Quantity,
		Price:     position.AvgPrice,
	})
	if err != nil {
		m.logger.Warn("Failed to get AI risk score for position", zap.Error(err))
	} else if riskScore > 0.7 {
		return fmt.Errorf("position AI risk score too high: %f > 0.7", riskScore)
	}

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

// checkDEXOrderRisk validates DEX-specific risk parameters
func (m *Manager) checkDEXOrderRisk(ctx context.Context, order *types.Order) error {
	if order.Slippage > m.limits.DEX.MaxSlippage {
		return fmt.Errorf("slippage too high: %f > %f",
			order.Slippage, m.limits.DEX.MaxSlippage)
	}

	if order.PriceImpact > m.limits.DEX.MaxImpact {
		return fmt.Errorf("price impact too high: %f > %f",
			order.PriceImpact, m.limits.DEX.MaxImpact)
	}

	if order.Spread > m.limits.DEX.MaxSpread {
		return fmt.Errorf("spread too high: %f > %f",
			order.Spread, m.limits.DEX.MaxSpread)
	}

	if order.PoolSize < m.limits.DEX.MinPoolSize {
		return fmt.Errorf("pool size too small: %f < %f",
			order.PoolSize, m.limits.DEX.MinPoolSize)
	}

	return nil
}

// checkPumpFunOrderRisk validates meme trading risk parameters
func (m *Manager) checkPumpFunOrderRisk(ctx context.Context, order *types.Order) error {
	if order.MarketCap < m.limits.PumpFun.MinMarketCap {
		return fmt.Errorf("market cap too low: %f < %f",
			order.MarketCap, m.limits.PumpFun.MinMarketCap)
	}

	if order.Volume < m.limits.PumpFun.MinVolume {
		return fmt.Errorf("volume too low: %f < %f",
			order.Volume, m.limits.PumpFun.MinVolume)
	}

	if order.Holders < m.limits.PumpFun.MinHolders {
		return fmt.Errorf("holders too few: %d < %d",
			order.Holders, m.limits.PumpFun.MinHolders)
	}

	if order.Volatility > m.limits.PumpFun.MaxVolatility {
		return fmt.Errorf("volatility too high: %f > %f",
			order.Volatility, m.limits.PumpFun.MaxVolatility)
	}

	if order.SocialScore < m.limits.PumpFun.MinSocialScore {
		return fmt.Errorf("social score too low: %f < %f",
			order.SocialScore, m.limits.PumpFun.MinSocialScore)
	}

	return nil
}

// checkDEXPositionRisk validates DEX-specific position risk parameters
func (m *Manager) checkDEXPositionRisk(ctx context.Context, position *types.Position) error {
	// Check liquidity relative to position size
	if position.PoolSize > 0 && math.Abs(position.Quantity*position.AvgPrice)/position.PoolSize > 0.1 {
		return fmt.Errorf("position size too large relative to pool: %f > 10%%",
			math.Abs(position.Quantity*position.AvgPrice)/position.PoolSize*100)
	}

	// Check spread impact
	if position.Spread > m.limits.DEX.MaxSpread {
		return fmt.Errorf("spread too high for position: %f > %f",
			position.Spread, m.limits.DEX.MaxSpread)
	}

	return nil
}

// checkPumpFunPositionRisk validates meme trading position risk parameters
func (m *Manager) checkPumpFunPositionRisk(ctx context.Context, position *types.Position) error {
	// Check market cap ratio
	if position.MarketCap > 0 {
		positionRatio := math.Abs(position.Quantity*position.AvgPrice) / position.MarketCap
		if positionRatio > 0.01 {
			return fmt.Errorf("position too large relative to market cap: %f > 1%%",
				positionRatio*100)
		}
	}

	// Check volume ratio
	if position.Volume > 0 {
		volumeRatio := math.Abs(position.Quantity*position.AvgPrice) / position.Volume
		if volumeRatio > 0.2 {
			return fmt.Errorf("position too large relative to volume: %f > 20%%",
				volumeRatio*100)
		}
	}

	// Check volatility
	if position.Volatility > m.limits.PumpFun.MaxVolatility {
		return fmt.Errorf("volatility too high for position: %f > %f",
			position.Volatility, m.limits.PumpFun.MaxVolatility)
	}

	return nil
}

// getAIRiskScore gets risk assessment from AI service
func (m *Manager) getAIRiskScore(ctx context.Context, order *types.Order) (float64, error) {
	url := fmt.Sprintf("%s/api/v1/risk/analyze", m.aiClient.baseURL)
	
	payload := map[string]interface{}{
		"order": order,
		"mode":  m.mode,
	}
	
	jsonData, err := json.Marshal(payload)
	if err != nil {
		return 0, fmt.Errorf("failed to marshal payload: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return 0, fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := m.aiClient.client.Do(req)
	if err != nil {
		return 0, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return 0, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	var result struct {
		RiskScore float64 `json:"risk_score"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return 0, fmt.Errorf("failed to decode response: %w", err)
	}

	return result.RiskScore, nil
}
