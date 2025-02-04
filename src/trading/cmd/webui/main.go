package main

import (
	"context"
	"embed"
	"flag"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/spf13/viper"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
	"go.uber.org/zap"

	"github.com/devinjacknz/tradingbot/cmd/webui/server"
	"github.com/devinjacknz/tradingbot/internal/backtest"
)

//go:embed templates/*
var templates embed.FS

//go:embed static/*
var static embed.FS

func main() {
	// Parse command line flags
	configFile := flag.String("config", "configs/config.yaml", "path to config file")
	port := flag.Int("port", 8080, "port to listen on")
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

	// Create context
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

	// Initialize storage
	database := viper.GetString("database.mongodb.database")
	storage := backtest.NewMongoStorage(mongoClient, database)

	// Create server
	srv, err := server.NewServer(logger, storage, templates)
	if err != nil {
		logger.Fatal("Failed to create server", zap.Error(err))
	}

	// Register static files
	srv.RegisterStaticFiles(static)

	// Start server
	addr := fmt.Sprintf(":%d", *port)
	logger.Info("Starting server", zap.String("addr", addr))
	if err := http.ListenAndServe(addr, srv); err != nil {
		logger.Fatal("Server error", zap.Error(err))
	}
}
