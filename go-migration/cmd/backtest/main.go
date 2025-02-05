package main

import (
	"context"
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/spf13/viper"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
	"go.uber.org/zap"

	"github.com/kwanRoshi/B/go-migration/internal/backtest"
	"github.com/kwanRoshi/B/go-migration/internal/market"
	"github.com/kwanRoshi/B/go-migration/internal/market/solana"
	"github.com/kwanRoshi/B/go-migration/internal/pricing"
)

func main() {
	// Parse command line flags
	configFile := flag.String("config", "configs/config.yaml", "path to config file")
	symbol := flag.String("symbol", "BTCUSDT", "trading symbol")
	startDate := flag.String("start", "", "start date (YYYY-MM-DD)")
	endDate := flag.String("end", "", "end date (YYYY-MM-DD)")
	flag.Parse()

	// Load configuration
	viper.SetConfigFile(*configFile)
	if err := viper.ReadInConfig(); err != nil {
		log.Fatalf("Error reading config file: %s", err)
	}

	// Initialize logger
	logger, err := zap.NewProduction()
	if err != nil {
		log.Fatalf("Failed to create logger: %s", err)
	}
	defer logger.Sync()

	// Parse dates
	start, err := time.Parse("2006-01-02", *startDate)
	if err != nil {
		logger.Fatal("Invalid start date", zap.Error(err))
	}

	end, err := time.Parse("2006-01-02", *endDate)
	if err != nil {
		logger.Fatal("Invalid end date", zap.Error(err))
	}

	// Create root context
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Handle interrupts
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigChan
		logger.Info("Shutting down...")
		cancel()
	}()

	// Connect to MongoDB
	mongoCtx, mongoCancel := context.WithTimeout(ctx, 10*time.Second)
	defer mongoCancel()

	mongoURI := viper.GetString("database.mongodb.uri")
	mongoClient, err := mongo.Connect(mongoCtx, options.Client().ApplyURI(mongoURI))
	if err != nil {
		logger.Fatal("Failed to connect to MongoDB", zap.Error(err))
	}
	defer mongoClient.Disconnect(ctx)

	// Initialize storage
	database := viper.GetString("database.mongodb.database")
	storage := backtest.NewMongoStorage(mongoClient, database)

	// Initialize market data provider
	solanaConfig := solana.Config{
		BaseURL:      viper.GetString("market.providers.solana.base_url"),
		WebSocketURL: viper.GetString("market.providers.solana.ws_url"),
		DexSources:   viper.GetStringSlice("market.providers.solana.dex_sources"),
		TimeoutSec:   int(viper.GetDuration("market.providers.solana.timeout").Seconds()),
	}
	solanaProvider := solana.NewProvider(solanaConfig, logger)
	_ = market.NewHandler(solanaProvider, logger) // Create handler but don't use it in backtest

	// Initialize pricing engine
	pricingConfig := pricing.Config{
		UpdateInterval: viper.GetDuration("pricing.engine.update_interval"),
		HistorySize:   viper.GetInt("pricing.engine.history_size"),
		Indicators:    viper.GetStringSlice("pricing.engine.indicators"),
		SignalParams: pricing.SignalParams{
			MinConfidence:  viper.GetFloat64("pricing.engine.min_confidence"),
			MaxVolatility:  viper.GetFloat64("pricing.engine.max_volatility"),
		},
	}
	pricingEngine := pricing.NewEngine(pricingConfig, logger)

	// Initialize backtest engine
	backtestConfig := backtest.Config{
		StartTime:      start,
		EndTime:        end,
		InitialBalance: viper.GetFloat64("trading.risk.max_position_size"),
		Commission:     viper.GetFloat64("trading.order.commission"),
		Slippage:       viper.GetFloat64("trading.order.slippage"),
		DataSource:     "csv",
		Symbol:         *symbol,
		Interval:       viper.GetDuration("market.handler.update_interval"),
	}

	backtestEngine := backtest.NewEngine(backtestConfig, logger, pricingEngine, storage)

	// Run backtest
	logger.Info("Starting backtest",
		zap.String("symbol", *symbol),
		zap.Time("start", start),
		zap.Time("end", end))

	result, err := backtestEngine.Run(ctx)
	if err != nil {
		logger.Fatal("Backtest failed", zap.Error(err))
	}

	// Log results
	logger.Info("Backtest completed",
		zap.Int("total_trades", result.TotalTrades),
		zap.Float64("win_rate", result.WinRate),
		zap.Float64("profit_factor", result.ProfitFactor),
		zap.Float64("sharpe_ratio", result.SharpeRatio),
		zap.Float64("max_drawdown", result.MaxDrawdown),
		zap.Float64("total_return", result.TotalReturn),
		zap.Float64("annualized_return", result.AnnualizedReturn))

	// Save results
	if err := storage.SaveResult(ctx, result); err != nil {
		logger.Error("Failed to save results", zap.Error(err))
	}
}
