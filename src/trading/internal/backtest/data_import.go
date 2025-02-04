package backtest

import (
	"context"
	"database/sql"
	"fmt"

	"go.uber.org/zap"
)

// CreateMarketDataTable creates the market data table in the database
func CreateMarketDataTable(ctx context.Context, db *sql.DB) error {
	query := `
		CREATE TABLE IF NOT EXISTS market_data (
			id SERIAL PRIMARY KEY,
			symbol VARCHAR(20) NOT NULL,
			timestamp TIMESTAMP NOT NULL,
			price DECIMAL(20,8) NOT NULL,
			volume DECIMAL(20,8) NOT NULL,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			UNIQUE(symbol, timestamp)
		)
	`
	_, err := db.ExecContext(ctx, query)
	return err
}

// ImportCSVData imports data from a CSV feed into the database
func ImportCSVData(ctx context.Context, db *sql.DB, feed DataFeed, symbol string, logger *zap.Logger) error {
	// Prepare insert statement
	stmt, err := db.PrepareContext(ctx, `
		INSERT INTO market_data (symbol, timestamp, price, volume)
		VALUES ($1, $2, $3, $4)
		ON CONFLICT (symbol, timestamp) DO NOTHING
	`)
	if err != nil {
		return fmt.Errorf("failed to prepare statement: %w", err)
	}
	defer stmt.Close()

	// Import data
	var count int
	for feed.Next() {
		data := feed.Current()
		_, err := stmt.ExecContext(ctx,
			symbol,
			data.Timestamp,
			data.Price,
			data.Volume,
		)
		if err != nil {
			logger.Error("Failed to insert row",
				zap.Error(err),
				zap.String("symbol", symbol),
				zap.Time("timestamp", data.Timestamp),
			)
			continue
		}
		count++
		if count%1000 == 0 {
			logger.Info("Import progress",
				zap.Int("rows", count),
				zap.String("symbol", symbol),
			)
		}
	}

	logger.Info("Import completed",
		zap.Int("total_rows", count),
	)
	return nil
}
