package pump

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"

	"go.uber.org/zap"

	"github.com/kwanRoshi/B/go-migration/internal/types"
)

type TokenMonitor struct {
	logger     *zap.Logger
	client     *http.Client
	baseURL    string
	updateChan chan *types.TokenUpdate
	mu         sync.RWMutex
	active     bool
}

type TokenUpdate struct {
	Symbol     string    `json:"symbol"`
	MintTime   time.Time `json:"mint_time"`
	InitPrice  float64   `json:"init_price"`
	TotalMint  int64     `json:"total_mint"`
}

func NewTokenMonitor(baseURL string, logger *zap.Logger) *TokenMonitor {
	return &TokenMonitor{
		logger:     logger,
		client:     &http.Client{Timeout: 10 * time.Second},
		baseURL:    baseURL,
		updateChan: make(chan *types.TokenUpdate, 100),
		active:     false,
	}
}

func (tm *TokenMonitor) Start(ctx context.Context) error {
	tm.mu.Lock()
	if tm.active {
		tm.mu.Unlock()
		return nil
	}
	tm.active = true
	tm.mu.Unlock()

	go tm.monitorNewTokens(ctx)
	return nil
}

func (tm *TokenMonitor) Stop() {
	tm.mu.Lock()
	tm.active = false
	tm.mu.Unlock()
}

func (tm *TokenMonitor) GetUpdates() <-chan *types.TokenUpdate {
	return tm.updateChan
}

func (tm *TokenMonitor) monitorNewTokens(ctx context.Context) {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			updates, err := tm.fetchNewTokens(ctx)
			if err != nil {
				tm.logger.Error("failed to fetch new tokens", zap.Error(err))
				continue
			}

			for _, update := range updates {
				select {
				case tm.updateChan <- update:
				default:
					tm.logger.Warn("update channel full, dropping token update")
				}
			}
		}
	}
}

func (tm *TokenMonitor) fetchNewTokens(ctx context.Context) ([]*types.TokenUpdate, error) {
	url := fmt.Sprintf("%s/api/v1/new-tokens", tm.baseURL)
	
	backoff := time.Second
	maxBackoff := 30 * time.Second
	maxRetries := 3
	
	var updates []*types.TokenUpdate
	var lastErr error
	
	for retry := 0; retry < maxRetries; retry++ {
		if retry > 0 {
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(backoff):
				backoff = time.Duration(float64(backoff) * 1.5)
				if backoff > maxBackoff {
					backoff = maxBackoff
				}
			}
		}
		
		req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
		if err != nil {
			lastErr = fmt.Errorf("failed to create request: %w", err)
			continue
		}
		
		resp, err := tm.client.Do(req)
		if err != nil {
			metrics.PumpAPIErrors.WithLabelValues("fetch_new_tokens").Inc()
			lastErr = fmt.Errorf("failed to fetch new tokens: %w", err)
			tm.logger.Error("failed to fetch new tokens", 
				zap.Error(err),
				zap.Int("retry", retry),
				zap.Duration("backoff", backoff))
			continue
		}
		defer resp.Body.Close()
		
		if resp.StatusCode != http.StatusOK {
			metrics.PumpAPIErrors.WithLabelValues("fetch_new_tokens").Inc()
			lastErr = fmt.Errorf("unexpected status code: %d", resp.StatusCode)
			tm.logger.Error("unexpected status code",
				zap.Int("status_code", resp.StatusCode),
				zap.Int("retry", retry),
				zap.Duration("backoff", backoff))
			if resp.StatusCode == http.StatusTooManyRequests {
				continue
			}
			return nil, lastErr
		}
		
		if err := json.NewDecoder(resp.Body).Decode(&updates); err != nil {
			metrics.PumpAPIErrors.WithLabelValues("fetch_new_tokens").Inc()
			lastErr = fmt.Errorf("failed to decode response: %w", err)
			tm.logger.Error("failed to decode response",
				zap.Error(err),
				zap.Int("retry", retry))
			continue
		}
		
		// Update metrics for successful fetch
		metrics.PumpNewTokens.Add(float64(len(updates)))
		return updates, nil
	}
	
	return nil, fmt.Errorf("max retries exceeded: %w", lastErr)
}
