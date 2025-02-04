package solana

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

	// Already connected
	if c.conn != nil {
		return nil
	}

	// Connect to WebSocket server
	conn, _, err := websocket.DefaultDialer.DialContext(ctx, c.wsURL, nil)
	if err != nil {
		return fmt.Errorf("failed to connect to WebSocket: %w", err)
	}
	c.conn = conn

	// Start message handler
	go c.handleMessages()

	return nil
}

// Subscribe subscribes to price updates for a symbol
func (c *WSClient) Subscribe(dex string, symbols []string) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.conn == nil {
		return fmt.Errorf("not connected")
	}

	// Subscribe to each symbol
	for _, symbol := range symbols {
		// Already subscribed
		if c.symbols[symbol] {
			continue
		}

		// Send subscription message
		msg := struct {
			Type    string `json:"type"`
			Symbol  string `json:"symbol"`
			Channel string `json:"channel"`
			Source  string `json:"source"`
		}{
			Type:    "subscribe",
			Symbol:  symbol,
			Channel: "trades",
			Source:  dex,
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

// Internal methods

func (c *WSClient) handleMessages() {
	defer close(c.updates)

	for {
		select {
		case <-c.done:
			return
		default:
			// Read message
			_, msg, err := c.conn.ReadMessage()
			if err != nil {
				if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
					c.logger.Error("WebSocket read error",
						zap.Error(err))
				}
				return
			}

			// Parse message
			var data struct {
				Type      string  `json:"type"`
				Symbol    string  `json:"symbol"`
				Price     float64 `json:"price"`
				Volume    float64 `json:"volume"`
				Timestamp int64   `json:"timestamp"`
			}

			if err := json.Unmarshal(msg, &data); err != nil {
				c.logger.Error("Failed to parse WebSocket message",
					zap.Error(err))
				continue
			}

			// Create price update
			update := &types.PriceUpdate{
				Symbol:    data.Symbol,
				Price:     data.Price,
				Volume:    data.Volume,
				Timestamp: time.Unix(data.Timestamp/1000, 0),
			}

			// Send update
			select {
			case c.updates <- update:
			default:
				c.logger.Warn("Update channel full")
			}
		}
	}
}

// Helper functions

func (c *WSClient) reconnect(ctx context.Context) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	// Close existing connection
	if c.conn != nil {
		c.conn.Close()
		c.conn = nil
	}

	// Connect to WebSocket server
	conn, _, err := websocket.DefaultDialer.DialContext(ctx, c.wsURL, nil)
	if err != nil {
		return fmt.Errorf("failed to reconnect to WebSocket: %w", err)
	}
	c.conn = conn

	// Resubscribe to symbols
	for symbol := range c.symbols {
		msg := struct {
			Type    string `json:"type"`
			Symbol  string `json:"symbol"`
			Channel string `json:"channel"`
		}{
			Type:    "subscribe",
			Symbol:  symbol,
			Channel: "trades",
		}

		if err := c.conn.WriteJSON(msg); err != nil {
			return fmt.Errorf("failed to resubscribe to %s: %w", symbol, err)
		}
	}

	return nil
}
