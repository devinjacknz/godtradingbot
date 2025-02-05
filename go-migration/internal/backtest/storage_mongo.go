package backtest

import (
	"context"
	"fmt"
	"time"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
	"go.uber.org/zap"

	"github.com/kwanRoshi/B/go-migration/internal/pricing"
)

// MongoStorage implements Storage interface using MongoDB
type MongoStorage struct {
	client *mongo.Client
	db     string
	logger *zap.Logger
}

// MongoConfig represents MongoDB configuration
type MongoConfig struct {
	URI      string
	Database string
}

// NewMongoStorage creates a new MongoDB storage
func NewMongoStorage(config MongoConfig, logger *zap.Logger) (*MongoStorage, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	client, err := mongo.Connect(ctx, options.Client().ApplyURI(config.URI))
	if err != nil {
		return nil, fmt.Errorf("failed to connect to MongoDB: %w", err)
	}

	// Ping the database
	if err := client.Ping(ctx, nil); err != nil {
		return nil, fmt.Errorf("failed to ping MongoDB: %w", err)
	}

	return &MongoStorage{
		client: client,
		db:     config.Database,
		logger: logger,
	}, nil
}

// SaveResult implements Storage interface
func (s *MongoStorage) SaveResult(ctx context.Context, result *Result) error {
	collection := s.client.Database(s.db).Collection("backtest_results")
	_, err := collection.InsertOne(ctx, result)
	if err != nil {
		return fmt.Errorf("failed to save backtest result: %w", err)
	}
	return nil
}

// SaveSignals implements Storage interface
func (s *MongoStorage) SaveSignals(ctx context.Context, signals []*pricing.Signal) error {
	if len(signals) == 0 {
		return nil
	}

	collection := s.client.Database(s.db).Collection("backtest_signals")

	// Convert signals to interface{} for bulk write
	docs := make([]interface{}, len(signals))
	for i, signal := range signals {
		docs[i] = signal
	}

	_, err := collection.InsertMany(ctx, docs)
	if err != nil {
		return fmt.Errorf("failed to save signals: %w", err)
	}
	return nil
}

// LoadResult implements Storage interface
func (s *MongoStorage) LoadResult(ctx context.Context, id string) (*Result, error) {
	collection := s.client.Database(s.db).Collection("backtest_results")

	var result Result
	err := collection.FindOne(ctx, bson.M{"_id": id}).Decode(&result)
	if err != nil {
		if err == mongo.ErrNoDocuments {
			return nil, fmt.Errorf("backtest result not found: %s", id)
		}
		return nil, fmt.Errorf("failed to load backtest result: %w", err)
	}

	return &result, nil
}

// LoadSignals implements Storage interface
func (s *MongoStorage) LoadSignals(ctx context.Context, symbol string, start, end time.Time) ([]*pricing.Signal, error) {
	collection := s.client.Database(s.db).Collection("backtest_signals")

	filter := bson.M{
		"symbol": symbol,
		"timestamp": bson.M{
			"$gte": start,
			"$lte": end,
		},
	}

	cursor, err := collection.Find(ctx, filter)
	if err != nil {
		return nil, fmt.Errorf("failed to load signals: %w", err)
	}
	defer cursor.Close(ctx)

	var signals []*pricing.Signal
	if err := cursor.All(ctx, &signals); err != nil {
		return nil, fmt.Errorf("failed to decode signals: %w", err)
	}

	return signals, nil
}

// Close closes the MongoDB connection
func (s *MongoStorage) Close(ctx context.Context) error {
	return s.client.Disconnect(ctx)
}
