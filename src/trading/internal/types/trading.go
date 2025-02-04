package types

import "time"

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

// RiskMetrics represents account risk metrics
type RiskMetrics struct {
	UserID          string    `json:"user_id"`
	TotalEquity     float64   `json:"total_equity"`
	UsedMargin      float64   `json:"used_margin"`
	AvailableMargin float64   `json:"available_margin"`
	MarginLevel     float64   `json:"margin_level"`
	DailyPnL        float64   `json:"daily_pnl"`
	UpdateTime      time.Time `json:"update_time"`
}
