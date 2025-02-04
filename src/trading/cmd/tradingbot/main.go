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

	"github.com/devinjacknz/tradingbot/internal/market"
	"github.com/devinjacknz/tradingbot/internal/market/solana"
	"github.com/devinjacknz/tradingbot/internal/types"
	"github.com/devinjacknz/tradingbot/internal/pricing"
	"github.com/devinjacknz/tradingbot/internal/storage/mongodb"
	"github.com/devinjacknz/tradingbot/internal/trading"
	"github.com/devinjacknz/tradingbot/internal/ws"
)

func main() {
	// Parse command line flags
	configFile := flag.String("config", "configs/config.yaml", "path to config file")
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

	// Create root context
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Connect to MongoDB
	mongoCtx, mongoCancel := context.WithTimeout(ctx, 10*time.Second)
	defer mongoCancel()

	mongoURI := viper.GetString("database.mongodb.uri")
	mongoClient, err := mongo.Connect(mongoCtx, options.Client().ApplyURI(mongoURI))
	if err != nil {
		logger.Fatal("Failed to connect to MongoDB", zap.Error(err))
	}
	defer mongoClient.Disconnect(ctx)

	// Initialize storage and providers
	database := viper.GetString("database.mongodb.database")
	storage := mongodb.NewTradingStorage(mongoClient, database, logger)

	// Initialize Solana provider as main provider
	solanaConfig := solana.Config{
		BaseURL:      viper.GetString("market.providers.solana.base_url"),
		WebSocketURL: viper.GetString("market.providers.solana.ws_url"),
		DexSources:   viper.GetStringSlice("market.providers.solana.dex_sources"),
		TimeoutSec:   int(viper.GetDuration("market.providers.solana.timeout").Seconds()),
	}
	solanaProvider := solana.NewProvider(solanaConfig, logger)

	// Initialize market data handler with Solana provider as main provider
	marketHandler := market.NewHandler(solanaProvider, logger)

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

	// Subscribe to symbols
	symbols := []string{"SOL/USDC", "BONK/SOL"} // Example Solana symbols
	for _, symbol := range symbols {
		ctx := context.Background()
		updates, err := marketHandler.SubscribePrices(ctx, []string{symbol})
		if err != nil {
			logger.Error("Failed to subscribe to symbol",
				zap.String("symbol", symbol),
				zap.Error(err))
			continue
		}
		go handleUpdates(ctx, logger, updates)
	}

	// Start signal processing
	go handleSignals(ctx, logger, pricingEngine)

	// Initialize trading engine
	tradingConfig := trading.Config{
		Commission:     viper.GetFloat64("trading.order.commission"),
		Slippage:      viper.GetFloat64("trading.order.slippage"),
		MaxOrderSize:   viper.GetFloat64("trading.risk.max_order_size"),
		MinOrderSize:   viper.GetFloat64("trading.risk.min_order_size"),
		MaxPositions:   viper.GetInt("trading.risk.max_positions"),
		UpdateInterval: viper.GetDuration("trading.engine.update_interval"),
	}
	tradingEngine := trading.NewEngine(tradingConfig, logger, storage)

	// Initialize WebSocket server
	wsConfig := ws.Config{
		Port:           viper.GetInt("server.websocket.port"),
		PingInterval:   viper.GetDuration("server.websocket.ping_interval"),
		PongWait:       viper.GetDuration("server.websocket.pong_wait"),
		WriteWait:      10 * time.Second,
		MaxMessageSize: 1024 * 1024, // 1MB
	}
	// Create trading service that implements TradingEngine interface
	tradingService := trading.NewService(tradingEngine, logger)
	wsServer := ws.NewServer(wsConfig, logger, tradingService, marketHandler)

	// Start WebSocket server
	go wsServer.Start()

	// Wait for shutdown signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan

	// Graceful shutdown
	logger.Info("Shutting down...")
	cancel() // Cancel root context

	// Wait for cleanup
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()

	// Add cleanup code here
	if err := mongoClient.Disconnect(shutdownCtx); err != nil {
		logger.Error("Failed to disconnect from MongoDB", zap.Error(err))
	}
}

// handleSignals processes trading signals from the pricing engine
func handleSignals(ctx context.Context, logger *zap.Logger, engine *pricing.Engine) {
	signals := engine.GetSignals()
	for {
		select {
		case <-ctx.Done():
			return
		case signal := <-signals:
			logger.Info("Received trading signal",
				zap.String("symbol", signal.Symbol),
				zap.String("type", signal.Type),
				zap.String("direction", signal.Direction),
				zap.Float64("price", signal.Price),
				zap.Float64("confidence", signal.Confidence))
		}
	}
}

// handleUpdates processes price updates from market data providers
func handleUpdates(ctx context.Context, logger *zap.Logger, updates <-chan *types.PriceUpdate) {
	for {
		select {
		case <-ctx.Done():
			return
		case update := <-updates:
			logger.Debug("Received price update",
				zap.String("symbol", update.Symbol),
				zap.Float64("price", update.Price),
				zap.Float64("volume", update.Volume),
				zap.Time("timestamp", update.Timestamp))
		}
	}
}
