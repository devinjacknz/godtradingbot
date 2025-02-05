package trading

import (
	"fmt"
	"sync"

	"github.com/kwanRoshi/B/go-migration/internal/types"
	"go.uber.org/zap"
)

// Engine manages trading operations
type Engine struct {
	logger     *zap.Logger
	config     Config
	storage    Storage
	positions  map[string]*types.Position
	orders     map[string]*types.Order
	mu         sync.RWMutex
	totalValue float64
}

// NewEngine creates a new trading engine
func NewEngine(config Config, logger *zap.Logger, storage Storage) *Engine {
	return &Engine{
		logger:     logger,
		config:     config,
		storage:    storage,
		positions:  make(map[string]*types.Position),
		orders:     make(map[string]*types.Order),
		totalValue: 0,
	}
}

func (e *Engine) GetTotalValue() float64 {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.totalValue
}

// PlaceOrder places a new order
func (e *Engine) PlaceOrder(order *types.Order) error {
	// Validate order
	if err := e.validateOrder(order); err != nil {
		return err
	}

	// Store order
	e.mu.Lock()
	e.orders[order.ID] = order
	e.mu.Unlock()

	return e.storage.SaveOrder(order)
}

// CancelOrder cancels an existing order
func (e *Engine) CancelOrder(orderID string) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	order, exists := e.orders[orderID]
	if !exists {
		return fmt.Errorf("order not found: %s", orderID)
	}

	order.Status = types.OrderStatusCanceled
	delete(e.orders, orderID)

	return e.storage.SaveOrder(order)
}

// GetOrder returns an order by ID
func (e *Engine) GetOrder(orderID string) (*types.Order, error) {
	e.mu.RLock()
	defer e.mu.RUnlock()

	order, exists := e.orders[orderID]
	if !exists {
		return nil, fmt.Errorf("order not found: %s", orderID)
	}
	return order, nil
}

// GetOrders returns all orders for a user
func (e *Engine) GetOrders(userID string) ([]*types.Order, error) {
	e.mu.RLock()
	defer e.mu.RUnlock()

	var orders []*types.Order
	for _, order := range e.orders {
		if order.UserID == userID {
			orders = append(orders, order)
		}
	}
	return orders, nil
}

// GetPosition returns current position for a symbol
func (e *Engine) GetPosition(symbol string) *types.Position {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.positions[symbol]
}

// GetPositions returns all current positions
func (e *Engine) GetPositions() []*types.Position {
	e.mu.RLock()
	defer e.mu.RUnlock()

	positions := make([]*types.Position, 0, len(e.positions))
	for _, pos := range e.positions {
		positions = append(positions, pos)
	}
	return positions
}

// Internal methods

func (e *Engine) validateOrder(order *types.Order) error {
	if order.Quantity < e.config.MinOrderSize {
		return fmt.Errorf("order size too small: %f < %f",
			order.Quantity, e.config.MinOrderSize)
	}
	if order.Quantity > e.config.MaxOrderSize {
		return fmt.Errorf("order size too large: %f > %f",
			order.Quantity, e.config.MaxOrderSize)
	}
	return nil
}
