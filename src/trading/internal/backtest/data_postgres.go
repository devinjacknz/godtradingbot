package backtest

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	_ "github.com/lib/pq"
	"go.uber.org/zap"

	"github.com/devinjacknz/tradingbot/internal/pricing"
)

// PostgresConfig represents PostgreSQL configuration
type PostgresConfig struct {
	Host     string
	Port     int
	User     string
	Password string
	DBName   string
	SSLMode  string
}

// PostgresDataFeed implements DataFeed interface using PostgreSQL
type PostgresDataFeed struct {
	db        *sql.DB
	rows      *sql.Rows
	current   *pricing.PriceLevel
	symbol    string
	startTime time.Time
	endTime   time.Time
	interval  time.Duration
	logger    *zap.Logger
}

// NewPostgresDataFeed creates a new PostgreSQL data feed
func NewPostgresDataFeed(ctx context.Context, config PostgresConfig, logger *zap.Logger, symbol string, start, end time.Time, interval time.Duration) (DataFeed, error) {
	// Connect to database
	connStr := fmt.Sprintf(
		"host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		config.Host,
		config.Port,
		config.User,
		config.Password,
		config.DBName,
		config.SSLMode,
	)

	db, err := sql.Open("postgres", connStr)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	// Query market data
	query := `
		SELECT timestamp, price, volume
		FROM market_data
		WHERE symbol = $1
		AND timestamp BETWEEN $2 AND $3
		ORDER BY timestamp ASC
	`
	rows, err := db.QueryContext(ctx, query, symbol, start, end)
	if err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to query market data: %w", err)
	}

	return &PostgresDataFeed{
		db:        db,
		rows:      rows,
		symbol:    symbol,
		startTime: start,
		endTime:   end,
		interval:  interval,
		logger:    logger,
	}, nil
}

// Next advances to next record
func (f *PostgresDataFeed) Next() bool {
	if !f.rows.Next() {
		return false
	}

	var timestamp time.Time
	var price, volume float64
	if err := f.rows.Scan(&timestamp, &price, &volume); err != nil {
		f.logger.Error("Failed to scan row",
			zap.Error(err),
			zap.String("symbol", f.symbol),
		)
		return false
	}

	f.current = &pricing.PriceLevel{
		Symbol:    f.symbol,
		Price:     price,
		Volume:    volume,
		Timestamp: timestamp,
	}

	return true
}

// Current returns current price level
func (f *PostgresDataFeed) Current() *pricing.PriceLevel {
	return f.current
}

// Close closes the data feed
func (f *PostgresDataFeed) Close() error {
	if f.rows != nil {
		f.rows.Close()
	}
	if f.db != nil {
		return f.db.Close()
	}
	return nil
}
