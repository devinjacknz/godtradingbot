package backtest

import (
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"github.com/kwanRoshi/B/go-migration/internal/pricing"
)

// CSVDataFeed implements DataFeed interface using CSV files
type CSVDataFeed struct {
	file    *os.File
	reader  *csv.Reader
	current *pricing.PriceLevel
	symbol  string
}

// NewCSVDataFeed creates a new CSV data feed
func NewCSVDataFeed(symbol string) (DataFeed, error) {
	// Look for CSV file in data directory
	filename := fmt.Sprintf("%s.csv", symbol)
	filepath := filepath.Join("data", filename)

	file, err := os.Open(filepath)
	if err != nil {
		return nil, fmt.Errorf("failed to open CSV file: %w", err)
	}

	return &CSVDataFeed{
		file:   file,
		reader: csv.NewReader(file),
		symbol: symbol,
	}, nil
}

// Next advances to next record
func (f *CSVDataFeed) Next() bool {
	record, err := f.reader.Read()
	if err != nil {
		return false
	}

	timestamp, err := time.Parse("2006-01-02 15:04:05", record[0])
	if err != nil {
		return false
	}

	price, err := strconv.ParseFloat(record[1], 64)
	if err != nil {
		return false
	}

	volume, err := strconv.ParseFloat(record[2], 64)
	if err != nil {
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
func (f *CSVDataFeed) Current() *pricing.PriceLevel {
	return f.current
}

// Close closes the data feed
func (f *CSVDataFeed) Close() error {
	return f.file.Close()
}
