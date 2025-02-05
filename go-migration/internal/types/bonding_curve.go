package types

import "time"

type BondingCurve struct {
	Symbol       string    `json:"symbol"`
	CurrentPrice float64   `json:"current_price"`
	BasePrice    float64   `json:"base_price"`
	Slope        float64   `json:"slope"`
	Supply       int64     `json:"supply"`
	MaxSupply    int64     `json:"max_supply"`
	UpdateTime   time.Time `json:"update_time"`
}
