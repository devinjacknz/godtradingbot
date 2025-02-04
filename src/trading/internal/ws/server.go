package ws

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"go.uber.org/zap"

	"github.com/devinjacknz/tradingbot/internal/trading"
	"github.com/devinjacknz/tradingbot/internal/market"
)

type Config struct {
	Port           int           `yaml:"port"`
	PingInterval   time.Duration `yaml:"ping_interval"`
	PongWait       time.Duration `yaml:"pong_wait"`
	WriteWait      time.Duration `yaml:"write_wait"`
	MaxMessageSize int64         `yaml:"max_message_size"`
}

type Server struct {
	config     Config
	upgrader   websocket.Upgrader
	logger     *zap.Logger
	engine     trading.TradingEngine
	market     *market.Handler
	clients    map[*Client]bool
	register   chan *Client
	unregister chan *Client
	broadcast  chan []byte
	mu         sync.RWMutex
}

type Client struct {
	server *Server
	conn   *websocket.Conn
	send   chan []byte
	userID string
}

func NewServer(config Config, logger *zap.Logger, engine trading.TradingEngine, market *market.Handler) *Server {
	return &Server{
		config: config,
		upgrader: websocket.Upgrader{
			ReadBufferSize:  1024,
			WriteBufferSize: 1024,
			CheckOrigin: func(r *http.Request) bool {
				return true // TODO: Implement proper origin checking
			},
		},
		logger:     logger,
		engine:     engine,
		market:     market,
		clients:    make(map[*Client]bool),
		register:   make(chan *Client),
		unregister: make(chan *Client),
		broadcast:  make(chan []byte),
	}
}

func (s *Server) Start() {
	go s.run()

	http.HandleFunc("/ws", s.handleWebSocket)
	addr := fmt.Sprintf(":%d", s.config.Port)
	s.logger.Info("Starting WebSocket server", zap.String("addr", addr))
	if err := http.ListenAndServe(addr, nil); err != nil {
		s.logger.Fatal("WebSocket server error", zap.Error(err))
	}
}

func (s *Server) run() {
	for {
		select {
		case client := <-s.register:
			s.mu.Lock()
			s.clients[client] = true
			s.mu.Unlock()
			s.logger.Info("Client connected", zap.String("user_id", client.userID))

		case client := <-s.unregister:
			s.mu.Lock()
			if _, ok := s.clients[client]; ok {
				delete(s.clients, client)
				close(client.send)
			}
			s.mu.Unlock()
			s.logger.Info("Client disconnected", zap.String("user_id", client.userID))

		case message := <-s.broadcast:
			s.mu.RLock()
			for client := range s.clients {
				select {
				case client.send <- message:
				default:
					close(client.send)
					delete(s.clients, client)
				}
			}
			s.mu.RUnlock()
		}
	}
}

func (s *Server) handleWebSocket(w http.ResponseWriter, r *http.Request) {
	userID := r.URL.Query().Get("user_id")
	if userID == "" {
		http.Error(w, "Missing user_id parameter", http.StatusBadRequest)
		return
	}

	conn, err := s.upgrader.Upgrade(w, r, nil)
	if err != nil {
		s.logger.Error("WebSocket upgrade failed", zap.Error(err))
		return
	}

	client := &Client{
		server: s,
		conn:   conn,
		send:   make(chan []byte, 256),
		userID: userID,
	}

	client.server.register <- client

	go client.writePump()
	go client.readPump()
}

func (c *Client) readPump() {
	defer func() {
		c.server.unregister <- c
		c.conn.Close()
	}()

	c.conn.SetReadLimit(c.server.config.MaxMessageSize)
	c.conn.SetReadDeadline(time.Now().Add(c.server.config.PongWait))
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(c.server.config.PongWait))
		return nil
	})

	for {
		_, message, err := c.conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				c.server.logger.Error("WebSocket read error", zap.Error(err))
			}
			break
		}

		// Handle incoming messages
		if err := c.handleMessage(message); err != nil {
			c.server.logger.Error("Message handling error", zap.Error(err))
		}
	}
}

func (c *Client) writePump() {
	ticker := time.NewTicker(c.server.config.PingInterval)
	defer func() {
		ticker.Stop()
		c.conn.Close()
	}()

	for {
		select {
		case message, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(c.server.config.WriteWait))
			if !ok {
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			w, err := c.conn.NextWriter(websocket.TextMessage)
			if err != nil {
				return
			}
			w.Write(message)

			n := len(c.send)
			for i := 0; i < n; i++ {
				w.Write([]byte{'\n'})
				w.Write(<-c.send)
			}

			if err := w.Close(); err != nil {
				return
			}

		case <-ticker.C:
			c.conn.SetWriteDeadline(time.Now().Add(c.server.config.WriteWait))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

func (c *Client) handleMessage(message []byte) error {
	var msg struct {
		Type    string          `json:"type"`
		Payload json.RawMessage `json:"payload"`
	}

	if err := json.Unmarshal(message, &msg); err != nil {
		return fmt.Errorf("failed to unmarshal message: %w", err)
	}

	switch msg.Type {
	case "subscribe_orderbook":
		var req struct {
			Symbol string `json:"symbol"`
		}
		if err := json.Unmarshal(msg.Payload, &req); err != nil {
			return fmt.Errorf("failed to unmarshal payload: %w", err)
		}

		// Subscribe to order book updates
		go func() {
			ctx := context.Background()
			updates, err := c.server.engine.SubscribeOrderBook(ctx, req.Symbol)
			if err != nil {
				c.server.logger.Error("OrderBook subscription failed",
					zap.String("symbol", req.Symbol),
					zap.Error(err))
				return
			}

			for update := range updates {
				data, err := json.Marshal(map[string]interface{}{
					"type":    "orderbook_update",
					"payload": update,
				})
				if err != nil {
					c.server.logger.Error("Failed to marshal orderbook update", zap.Error(err))
					continue
				}

				select {
				case c.send <- data:
				default:
					log.Printf("Client send buffer full")
				}
			}
		}()

	case "subscribe_market":
		var req struct {
			Symbol string `json:"symbol"`
		}
		if err := json.Unmarshal(msg.Payload, &req); err != nil {
			return fmt.Errorf("failed to unmarshal payload: %w", err)
		}

		// Subscribe to market data updates
		updates, err := c.server.market.SubscribePrices(context.Background(), []string{req.Symbol})
		if err != nil {
			return fmt.Errorf("failed to subscribe to market data: %w", err)
		}

		// Handle market data updates
		go func() {
			for update := range updates {
				data, err := json.Marshal(map[string]interface{}{
					"type":    "market_update",
					"payload": update,
				})
				if err != nil {
					c.server.logger.Error("Failed to marshal market update", zap.Error(err))
					continue
				}

				select {
				case c.send <- data:
				default:
					c.server.logger.Warn("Client send buffer full")
				}
			}
		}()

	default:
		return fmt.Errorf("unknown message type: %s", msg.Type)
	}

	return nil
}
