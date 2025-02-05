package monitoring

import (
	"context"
	"strings"
	"sync"
	"time"

	"go.uber.org/zap"

	"github.com/kwanRoshi/B/go-migration/internal/market/pump"
	"github.com/kwanRoshi/B/go-migration/internal/metrics"
	"github.com/kwanRoshi/B/go-migration/internal/types"
)

type Service struct {
	logger   *zap.Logger
	provider *pump.Provider
	metrics  *metrics.PumpMetrics
	mu       sync.RWMutex
	tokens   map[string]*types.TokenInfo
}

func NewService(provider *pump.Provider, metrics *metrics.PumpMetrics, logger *zap.Logger) *Service {
	return &Service{
		logger:   logger,
		provider: provider,
		metrics:  metrics,
		tokens:   make(map[string]*types.TokenInfo),
	}
}

func (s *Service) Start(ctx context.Context) error {
	tokenUpdates, err := s.provider.SubscribeNewTokens(ctx)
	if err != nil {
		return err
	}

	go s.monitorNewTokens(ctx, tokenUpdates)
	go s.monitorMarketData(ctx)

	return nil
}

func (s *Service) monitorNewTokens(ctx context.Context, updates <-chan *types.TokenInfo) {
	const maxMarketCap = 30000.0 // $30,000 market cap threshold

	for {
		select {
		case <-ctx.Done():
			return
		case token := <-updates:
			// Filter for SOL meme coins with market cap below threshold
			if !strings.HasSuffix(strings.ToUpper(token.Symbol), "/SOL") || token.MarketCap > maxMarketCap {
				s.logger.Debug("Token filtered out",
					zap.String("symbol", token.Symbol),
					zap.Float64("market_cap", token.MarketCap),
					zap.String("reason", "not SOL meme coin or market cap too high"))
				continue
			}

			s.mu.Lock()
			s.tokens[token.Symbol] = token
			s.mu.Unlock()

			s.logger.Info("New SOL meme token detected",
				zap.String("symbol", token.Symbol),
				zap.String("name", token.Name),
				zap.Float64("market_cap", token.MarketCap),
				zap.Int64("supply", token.Supply),
				zap.Float64("volume", token.Volume))

			s.metrics.RecordNewToken(token)

			// Trigger early entry alert for qualifying tokens
			if token.MarketCap < maxMarketCap {
				s.logger.Info("Early entry opportunity detected",
					zap.String("symbol", token.Symbol),
					zap.Float64("market_cap", token.MarketCap),
					zap.Float64("volume", token.Volume))
			}
		}
	}
}

func (s *Service) monitorMarketData(ctx context.Context) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			s.mu.RLock()
			tokens := make([]string, 0, len(s.tokens))
			for symbol := range s.tokens {
				tokens = append(tokens, symbol)
			}
			s.mu.RUnlock()

			for _, symbol := range tokens {
				curve, err := s.provider.GetBondingCurve(ctx, symbol)
				if err != nil {
					s.logger.Error("Failed to get bonding curve",
						zap.String("symbol", symbol),
						zap.Error(err))
					continue
				}

				s.metrics.RecordBondingCurve(curve)
				s.logger.Debug("Updated bonding curve",
					zap.String("symbol", symbol),
					zap.Float64("price", curve.CurrentPrice),
					zap.Float64("base_price", curve.BasePrice),
					zap.Int64("supply", curve.Supply))
			}
		}
	}
}

func (s *Service) GetTokens() map[string]*types.TokenInfo {
	s.mu.RLock()
	defer s.mu.RUnlock()

	tokens := make(map[string]*types.TokenInfo, len(s.tokens))
	for k, v := range s.tokens {
		tokens[k] = v
	}
	return tokens
}

func calculateAverageVolume(history []float64) float64 {
	if len(history) == 0 {
		return 0
	}
	
	var sum float64
	for _, v := range history {
		sum += v
	}
	return sum / float64(len(history))
}
