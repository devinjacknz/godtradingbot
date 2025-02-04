package trading

import (
	"context"

	"go.uber.org/zap"
)

// Service implements the TradingEngine interface for WebSocket server
type Service struct {
	engine *Engine
	logger *zap.Logger
}

// NewService creates a new trading service
func NewService(engine *Engine, logger *zap.Logger) *Service {
	return &Service{
		engine: engine,
		logger: logger,
	}
}

// PlaceOrder implements TradingEngine interface
func (s *Service) PlaceOrder(ctx context.Context, order *Order) error {
	return s.engine.PlaceOrder(order)
}

// CancelOrder implements TradingEngine interface
func (s *Service) CancelOrder(ctx context.Context, orderID string) error {
	return s.engine.CancelOrder(orderID)
}

// GetOrder implements TradingEngine interface
func (s *Service) GetOrder(ctx context.Context, orderID string) (*Order, error) {
	return s.engine.GetOrder(orderID)
}

// GetOrders implements TradingEngine interface
func (s *Service) GetOrders(ctx context.Context, userID string) ([]*Order, error) {
	return s.engine.GetOrders(userID)
}

// ExecuteTrade implements TradingEngine interface
func (s *Service) ExecuteTrade(ctx context.Context, trade *Trade) error {
	return nil // TODO: Implement trade execution
}

// GetTrades implements TradingEngine interface
func (s *Service) GetTrades(ctx context.Context, userID string) ([]*Trade, error) {
	return nil, nil // TODO: Implement get trades
}

// GetPosition implements TradingEngine interface
func (s *Service) GetPosition(ctx context.Context, userID, symbol string) (*Position, error) {
	pos := s.engine.GetPosition(symbol)
	if pos == nil {
		return nil, nil
	}
	return pos, nil
}

// GetPositions implements TradingEngine interface
func (s *Service) GetPositions(ctx context.Context, userID string) ([]*Position, error) {
	return s.engine.GetPositions(), nil
}

// GetOrderBook implements TradingEngine interface
func (s *Service) GetOrderBook(ctx context.Context, symbol string) (*OrderBook, error) {
	return nil, nil // TODO: Implement get order book
}

// SubscribeOrderBook implements TradingEngine interface
func (s *Service) SubscribeOrderBook(ctx context.Context, symbol string) (<-chan *OrderBook, error) {
	updates := make(chan *OrderBook)
	// TODO: Implement order book subscription
	return updates, nil
}
