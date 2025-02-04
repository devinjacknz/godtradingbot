from typing import Dict, List, Optional, Union

from ..agents.base_agent import BaseAgent
from ..agents.fundamentals_agent import FundamentalsAgent
from ..agents.market_data_agent import MarketDataAgent
from ..agents.portfolio_manager_agent import PortfolioManagerAgent
from ..agents.risk_manager_agent import RiskManagerAgent
from ..agents.sentiment_agent import SentimentAgent
from ..agents.technical_analyst_agent import TechnicalAnalystAgent
from ..agents.trading_agent import TradingAgent
from ..agents.valuation_agent import ValuationAgent

AgentType = Union[
    TradingAgent,
    MarketDataAgent,
    ValuationAgent,
    SentimentAgent,
    FundamentalsAgent,
    TechnicalAnalystAgent,
    RiskManagerAgent,
    PortfolioManagerAgent,
]


class AgentManager:
    def __init__(self):
        self.agents: Dict[str, AgentType] = {}

    async def create_agent(
        self, agent_id: str, name: str, config: Dict
    ) -> TradingAgent:
        """Create a new trading agent"""
        if agent_id in self.agents:
            raise ValueError(f"Agent with ID {agent_id} already exists")

        agent = TradingAgent(agent_id, name, config)
        self.agents[agent_id] = agent
        return agent

    async def create_specialized_agent(
        self, agent_type: str, agent_id: str, name: str, config: Dict
    ) -> AgentType:
        if agent_id in self.agents:
            raise ValueError(f"Agent with ID {agent_id} already exists")

        agent: AgentType
        if agent_type == "market_data":
            agent = MarketDataAgent(agent_id, name, config)
        elif agent_type == "valuation":
            agent = ValuationAgent(agent_id, name, config)
        elif agent_type == "sentiment":
            agent = SentimentAgent(agent_id, name, config)
        elif agent_type == "fundamentals":
            agent = FundamentalsAgent(agent_id, name, config)
        elif agent_type == "technical":
            agent = TechnicalAnalystAgent(agent_id, name, config)
        elif agent_type == "risk":
            agent = RiskManagerAgent(agent_id, name, config)
        elif agent_type == "portfolio":
            agent = PortfolioManagerAgent(agent_id, name, config)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")

        self.agents[agent_id] = agent
        return agent

    async def get_agent(self, agent_id: str) -> Optional[AgentType]:
        """Get an agent by ID"""
        return self.agents.get(agent_id)

    async def update_agent(self, agent_id: str, config: Dict) -> Optional[AgentType]:
        """Update an existing agent's configuration"""
        agent = await self.get_agent(agent_id)
        if agent:
            await agent.update_config(config)
            return agent
        return None

    async def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent"""
        agent = await self.get_agent(agent_id)
        if agent:
            await agent.stop()
            del self.agents[agent_id]
            return True
        return False

    async def start_agent(self, agent_id: str) -> bool:
        """Start an agent's operations"""
        agent = await self.get_agent(agent_id)
        if agent:
            try:
                await agent.start()
                agent.status = "active"
                return True
            except Exception as e:
                agent.status = "error"
                return False
        return False

    async def stop_agent(self, agent_id: str) -> bool:
        """Stop an agent's operations"""
        agent = await self.get_agent(agent_id)
        if agent:
            await agent.stop()
            return True
        return False

    def get_all_agents(self) -> List[Dict]:
        """Get status of all agents"""
        return [agent.get_status() for agent in self.agents.values()]

    async def stop_all_agents(self):
        """Stop all running agents"""
        for agent in self.agents.values():
            if agent.status == "active":
                await agent.stop()
