from typing import ClassVar as _ClassVar
from typing import Iterable as _Iterable
from typing import Mapping as _Mapping
from typing import Optional as _Optional
from typing import Union as _Union

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf.internal import containers as _containers

DESCRIPTOR: _descriptor.FileDescriptor

class MarketDataRequest(_message.Message):
    __slots__ = ("symbol", "timeframe", "limit")
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    symbol: str
    timeframe: str
    limit: int
    def __init__(
        self,
        symbol: _Optional[str] = ...,
        timeframe: _Optional[str] = ...,
        limit: _Optional[int] = ...,
    ) -> None: ...

class MarketDataReply(_message.Message):
    __slots__ = ("candles",)
    CANDLES_FIELD_NUMBER: _ClassVar[int]
    candles: _containers.RepeatedCompositeFieldContainer[Candle]
    def __init__(
        self, candles: _Optional[_Iterable[_Union[Candle, _Mapping]]] = ...
    ) -> None: ...

class Candle(_message.Message):
    __slots__ = ("open", "high", "low", "close", "volume", "timestamp")
    OPEN_FIELD_NUMBER: _ClassVar[int]
    HIGH_FIELD_NUMBER: _ClassVar[int]
    LOW_FIELD_NUMBER: _ClassVar[int]
    CLOSE_FIELD_NUMBER: _ClassVar[int]
    VOLUME_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: int
    def __init__(
        self,
        open: _Optional[float] = ...,
        high: _Optional[float] = ...,
        low: _Optional[float] = ...,
        close: _Optional[float] = ...,
        volume: _Optional[float] = ...,
        timestamp: _Optional[int] = ...,
    ) -> None: ...

class TradeRequest(_message.Message):
    __slots__ = ("symbol", "side", "amount", "price", "order_type", "slippage")
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    SLIPPAGE_FIELD_NUMBER: _ClassVar[int]
    symbol: str
    side: str
    amount: float
    price: float
    order_type: str
    slippage: float
    def __init__(
        self,
        symbol: _Optional[str] = ...,
        side: _Optional[str] = ...,
        amount: _Optional[float] = ...,
        price: _Optional[float] = ...,
        order_type: _Optional[str] = ...,
        slippage: _Optional[float] = ...,
    ) -> None: ...

class TradeReply(_message.Message):
    __slots__ = ("order_id", "status", "executed_price", "executed_amount", "timestamp")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    EXECUTED_PRICE_FIELD_NUMBER: _ClassVar[int]
    EXECUTED_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    status: str
    executed_price: float
    executed_amount: float
    timestamp: int
    def __init__(
        self,
        order_id: _Optional[str] = ...,
        status: _Optional[str] = ...,
        executed_price: _Optional[float] = ...,
        executed_amount: _Optional[float] = ...,
        timestamp: _Optional[int] = ...,
    ) -> None: ...

class OrderStatusRequest(_message.Message):
    __slots__ = ("order_id",)
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    def __init__(self, order_id: _Optional[str] = ...) -> None: ...

class OrderStatusReply(_message.Message):
    __slots__ = (
        "order_id",
        "status",
        "filled_amount",
        "average_price",
        "error_message",
    )
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    FILLED_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    AVERAGE_PRICE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    status: str
    filled_amount: float
    average_price: float
    error_message: str
    def __init__(
        self,
        order_id: _Optional[str] = ...,
        status: _Optional[str] = ...,
        filled_amount: _Optional[float] = ...,
        average_price: _Optional[float] = ...,
        error_message: _Optional[str] = ...,
    ) -> None: ...

class PriceSubscriptionRequest(_message.Message):
    __slots__ = ("symbols", "update_interval_ms")
    SYMBOLS_FIELD_NUMBER: _ClassVar[int]
    UPDATE_INTERVAL_MS_FIELD_NUMBER: _ClassVar[int]
    symbols: _containers.RepeatedScalarFieldContainer[str]
    update_interval_ms: int
    def __init__(
        self,
        symbols: _Optional[_Iterable[str]] = ...,
        update_interval_ms: _Optional[int] = ...,
    ) -> None: ...

class PriceUpdateReply(_message.Message):
    __slots__ = ("symbol", "price", "volume", "timestamp", "bid", "ask")
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    VOLUME_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    BID_FIELD_NUMBER: _ClassVar[int]
    ASK_FIELD_NUMBER: _ClassVar[int]
    symbol: str
    price: float
    volume: float
    timestamp: int
    bid: float
    ask: float
    def __init__(
        self,
        symbol: _Optional[str] = ...,
        price: _Optional[float] = ...,
        volume: _Optional[float] = ...,
        timestamp: _Optional[int] = ...,
        bid: _Optional[float] = ...,
        ask: _Optional[float] = ...,
    ) -> None: ...
