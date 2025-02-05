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

	"github.com/kwanRoshi/B/go-migration/internal/market"
	"github.com/kwanRoshi/B/go-migration/internal/market/pump"
	"github.com/kwanRoshi/B/go-migration/internal/market/solana"
	"github.com/kwanRoshi/B/go-migration/internal/metrics"
	"github.com/kwanRoshi/B/go-migration/internal/monitoring"
	"github.com/kwanRoshi/B/go-migration/internal/types"
	"github.com/kwanRoshi/B/go-migration/internal/pricing"
	"github.com/kwanRoshi/B/go-migration/internal/storage/mongodb"
	"github.com/kwanRoshi/B/go-migration/internal/trading"
	"github.com/kwanRoshi/B/go-migration/internal/trading/executor"
	"github.com/kwanRoshi/B/go-migration/internal/trading/grpc"
	"github.com/kwanRoshi/B/go-migration/internal/trading/strategy"
	"github.com/kwanRoshi/B/go-migration/internal/ws"
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

	// Initialize Solana provider
	solanaConfig := solana.Config{
		BaseURL:      viper.GetString("market.providers.solana.base_url"),
		WebSocketURL: viper.GetString("market.providers.solana.ws_url"),
		DexSources:   viper.GetStringSlice("market.providers.solana.dex_sources"),
		TimeoutSec:   int(viper.GetDuration("market.providers.solana.timeout").Seconds()),
	}
	solanaProvider := solana.NewProvider(solanaConfig, logger)

	// Initialize pump.fun provider
	pumpConfig := pump.Config{
		BaseURL:      viper.GetString("market.providers.pump.base_url"),
		WebSocketURL: viper.GetString("market.providers.pump.ws_url"),
		TimeoutSec:   int(viper.GetDuration("market.providers.pump.timeout").Seconds()),
	}
	pumpProvider := pump.NewProvider(pumpConfig, logger)

	// Initialize market data handler with both providers
	marketHandler := market.NewHandler([]market.Provider{solanaProvider, pumpProvider}, logger)

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
	symbols := []string{"SOL/USDC", "BONK/SOL"} // Solana symbols
	pumpSymbols := []string{"PUMP/SOL"} // pump.fun symbols
	symbols = append(symbols, pumpSymbols...)
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

	// Load trading configuration
	var tradingCfg strategy.TradingConfig
	if err := viper.UnmarshalKey("trading", &tradingCfg); err != nil {
		logger.Fatal("Failed to parse trading config", zap.Error(err))
	}

	// Initialize trading executor
	secrets, err := config.LoadSecrets()
	if err != nil {
		logger.Fatal("Failed to load secrets", zap.Error(err))
	}

	tradingExecutor := executor.NewTradingExecutor(&tradingCfg, pumpProvider, metrics.NewPumpMetrics(), logger)
	if err := tradingExecutor.Start(ctx); err != nil {
		logger.Fatal("Failed to start trading executor", zap.Error(err))
	}

	// Initialize monitoring service
	monitoringService := monitoring.NewService(pumpProvider, metrics.NewPumpMetrics(), logger)
	if err := monitoringService.Start(ctx); err != nil {
		logger.Fatal("Failed to start monitoring service", zap.Error(err))
	}

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

	// Initialize and start gRPC server
	grpcServer := grpc.NewServer(tradingService, logger)
	if err := grpcServer.Start(viper.GetInt("server.grpc.port")); err != nil {
		logger.Fatal("Failed to start gRPC server", zap.Error(err))
	}

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
