package pricing

// SignalType represents different types of trading signals
type SignalType string

const (
	SignalTypeEntry SignalType = "entry"
	SignalTypeExit  SignalType = "exit"
	SignalTypeAlert SignalType = "alert"
)

// SignalDirection represents the direction of a trading signal
type SignalDirection string

const (
	SignalDirectionLong  SignalDirection = "long"
	SignalDirectionShort SignalDirection = "short"
	SignalDirectionFlat  SignalDirection = "flat"
)
