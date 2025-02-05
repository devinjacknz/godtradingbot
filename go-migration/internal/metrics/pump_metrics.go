package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/kwanRoshi/B/go-migration/internal/types"
	"go.uber.org/zap"
)

var (
	PumpNewTokens = promauto.NewCounter(prometheus.CounterOpts{
		Name: "pump_new_tokens_total",
		Help: "Total number of new tokens detected",
	})

	PumpTokenPrice = promauto.NewGaugeVec(prometheus.GaugeOpts{
		Name: "pump_token_price",
		Help: "Current token price",
	}, []string{"symbol"})

	PumpTokenVolume = promauto.NewGaugeVec(prometheus.GaugeOpts{
		Name: "pump_token_volume_24h",
		Help: "24h trading volume",
	}, []string{"symbol"})

	PumpBondingCurvePrice = promauto.NewGaugeVec(prometheus.GaugeOpts{
		Name: "pump_bonding_curve_price",
		Help: "Current bonding curve price",
	}, []string{"symbol"})

	PumpWebsocketConnections = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "pump_websocket_connections",
		Help: "Number of active WebSocket connections",
	})

	PumpAPIErrors = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "pump_api_errors_total",
		Help: "Total number of API errors",
	}, []string{"operation"})
)

type PumpMetrics struct {
	logger *zap.Logger
}

func NewPumpMetrics() *PumpMetrics {
	return &PumpMetrics{
		logger: zap.L(),
	}
}

func (m *PumpMetrics) RecordNewToken(token *types.TokenInfo) {
	m.logger.Info("New token metrics",
		zap.String("symbol", token.Symbol),
		zap.String("name", token.Name),
		zap.Float64("market_cap", token.MarketCap),
		zap.Int64("supply", token.Supply))
	PumpNewTokens.Inc()
	PumpTokenPrice.WithLabelValues(token.Symbol).Set(0)
}

func (m *PumpMetrics) RecordBondingCurve(curve *types.BondingCurve) {
	m.logger.Info("Bonding curve metrics",
		zap.String("symbol", curve.Symbol),
		zap.Float64("current_price", curve.CurrentPrice),
		zap.Float64("base_price", curve.BasePrice),
		zap.Int64("supply", curve.Supply))
	PumpBondingCurvePrice.WithLabelValues(curve.Symbol).Set(curve.CurrentPrice)
}
