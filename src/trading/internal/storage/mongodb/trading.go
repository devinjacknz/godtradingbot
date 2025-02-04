package mongodb

import (
	"context"

	"go.mongodb.org/mongo-driver/mongo"
	"go.uber.org/zap"

	"github.com/devinjacknz/tradingbot/internal/trading"
)

// TradingStorage implements trading.Storage interface
type TradingStorage struct {
	client *mongo.Client
	db     string
	logger *zap.Logger
}

// NewTradingStorage creates a new trading storage
func NewTradingStorage(client *mongo.Client, db string, logger *zap.Logger) *TradingStorage {
	return &TradingStorage{
		client: client,
		db:     db,
		logger: logger,
	}
}

// SaveOrder implements trading.Storage interface
func (s *TradingStorage) SaveOrder(order *trading.Order) error {
	collection := s.client.Database(s.db).Collection("orders")
	ctx := context.Background()
	_, err := collection.InsertOne(ctx, order)
	return err
}

// SaveTrade implements trading.Storage interface
func (s *TradingStorage) SaveTrade(trade *trading.Trade) error {
	collection := s.client.Database(s.db).Collection("trades")
	ctx := context.Background()
	_, err := collection.InsertOne(ctx, trade)
	return err
}

// SavePosition implements trading.Storage interface
func (s *TradingStorage) SavePosition(position *trading.Position) error {
	collection := s.client.Database(s.db).Collection("positions")
	ctx := context.Background()
	_, err := collection.InsertOne(ctx, position)
	return err
}
