from datetime import datetime
from decimal import Decimal
import httpx
import logging
from typing import Dict, List, Optional
from fastapi import HTTPException

from src.shared.models.meme_trading import MemeOrder, MemeOpportunity
from src.backend.monitoring.metrics import TradingMetrics
from src.backend.monitoring.alerts import AlertManager
from src.backend.monitoring.audit_log import AuditLogger

logger = logging.getLogger(__name__)

class MemeManager:
    def __init__(self):
        self._metrics = TradingMetrics()
        self._alert_manager = AlertManager()
        self._audit_logger = AuditLogger()
        self._min_market_cap = Decimal("100000")
        self._min_volume = Decimal("50000")
        self._min_holders = 1000
        self._max_risk = Decimal("0.7")
        
    async def execute_trade(self, order: MemeOrder) -> Dict:
        try:
            validation = await self.validate_token(order.symbol)
            if not validation["is_valid"]:
                raise HTTPException(400, f"Invalid token: {validation['reason']}")
                
            metrics = await self.get_token_metrics(order.symbol)
            
            if Decimal(str(metrics["market_cap"])) < self._min_market_cap:
                raise HTTPException(400, f"Market cap too low (min: ${self._min_market_cap:,.2f})")
                
            if Decimal(str(metrics["volume_24h"])) < self._min_volume:
                raise HTTPException(400, f"Volume too low (min: ${self._min_volume:,.2f})")
                
            if metrics["holders"] < self._min_holders:
                raise HTTPException(400, f"Too few holders (min: {self._min_holders:,})")
                
            from src.backend.services.dex.aggregator import DEXAggregator
            dex = DEXAggregator()
            
            quote = await dex.get_best_quote(
                order.symbol,
                "USDC",
                order.amount
            )
            
            if quote["price_impact"] > order.max_slippage:
                raise HTTPException(400, f"Price impact too high: {quote['price_impact']*100:.2f}%")
                
            result = await dex.execute_swap(quote)
            
            await self._audit_logger.log_event(
                "meme_trade",
                order.symbol,
                {
                    "side": order.side,
                    "amount": str(order.amount),
                    "price": str(quote["price"]),
                    "tx_hash": result["transaction_hash"]
                }
            )
            
            self._metrics.meme_trade_volume.inc(float(order.amount))
            self._metrics.meme_trade_count.inc()
            
            return {
                "status": "completed",
                "transaction_hash": result["transaction_hash"],
                "filled_amount": result["output_amount"],
                "price": result["price"],
                "fee": result["fee"]
            }
            
        except Exception as e:
            logger.error(f"Meme trade execution failed: {str(e)}")
            raise HTTPException(500, f"Trade execution failed: {str(e)}")
    
    async def scan_opportunities(
        self,
        min_market_cap: Decimal = Decimal("100000"),
        min_volume: Decimal = Decimal("50000"),
        min_holders: int = 1000,
        max_risk: Decimal = Decimal("0.7")
    ) -> List[MemeOpportunity]:
        try:
            tokens = await self._get_potential_tokens()
            opportunities = []
            
            for token in tokens:
                try:
                    metrics = await self.get_token_metrics(token["symbol"])
                    
                    if (Decimal(str(metrics["market_cap"])) >= min_market_cap and
                        Decimal(str(metrics["volume_24h"])) >= min_volume and
                        metrics["holders"] >= min_holders):
                        
                        score = self._calculate_opportunity_score(metrics)
                        
                        if score <= max_risk:
                            opportunities.append(
                                MemeOpportunity(
                                    symbol=token["symbol"],
                                    market_cap=Decimal(str(metrics["market_cap"])),
                                    volume_24h=Decimal(str(metrics["volume_24h"])),
                                    price=Decimal(str(metrics["price"])),
                                    holders=metrics["holders"],
                                    score=score,
                                    timestamp=datetime.utcnow(),
                                    metrics=metrics,
                                    signals=self._generate_signals(metrics)
                                )
                            )
                            
                except Exception as e:
                    logger.warning(f"Failed to process token {token['symbol']}: {str(e)}")
                    continue
            
            opportunities.sort(key=lambda x: x.score)
            return opportunities
            
        except Exception as e:
            logger.error(f"Opportunity scanning failed: {str(e)}")
            raise HTTPException(500, f"Scanning failed: {str(e)}")
    
    async def get_token_metrics(self, symbol: str) -> Dict:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.pump.fun/v1/tokens/{symbol}/metrics"
                )
                response.raise_for_status()
                data = response.json()
                
            return {
                "market_cap": Decimal(str(data["market_cap"])),
                "volume_24h": Decimal(str(data["volume_24h"])),
                "price": Decimal(str(data["price"])),
                "holders": int(data["holders"]),
                "liquidity": Decimal(str(data["liquidity"])),
                "price_change_24h": Decimal(str(data["price_change_24h"])),
                "social_score": Decimal(str(data["social_score"])),
                "risk_score": Decimal(str(data["risk_score"]))
            }
            
        except Exception as e:
            logger.error(f"Failed to get token metrics: {str(e)}")
            raise HTTPException(500, f"Failed to get metrics: {str(e)}")
    
    async def validate_token(self, symbol: str) -> Dict:
        try:
            if not symbol or "/" not in symbol:
                return {
                    "is_valid": False,
                    "reason": "Invalid symbol format"
                }
                
            metrics = await self.get_token_metrics(symbol)
            contract_validation = await self._validate_contract(symbol)
            
            if not contract_validation["is_valid"]:
                return contract_validation
                
            red_flags = []
            
            if metrics["risk_score"] > Decimal("0.7"):
                red_flags.append("High risk score")
                
            if metrics["holders"] < 100:
                red_flags.append("Very few holders")
                
            if metrics["liquidity"] < Decimal("10000"):
                red_flags.append("Low liquidity")
                
            return {
                "is_valid": len(red_flags) == 0,
                "reason": ", ".join(red_flags) if red_flags else None,
                "risk_score": metrics["risk_score"],
                "contract_verified": contract_validation["contract_verified"]
            }
            
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            return {
                "is_valid": False,
                "reason": f"Validation failed: {str(e)}"
            }
    
    async def _get_potential_tokens(self) -> List[Dict]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.pump.fun/v1/tokens/trending"
                )
                response.raise_for_status()
                return response.json()["tokens"]
        except Exception as e:
            logger.error(f"Failed to get potential tokens: {str(e)}")
            return []
    
    async def _validate_contract(self, symbol: str) -> Dict:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.pump.fun/v1/tokens/{symbol}/contract"
                )
                response.raise_for_status()
                data = response.json()
                
            return {
                "is_valid": data["is_valid"],
                "reason": data.get("reason"),
                "contract_verified": data["verified"]
            }
        except Exception as e:
            logger.error(f"Contract validation failed: {str(e)}")
            return {
                "is_valid": False,
                "reason": f"Validation failed: {str(e)}"
            }
    
    def _calculate_opportunity_score(self, metrics: Dict) -> Decimal:
        try:
            weights = {
                "risk_score": Decimal("0.4"),
                "market_cap": Decimal("0.2"),
                "volume_24h": Decimal("0.2"),
                "social_score": Decimal("0.2")
            }
            
            normalized = {
                "risk_score": metrics["risk_score"],
                "market_cap": Decimal("1") - min(metrics["market_cap"] / Decimal("1000000"), Decimal("1")),
                "volume_24h": Decimal("1") - min(metrics["volume_24h"] / Decimal("100000"), Decimal("1")),
                "social_score": Decimal("1") - metrics["social_score"]
            }
            
            score = sum(normalized[k] * weights[k] for k in weights)
            return min(max(score, Decimal("0")), Decimal("1"))
            
        except Exception as e:
            logger.error(f"Score calculation failed: {str(e)}")
            return Decimal("1")
    
    def _generate_signals(self, metrics: Dict) -> List[str]:
        signals = []
        
        if metrics["price_change_24h"] > Decimal("0.1"):
            signals.append("Strong upward momentum")
            
        if metrics["volume_24h"] > metrics["market_cap"] * Decimal("0.1"):
            signals.append("High volume relative to market cap")
            
        if metrics["social_score"] > Decimal("0.7"):
            signals.append("High social activity")
            
        if metrics["holders"] > 10000:
            signals.append("Large holder base")
            
        return signals
