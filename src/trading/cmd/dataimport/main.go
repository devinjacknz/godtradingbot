package main

import (
	"context"
	"database/sql"
	"flag"
	"fmt"
	"os"

	_ "github.com/lib/pq"
	"go.uber.org/zap"

	"github.com/devinjacknz/tradingbot/internal/backtest"
)

func main() {
	// Parse command line flags
	var (
		symbol   = flag.String("symbol", "", "Trading symbol (e.g., BTC/USD)")
		dbHost   = flag.String("db-host", "localhost", "Database host")
		dbPort   = flag.Int("db-port", 5432, "Database port")
		dbUser   = flag.String("db-user", "postgres", "Database user")
		dbPass   = flag.String("db-pass", "", "Database password")
		dbName   = flag.String("db-name", "tradingbot", "Database name")
		dbSSL    = flag.String("db-ssl", "disable", "Database SSL mode")
	)
	flag.Parse()

	if *symbol == "" {
		fmt.Println("Symbol is required")
		os.Exit(1)
	}

	// Initialize logger
	logger, err := zap.NewDevelopment()
	if err != nil {
		fmt.Printf("Failed to create logger: %v\n", err)
		os.Exit(1)
	}
	defer logger.Sync()

	// Connect to database
	connStr := fmt.Sprintf(
		"host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		*dbHost,
		*dbPort,
		*dbUser,
		*dbPass,
		*dbName,
		*dbSSL,
	)

	db, err := sql.Open("postgres", connStr)
	if err != nil {
		logger.Fatal("Failed to connect to database",
			zap.Error(err),
		)
	}
	defer db.Close()

	ctx := context.Background()

	// Create market data table
	if err := backtest.CreateMarketDataTable(ctx, db); err != nil {
		logger.Fatal("Failed to create market data table",
			zap.Error(err),
		)
	}

	// Create CSV data feed
	feed, err := backtest.NewCSVDataFeed(*symbol)
	if err != nil {
		logger.Fatal("Failed to create CSV data feed",
			zap.Error(err),
			zap.String("symbol", *symbol),
		)
	}
	defer feed.Close()

	// Import data
	if err := backtest.ImportCSVData(ctx, db, feed, *symbol, logger); err != nil {
		logger.Fatal("Failed to import data",
			zap.Error(err),
			zap.String("symbol", *symbol),
		)
	}
}
