package trading

import (
	"context"
	"time"
)

// TradingEngine defines the interface for trading operations
type TradingEngine interface {
	// Order Management
	PlaceOrder(ctx context.Context, order *Order) error
	CancelOrder(ctx context.Context, orderID string) error
	GetOrder(ctx context.Context, orderID string) (*Order, error)
	GetOrders(ctx context.Context, userID string) ([]*Order, error)

	// Trade Management
	ExecuteTrade(ctx context.Context, trade *Trade) error
	GetTrades(ctx context.Context, userID string) ([]*Trade, error)

	// Position Management
	GetPosition(ctx context.Context, userID, symbol string) (*Position, error)
	GetPositions(ctx context.Context, userID string) ([]*Position, error)

	// Market Data
	GetOrderBook(ctx context.Context, symbol string) (*OrderBook, error)
	SubscribeOrderBook(ctx context.Context, symbol string) (<-chan *OrderBook, error)
}

// OrderSide represents the side of an order
type OrderSide string

const (
	OrderSideBuy  OrderSide = "buy"
	OrderSideSell OrderSide = "sell"
)

// OrderType represents the type of an order
type OrderType string

const (
	OrderTypeMarket OrderType = "market"
	OrderTypeLimit  OrderType = "limit"
	OrderTypeStop   OrderType = "stop"
)

// OrderStatus represents the status of an order
type OrderStatus string

const (
	OrderStatusNew      OrderStatus = "new"
	OrderStatusPartial  OrderStatus = "partial"
	OrderStatusFilled   OrderStatus = "filled"
	OrderStatusCanceled OrderStatus = "canceled"
	OrderStatusRejected OrderStatus = "rejected"
)

// Order represents a trading order
type Order struct {
	ID        string      `json:"id" bson:"_id"`
	UserID    string      `json:"user_id" bson:"user_id"`
	Symbol    string      `json:"symbol" bson:"symbol"`
	Side      OrderSide   `json:"side" bson:"side"`
	Type      OrderType   `json:"type" bson:"type"`
	Price     float64     `json:"price" bson:"price"`
	Quantity  float64     `json:"quantity" bson:"quantity"`
	FilledQty float64     `json:"filled_qty" bson:"filled_qty"`
	Status    OrderStatus `json:"status" bson:"status"`
	CreatedAt time.Time   `json:"created_at" bson:"created_at"`
	UpdatedAt time.Time   `json:"updated_at" bson:"updated_at"`
}

// Trade represents an executed trade
type Trade struct {
	ID        string    `json:"id" bson:"_id"`
	OrderID   string    `json:"order_id" bson:"order_id"`
	UserID    string    `json:"user_id" bson:"user_id"`
	Symbol    string    `json:"symbol" bson:"symbol"`
	Side      OrderSide `json:"side" bson:"side"`
	Price     float64   `json:"price" bson:"price"`
	Quantity  float64   `json:"quantity" bson:"quantity"`
	Fee       float64   `json:"fee" bson:"fee"`
	Timestamp time.Time `json:"timestamp" bson:"timestamp"`
}

// Position represents a trading position
type Position struct {
	UserID        string    `json:"user_id" bson:"user_id"`
	Symbol        string    `json:"symbol" bson:"symbol"`
	Quantity      float64   `json:"quantity" bson:"quantity"`
	AvgPrice      float64   `json:"avg_price" bson:"avg_price"`
	UnrealizedPnL float64   `json:"unrealized_pnl" bson:"unrealized_pnl"`
	RealizedPnL   float64   `json:"realized_pnl" bson:"realized_pnl"`
	UpdatedAt     time.Time `json:"updated_at" bson:"updated_at"`
}

// OrderBook represents the current market state
type OrderBook struct {
	Symbol     string           `json:"symbol"`
	Bids       []OrderBookLevel `json:"bids"`
	Asks       []OrderBookLevel `json:"asks"`
	UpdateTime time.Time        `json:"update_time"`
}

// OrderBookLevel represents a price level in the order book
type OrderBookLevel struct {
	Price    float64 `json:"price"`
	Quantity float64 `json:"quantity"`
}

// Config represents trading engine configuration
type Config struct {
	Commission     float64       `json:"commission"`
	Slippage      float64       `json:"slippage"`
	MaxOrderSize   float64       `json:"max_order_size"`
	MinOrderSize   float64       `json:"min_order_size"`
	MaxPositions   int          `json:"max_positions"`
	UpdateInterval time.Duration `json:"update_interval"`
}

// Storage defines interface for trading data persistence
type Storage interface {
	SaveOrder(order *Order) error
	SaveTrade(trade *Trade) error
	SavePosition(position *Position) error
}
