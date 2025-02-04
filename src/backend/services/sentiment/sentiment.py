from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class SentimentAnalysis(Base):
    """Sentiment analysis results model."""

    __tablename__ = "sentiment_analysis"

    id = Column(Integer, primary_key=True)
    source_id = Column(String, unique=True, nullable=False)
    score = Column(Float, nullable=False)
    sentiment = Column(String, nullable=False)
    language = Column(String(2), nullable=False)
    raw_text = Column(Text)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
