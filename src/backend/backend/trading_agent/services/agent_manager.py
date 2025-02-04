from typing import Dict, List, Optional

from ..agents.trading_agent import TradingAgent


class AgentManager:
    def __init__(self):
        self.agents: Dict[str, TradingAgent] = {}

    async def create_agent(
        self, agent_id: str, name: str, config: Dict
    ) -> TradingAgent:
        """Create a new trading agent"""
        if agent_id in self.agents:
            raise ValueError(f"Agent with ID {agent_id} already exists")

        agent = TradingAgent(agent_id, name, config)
        self.agents[agent_id] = agent
        return agent

    async def get_agent(self, agent_id: str) -> Optional[TradingAgent]:
        """Get an agent by ID"""
        return self.agents.get(agent_id)

    async def update_agent(self, agent_id: str, config: Dict) -> Optional[TradingAgent]:
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
            await agent.start()
            return True
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
