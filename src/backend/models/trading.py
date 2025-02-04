from enum import Enum

from sqlalchemy import JSON, Boolean, Column
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class StrategyType(str, Enum):
    TECHNICAL_ANALYSIS = "technical_analysis"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    MARKET_MAKING = "market_making"
    ARBITRAGE = "arbitrage"


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"))
    address = Column(String, unique=True)
    chain = Column(String)
    balance = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"))
    name = Column(String)
    strategy_type = Column(SQLEnum(StrategyType))
    parameters = Column(JSON)
    is_active = Column(Boolean, default=True)
