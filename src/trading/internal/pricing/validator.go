package pricing

import (
	"time"

	"github.com/devinjacknz/tradingbot/internal/types"
	"github.com/devinjacknz/tradingbot/internal/utils"
)

// ValidationRule represents a signal validation rule
type ValidationRule func(*types.Signal) bool

// Validator handles signal validation and filtering
type Validator struct {
	rules []ValidationRule
}

// NewValidator creates a new signal validator
func NewValidator() *Validator {
	v := &Validator{
		rules: make([]ValidationRule, 0),
	}

	// Register default validation rules
	v.RegisterRule(validateTimestamp)
	v.RegisterRule(validatePrice)
	v.RegisterRule(validateConfidence)
	v.RegisterRule(validateIndicators)

	// Register strategy-specific validation rules
	v.RegisterRule(validateRSISignal)
	v.RegisterRule(validateMACDSignal)
	v.RegisterRule(validateBBSignal)

	// Register combined strategy validation rules
	v.RegisterRule(validateRSIAndMACD)
	v.RegisterRule(validateVolatilityFilter)

	return v
}

// RegisterRule adds a new validation rule
func (v *Validator) RegisterRule(rule ValidationRule) {
	v.rules = append(v.rules, rule)
}

// Validate checks if a signal passes all validation rules
func (v *Validator) Validate(signal *types.Signal) bool {
	for _, rule := range v.rules {
		if !rule(signal) {
			return false
		}
	}
	return true
}

// FilterSignals filters a slice of signals using validation rules
func (v *Validator) FilterSignals(signals []*types.Signal) []*types.Signal {
	filtered := make([]*types.Signal, 0)
	for _, signal := range signals {
		if v.Validate(signal) {
			filtered = append(filtered, signal)
		}
	}
	return filtered
}

// Default validation rules

func validateTimestamp(s *types.Signal) bool {
	// Check if timestamp is not too old (within last hour)
	return time.Since(s.Timestamp) <= time.Hour
}

func validatePrice(s *types.Signal) bool {
	// Check if price is positive
	return s.Price > 0
}

func validateConfidence(s *types.Signal) bool {
	// Check if confidence is between 0 and 1
	return s.Confidence >= 0 && s.Confidence <= 1
}

func validateIndicators(s *types.Signal) bool {
	// Check if signal has at least one indicator
	return len(s.Indicators) > 0
}

// Strategy-specific validation rules

func validateRSISignal(s *types.Signal) bool {
	for _, ind := range s.Indicators {
		if ind.Name == "RSI" {
			// Require strong oversold/overbought conditions
			if s.Direction == "long" {
				return ind.Value <= 25 // Strong oversold
			}
			if s.Direction == "short" {
				return ind.Value >= 75 // Strong overbought
			}
		}
	}
	return false
}

func validateMACDSignal(s *types.Signal) bool {
	for _, ind := range s.Indicators {
		if ind.Name == "MACD" {
			// Require minimum MACD value for signal strength
			params := ind.Params.(map[string]interface{})
			if signal, ok := params["signal"].(float64); ok {
				return utils.Abs(ind.Value-signal) >= 0.0001*s.Price
			}
		}
	}
	return false
}

func validateBBSignal(s *types.Signal) bool {
	for _, ind := range s.Indicators {
		if ind.Name == "BB" {
			params := ind.Params.(map[string]interface{})
			upper := params["upper"].(float64)
			lower := params["lower"].(float64)

			// Require price to be significantly outside bands
			if s.Direction == "long" {
				return s.Price <= lower*0.995 // 0.5% below lower band
			}
			if s.Direction == "short" {
				return s.Price >= upper*1.005 // 0.5% above upper band
			}
		}
	}
	return false
}

// Combined strategy validation rules

func validateRSIAndMACD(s *types.Signal) bool {
	var rsiValid, macdValid bool
	var rsiValue, macdValue float64

	for _, ind := range s.Indicators {
		switch ind.Name {
		case "RSI":
			rsiValue = ind.Value
			if s.Direction == "long" {
				rsiValid = rsiValue <= 30
			} else {
				rsiValid = rsiValue >= 70
			}
		case "MACD":
			macdValue = ind.Value
			if s.Direction == "long" {
				macdValid = macdValue > 0
			} else {
				macdValid = macdValue < 0
			}
		}
	}

	return rsiValid && macdValid
}

func validateVolatilityFilter(s *types.Signal) bool {
	for _, ind := range s.Indicators {
		if ind.Name == "BB" {
			params := ind.Params.(map[string]interface{})
			upper := params["upper"].(float64)
			lower := params["lower"].(float64)
			middle := params["middle"].(float64)

			// Calculate volatility as percentage of price
			volatility := (upper - lower) / middle
			return volatility <= 0.02 // Maximum 2% volatility
		}
	}
	return true // Pass if no BB indicator
}
