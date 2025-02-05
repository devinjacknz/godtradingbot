package pump

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"go.uber.org/zap"

	"github.com/kwanRoshi/B/go-migration/internal/types"
)

// WSConfig holds WebSocket client configuration
type WSConfig struct {
	DialTimeout  time.Duration
	WriteTimeout time.Duration
	ReadTimeout  time.Duration
	PongWait     time.Duration
	MaxRetries   int
	APIKey       string
}

// WSClient handles WebSocket connections for real-time price updates
type WSClient struct {
	logger       *zap.Logger
	conn         *websocket.Conn
	updates      chan *types.PriceUpdate
	done         chan struct{}
	mu           sync.RWMutex
	symbols      map[string]bool
	wsURL        string
	dialTimeout  time.Duration
	writeTimeout time.Duration
	readTimeout  time.Duration
	pongWait     time.Duration
	pingPeriod   time.Duration
	maxRetries   int
	apiKey       string
}

// NewWSClient creates a new WebSocket client
func NewWSClient(wsURL string, logger *zap.Logger, config WSConfig) *WSClient {
	return &WSClient{
		logger:       logger,
		updates:      make(chan *types.PriceUpdate, 1000),
		done:         make(chan struct{}),
		symbols:      make(map[string]bool),
		wsURL:        wsURL,
		dialTimeout:  config.DialTimeout,
		writeTimeout: config.WriteTimeout,
		readTimeout:  config.ReadTimeout,
		pongWait:     config.PongWait,
		pingPeriod:   (config.PongWait * 9) / 10,
		maxRetries:   config.MaxRetries,
		apiKey:       config.APIKey,
	}
}

// Connect establishes WebSocket connection
func (c *WSClient) Connect(ctx context.Context) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.conn != nil {
		return nil
	}

	headers := http.Header{}
	headers.Add("X-API-Key", c.apiKey)
	headers.Add("Authorization", fmt.Sprintf("Bearer %s", c.apiKey))

	dialer := websocket.Dialer{
		HandshakeTimeout: c.dialTimeout,
		WriteBufferSize:  1024 * 16,
		ReadBufferSize:   1024 * 16,
		TLSClientConfig: &tls.Config{
			MinVersion:         tls.VersionTLS12,
			InsecureSkipVerify: true,
		},
		EnableCompression: true,
		Proxy:            http.ProxyFromEnvironment,
	}

	backoff := time.Second
	maxBackoff := 60 * time.Second
	retries := 0

	for {
		c.logger.Info("Attempting WebSocket connection",
			zap.String("url", c.wsURL),
			zap.Int("retry", retries),
			zap.Int("max_retries", c.maxRetries),
			zap.Duration("backoff", backoff))

		conn, resp, err := dialer.DialContext(ctx, c.wsURL, headers)
		if err != nil {
			metrics.PumpAPIErrors.WithLabelValues("websocket_connect").Inc()
			if resp != nil {
				c.logger.Error("WebSocket connection failed",
					zap.Int("status", resp.StatusCode),
					zap.String("status_text", resp.Status))
			}
			
			if retries >= c.maxRetries {
				return fmt.Errorf("max retries reached: %w", err)
			}
			
			retries++
			time.Sleep(backoff)
			backoff = time.Duration(float64(backoff) * 1.5)
			if backoff > maxBackoff {
				backoff = maxBackoff
			}
			continue
		}

		c.logger.Info("WebSocket connection established",
			zap.String("url", c.wsURL))
		metrics.PumpWebsocketConnections.Inc()

		// Send new token subscription
		newTokenMsg := struct {
			Method string `json:"method"`
			APIKey string `json:"api_key"`
		}{
			Method: "subscribeNewToken",
			APIKey: c.apiKey,
		}
		
		if err := conn.WriteJSON(newTokenMsg); err != nil {
			c.logger.Error("Failed to send new token subscription",
				zap.Error(err))
			conn.Close()
			metrics.PumpWebsocketConnections.Dec()
			continue
		}

		// Send trade subscription for each symbol
		for symbol := range c.symbols {
			tradeMsg := struct {
				Method string   `json:"method"`
				Keys   []string `json:"keys"`
				APIKey string   `json:"api_key"`
			}{
				Method: "subscribeTokenTrade",
				Keys:   []string{symbol},
				APIKey: c.apiKey,
			}
			
			if err := conn.WriteJSON(tradeMsg); err != nil {
				c.logger.Error("Failed to send trade subscription",
					zap.Error(err),
					zap.String("symbol", symbol))
				conn.Close()
				metrics.PumpWebsocketConnections.Dec()
				continue
			}
		}

		conn.SetReadDeadline(time.Now().Add(c.readTimeout))
		conn.SetWriteDeadline(time.Now().Add(c.writeTimeout))
		conn.SetPongHandler(func(string) error {
			return conn.SetReadDeadline(time.Now().Add(c.pongWait))
		})

		c.mu.Lock()
		c.conn = conn
		c.mu.Unlock()

		// Start message handler and keepalive routines
		go c.handleMessages()
		go c.keepAlive(ctx)

		c.logger.Info("Started message handler and keepalive routines")
		return nil
	}
	for {
		c.logger.Info("Attempting WebSocket connection",
			zap.String("url", c.wsURL),
			zap.Int("retry", retries),
			zap.Int("max_retries", c.maxRetries),
			zap.Duration("backoff", backoff),
			zap.String("api_key_length", fmt.Sprintf("%d", len(c.apiKey))))

		conn, resp, err := dialer.DialContext(ctx, c.wsURL, headers)
		if err != nil {
			if resp != nil {
				c.logger.Error("WebSocket connection failed",
					zap.Int("status", resp.StatusCode),
					zap.String("status_text", resp.Status))
			}
			
			if retries >= c.maxRetries {
				return fmt.Errorf("max retries reached: %w", err)
			}
			
			retries++
			time.Sleep(backoff)
			backoff = time.Duration(float64(backoff) * 1.5)
			if backoff > maxBackoff {
				backoff = maxBackoff
			}
			continue
		}

		c.logger.Info("WebSocket connection established",
			zap.String("url", c.wsURL))

		// Send new token subscription
		newTokenMsg := struct {
			Method string `json:"method"`
			APIKey string `json:"api_key"`
		}{
			Method: "subscribeNewToken",
			APIKey: c.apiKey,
		}
		
		if err := conn.WriteJSON(newTokenMsg); err != nil {
			c.logger.Error("Failed to send new token subscription",
				zap.Error(err))
			conn.Close()
			continue
		}

		// Send trade subscription for each symbol
		for symbol := range c.symbols {
			tradeMsg := struct {
				Method string   `json:"method"`
				Keys   []string `json:"keys"`
				APIKey string   `json:"api_key"`
			}{
				Method: "subscribeTokenTrade",
				Keys:   []string{symbol},
				APIKey: c.apiKey,
			}
			
			if err := conn.WriteJSON(tradeMsg); err != nil {
				c.logger.Error("Failed to send trade subscription",
					zap.Error(err),
					zap.String("symbol", symbol))
				conn.Close()
				continue
			}
		}

		conn.SetReadDeadline(time.Now().Add(c.readTimeout))
		conn.SetWriteDeadline(time.Now().Add(c.writeTimeout))
		conn.SetPongHandler(func(string) error {
			return conn.SetReadDeadline(time.Now().Add(c.pongWait))
		})

		c.mu.Lock()
		c.conn = conn
		c.mu.Unlock()

		// Start message handler and keepalive routines
		go c.handleMessages()
		go c.keepAlive(ctx)

		c.logger.Info("Started message handler and keepalive routines")
		return nil
	}
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
			Method string   `json:"method"`
			Keys   []string `json:"keys"`
			APIKey string   `json:"api_key"`
		}{
			Method: "subscribeTokenTrade",
			Keys:   []string{symbol},
			APIKey: c.apiKey,
		}

		if err := c.conn.WriteJSON(msg); err != nil {
			c.logger.Error("Failed to subscribe",
				zap.String("symbol", symbol),
				zap.Error(err))
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

func (c *WSClient) keepAlive(ctx context.Context) {
	ticker := time.NewTicker(c.pingPeriod)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			c.mu.Lock()
			if c.conn == nil {
				c.mu.Unlock()
				return
			}

			if err := c.conn.WriteControl(websocket.PingMessage, []byte{}, time.Now().Add(c.writeTimeout)); err != nil {
				c.logger.Error("failed to write ping message", zap.Error(err))
				c.conn.Close()
				c.conn = nil
				c.mu.Unlock()
				return
			}
			c.mu.Unlock()
		}
	}
}

func (c *WSClient) handleMessages() {
	defer close(c.updates)

	reconnectTicker := time.NewTicker(5 * time.Second)
	defer reconnectTicker.Stop()

	for {
		select {
		case <-c.done:
			return
		case <-reconnectTicker.C:
			c.mu.Lock()
			if c.conn == nil {
				ctx := context.Background()
				if err := c.Connect(ctx); err != nil {
					c.logger.Error("Failed to reconnect", zap.Error(err))
					c.mu.Unlock()
					continue
				}
				
				// Resubscribe to existing symbols
				symbols := make([]string, 0, len(c.symbols))
				for symbol := range c.symbols {
					symbols = append(symbols, symbol)
				}
				c.mu.Unlock()
				
				if err := c.Subscribe(symbols); err != nil {
					c.logger.Error("Failed to resubscribe", zap.Error(err))
				}
				continue
			}
			c.mu.Unlock()
		default:
			c.conn.SetReadDeadline(time.Now().Add(c.readTimeout))
			_, msg, err := c.conn.ReadMessage()
			if err != nil {
				if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
					c.logger.Error("WebSocket read error", zap.Error(err))
					metrics.PumpAPIErrors.WithLabelValues("websocket_read").Inc()
				}
				c.mu.Lock()
				if c.conn != nil {
					c.conn.Close()
					c.conn = nil
					metrics.PumpWebsocketConnections.Dec()
				}
				c.mu.Unlock()
				continue
			}

			var data struct {
				Method string `json:"method"`
				Data   struct {
					Address    string  `json:"address"`
					Price      float64 `json:"price"`
					Volume     float64 `json:"volume"`
					Time       int64   `json:"time"`
					TxHash     string  `json:"txHash"`
					BlockTime  int64   `json:"blockTime"`
					Error      string  `json:"error,omitempty"`
					TokenName  string  `json:"tokenName,omitempty"`
					MarketCap  float64 `json:"marketCap,omitempty"`
					TotalSupply float64 `json:"totalSupply,omitempty"`
				} `json:"data"`
				Error string `json:"error,omitempty"`
				Status string `json:"status,omitempty"`
			}

			// Update metrics and send updates
			select {
			case c.updates <- update:
				c.logger.Info("Trade update sent",
					zap.String("token", data.Data.TokenName),
					zap.Float64("price", data.Data.Price),
					zap.Float64("market_cap", data.Data.MarketCap))
				
				metrics.PumpTokenPrice.WithLabelValues(data.Data.Address).Set(data.Data.Price)
				metrics.PumpTokenVolume.WithLabelValues(data.Data.Address).Set(data.Data.Volume)
			default:
				c.logger.Warn("Update channel full",
					zap.String("token", data.Data.TokenName),
					zap.Float64("price", data.Data.Price))
			c.logger.Info("Received WebSocket message",
				zap.String("raw_message", string(msg)),
				zap.String("connection_status", "active"))

			if err := json.Unmarshal(msg, &data); err != nil {
				c.logger.Error("Failed to parse WebSocket message", 
					zap.Error(err),
					zap.String("raw_message", string(msg)))
				continue
			}

			if data.Error != "" || (data.Status != "" && data.Status != "success") {
				c.logger.Error("Received error in WebSocket message",
					zap.String("error", data.Error),
					zap.String("status", data.Status))
				if data.Error == "unauthorized" || data.Error == "invalid_token" {
					c.mu.Lock()
					if c.conn != nil {
						c.conn.Close()
						c.conn = nil
					}
					c.mu.Unlock()
				}
				continue
			}

			switch data.Method {
			case "trade":
				c.logger.Debug("Received trade event",
					zap.String("address", data.Data.Address),
					zap.String("token_name", data.Data.TokenName),
					zap.Float64("price", data.Data.Price),
					zap.Float64("volume", data.Data.Volume),
					zap.Float64("market_cap", data.Data.MarketCap),
					zap.Float64("total_supply", data.Data.TotalSupply),
					zap.String("txHash", data.Data.TxHash))

				update := &types.PriceUpdate{
					Symbol:      data.Data.Address,
					TokenName:   data.Data.TokenName,
					Price:      data.Data.Price,
					Volume:     data.Data.Volume,
					MarketCap:  data.Data.MarketCap,
					TotalSupply: data.Data.TotalSupply,
					Timestamp:  time.Unix(data.Data.BlockTime, 0),
				}

				select {
				case c.updates <- update:
					c.logger.Info("Trade update sent",
						zap.String("token", data.Data.TokenName),
						zap.Float64("price", data.Data.Price),
						zap.Float64("market_cap", data.Data.MarketCap))
				default:
					c.logger.Warn("Update channel full, dropping trade update",
						zap.String("token", data.Data.TokenName),
						zap.Float64("price", data.Data.Price),
						zap.Float64("market_cap", data.Data.MarketCap))
				}
			case "subscribed":
				c.logger.Info("Successfully subscribed to updates",
					zap.String("method", data.Method))
			case "error":
				c.logger.Error("Subscription error",
					zap.String("error", data.Data.Error))
			}
		}
	}
}
