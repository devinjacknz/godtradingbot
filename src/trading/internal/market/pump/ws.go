package pump

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"go.uber.org/zap"

	"github.com/devinjacknz/tradingbot/internal/types"
)

// WSClient handles WebSocket connections for real-time price updates
type WSClient struct {
	logger  *zap.Logger
	conn    *websocket.Conn
	updates chan *types.PriceUpdate
	done    chan struct{}
	mu      sync.RWMutex
	symbols map[string]bool
	wsURL   string
}

// NewWSClient creates a new WebSocket client
func NewWSClient(wsURL string, logger *zap.Logger) *WSClient {
	return &WSClient{
		logger:  logger,
		updates: make(chan *types.PriceUpdate, 1000),
		done:    make(chan struct{}),
		symbols: make(map[string]bool),
		wsURL:   wsURL,
	}
}

// Connect establishes WebSocket connection
func (c *WSClient) Connect(ctx context.Context) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.conn != nil {
		return nil
	}

	conn, _, err := websocket.DefaultDialer.DialContext(ctx, c.wsURL, nil)
	if err != nil {
		return fmt.Errorf("failed to connect to WebSocket: %w", err)
	}
	c.conn = conn

	go c.handleMessages()

	return nil
}

// Subscribe subscribes to price updates for symbols
func (c *WSClient) Subscribe(symbols []string) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.conn == nil {
		return fmt.Errorf("not connected")
	}

	for _, symbol := range symbols {
		if c.symbols[symbol] {
			continue
		}

		msg := struct {
			Type   string `json:"type"`
			Symbol string `json:"symbol"`
		}{
			Type:   "subscribe",
			Symbol: symbol,
		}

		if err := c.conn.WriteJSON(msg); err != nil {
			return fmt.Errorf("failed to subscribe to %s: %w", symbol, err)
		}

		c.symbols[symbol] = true
	}

	return nil
}

// GetUpdates returns the price updates channel
func (c *WSClient) GetUpdates() <-chan *types.PriceUpdate {
	return c.updates
}

// Close closes the WebSocket connection
func (c *WSClient) Close() error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.conn != nil {
		close(c.done)
		if err := c.conn.Close(); err != nil {
			return fmt.Errorf("failed to close WebSocket: %w", err)
		}
		c.conn = nil
	}

	return nil
}

func (c *WSClient) handleMessages() {
	defer close(c.updates)

	for {
		select {
		case <-c.done:
			return
		default:
			_, msg, err := c.conn.ReadMessage()
			if err != nil {
				if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
					c.logger.Error("WebSocket read error", zap.Error(err))
				}
				return
			}

			var data struct {
				Type      string  `json:"type"`
				Symbol    string  `json:"symbol"`
				Price     float64 `json:"price"`
				Volume    float64 `json:"volume"`
				Timestamp int64   `json:"timestamp"`
			}

			if err := json.Unmarshal(msg, &data); err != nil {
				c.logger.Error("Failed to parse WebSocket message", zap.Error(err))
				continue
			}

			update := &types.PriceUpdate{
				Symbol:    data.Symbol,
				Price:     data.Price,
				Volume:    data.Volume,
				Timestamp: time.Unix(data.Timestamp/1000, 0),
			}

			select {
			case c.updates <- update:
			default:
				c.logger.Warn("Update channel full")
			}
		}
	}
}
