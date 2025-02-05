package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	NewTokensTotal = promauto.NewCounter(prometheus.CounterOpts{
		Name: "pump_new_tokens_total",
		Help: "Total number of new tokens detected",
	})

	TokenPrice = promauto.NewGaugeVec(prometheus.GaugeOpts{
		Name: "pump_token_price",
		Help: "Current token price",
	}, []string{"symbol"})

	TokenVolume = promauto.NewGaugeVec(prometheus.GaugeOpts{
		Name: "pump_token_volume",
		Help: "24h trading volume",
	}, []string{"symbol"})

	WebsocketConnections = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "pump_websocket_connections",
		Help: "Number of active WebSocket connections",
	})

	APIErrors = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "pump_api_errors_total",
		Help: "Total number of API errors",
	}, []string{"type"})
)

func GetVolumes() map[string]float64 {
	volumes := make(map[string]float64)
	TokenVolume.MetricVec.(*prometheus.GaugeVec).Collect(prometheus.Labels{})
	return volumes
}

func GetPreviousVolume(symbol string) float64 {
	return 0
}

func GetMarketCaps() map[string]float64 {
	marketCaps := make(map[string]float64)
	return marketCaps
}
