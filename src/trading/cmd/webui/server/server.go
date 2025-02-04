package server

import (
	"context"
	"embed"
	"encoding/json"
	"fmt"
	"html/template"
	"net/http"
	"time"

	"github.com/gorilla/mux"
	"go.uber.org/zap"

	"github.com/devinjacknz/tradingbot/internal/backtest"
)

// Server represents the web UI server
type Server struct {
	logger  *zap.Logger
	storage backtest.Storage
	router  *mux.Router
	tmpl    *template.Template
}

// NewServer creates a new web UI server
func NewServer(logger *zap.Logger, storage backtest.Storage, templates embed.FS) (*Server, error) {
	// Parse templates
	tmpl, err := template.ParseFS(templates, "templates/*.html")
	if err != nil {
		return nil, fmt.Errorf("failed to parse templates: %w", err)
	}

	// Create router
	router := mux.NewRouter()

	server := &Server{
		logger:  logger,
		storage: storage,
		router:  router,
		tmpl:    tmpl,
	}

	// Register routes
	router.HandleFunc("/", server.handleIndex)
	router.HandleFunc("/results", server.handleResults)
	router.HandleFunc("/result/{id}", server.handleResult)
	router.HandleFunc("/api/results", server.handleAPIResults)
	router.HandleFunc("/api/result/{id}", server.handleAPIResult)
	router.HandleFunc("/api/signals/{symbol}", server.handleAPISignals)

	return server, nil
}

// ServeHTTP implements the http.Handler interface
func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.router.ServeHTTP(w, r)
}

// RegisterStaticFiles registers static file handlers
func (s *Server) RegisterStaticFiles(static embed.FS) {
	// Serve static files
	fs := http.FileServer(http.FS(static))
	s.router.PathPrefix("/static/").Handler(http.StripPrefix("/static/", fs))
}

func (s *Server) handleIndex(w http.ResponseWriter, r *http.Request) {
	s.tmpl.ExecuteTemplate(w, "index.html", nil)
}

func (s *Server) handleResults(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	// Get recent results
	results, err := s.getRecentResults(ctx)
	if err != nil {
		s.logger.Error("Failed to get results", zap.Error(err))
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	// Convert to response type
	response := make([]ResultResponse, len(results))
	for i, result := range results {
		response[i] = convertResult(result)
	}

	s.tmpl.ExecuteTemplate(w, "results.html", response)
}

func (s *Server) handleResult(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]

	ctx := r.Context()

	// Get result
	result, err := s.storage.LoadResult(ctx, id)
	if err != nil {
		s.logger.Error("Failed to load result", zap.Error(err))
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	// Convert to response type
	response := convertResult(result)
	s.tmpl.ExecuteTemplate(w, "result.html", response)
}

func (s *Server) handleAPIResults(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	// Get recent results
	results, err := s.getRecentResults(ctx)
	if err != nil {
		s.logger.Error("Failed to get results", zap.Error(err))
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	// Convert to response type
	response := make([]ResultResponse, len(results))
	for i, result := range results {
		response[i] = convertResult(result)
	}

	json.NewEncoder(w).Encode(response)
}

func (s *Server) handleAPIResult(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]

	ctx := r.Context()

	// Get result
	result, err := s.storage.LoadResult(ctx, id)
	if err != nil {
		s.logger.Error("Failed to load result", zap.Error(err))
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	// Convert to response type
	response := convertResult(result)
	json.NewEncoder(w).Encode(response)
}

func (s *Server) handleAPISignals(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	symbol := vars["symbol"]

	ctx := r.Context()

	// Parse time range
	startStr := r.URL.Query().Get("start")
	endStr := r.URL.Query().Get("end")

	var start, end time.Time
	var err error

	if startStr != "" {
		start, err = time.Parse("2006-01-02", startStr)
		if err != nil {
			http.Error(w, "Invalid start date", http.StatusBadRequest)
			return
		}
	} else {
		start = time.Now().AddDate(0, -1, 0) // Default to last month
	}

	if endStr != "" {
		end, err = time.Parse("2006-01-02", endStr)
		if err != nil {
			http.Error(w, "Invalid end date", http.StatusBadRequest)
			return
		}
	} else {
		end = time.Now()
	}

	// Get signals
	signals, err := s.storage.LoadSignals(ctx, symbol, start, end)
	if err != nil {
		s.logger.Error("Failed to load signals", zap.Error(err))
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	json.NewEncoder(w).Encode(signals)
}

func (s *Server) getRecentResults(ctx context.Context) ([]*backtest.Result, error) {
	// TODO: Implement getting recent results from storage
	return nil, nil
}

// Helper functions

func convertResult(result *backtest.Result) ResultResponse {
	response := ResultResponse{
		TotalTrades:      result.TotalTrades,
		WinningTrades:    result.WinningTrades,
		LosingTrades:     result.LosingTrades,
		WinRate:          result.WinRate,
		ProfitFactor:     result.ProfitFactor,
		SharpeRatio:      result.SharpeRatio,
		MaxDrawdown:      result.MaxDrawdown,
		FinalBalance:     result.FinalBalance,
		TotalReturn:      result.TotalReturn,
		AnnualizedReturn: result.AnnualizedReturn,
		Trades:           make([]Trade, len(result.Trades)),
		Metrics:          convertMetrics(result.Metrics),
	}

	// Convert trades
	for i, trade := range result.Trades {
		response.Trades[i] = convertTrade(trade)
	}

	return response
}

func convertTrade(trade *backtest.Trade) Trade {
	return Trade{
		Symbol:     trade.Symbol,
		Direction:  trade.Direction,
		EntryTime:  trade.EntryTime,
		ExitTime:   trade.ExitTime,
		EntryPrice: trade.EntryPrice,
		ExitPrice:  trade.ExitPrice,
		Quantity:   trade.Quantity,
		PnL:        trade.PnL,
		Commission: trade.Commission,
		Slippage:   trade.Slippage,
	}
}

func convertMetrics(metrics *backtest.Metrics) *Metrics {
	if metrics == nil {
		return nil
	}

	return &Metrics{
		DailyReturns:     metrics.DailyReturns,
		MonthlyReturns:   metrics.MonthlyReturns,
		ReturnsBySymbol:  metrics.ReturnsBySymbol,
		DrawdownSeries:   metrics.DrawdownSeries,
		VolatilitySeries: metrics.VolatilitySeries,
	}
}
