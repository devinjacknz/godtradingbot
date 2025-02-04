from datetime import datetime
from typing import Dict, List, Optional

from app.models.agent_models import AgentCreate, AgentResponse, AgentUpdate


class AgentManager:
    def __init__(self):
        self.agents: Dict[str, Dict] = {}

    async def create_agent(self, agent_data: AgentCreate) -> AgentResponse:
        agent_id = f"agent_{datetime.utcnow().timestamp()}"
        agent = {
            "id": agent_id,
            "name": agent_data.name,
            "type": agent_data.type,
            "parameters": agent_data.parameters,
            "description": agent_data.description,
            "status": "initialized",
            "created_at": datetime.utcnow(),
            "last_update": datetime.utcnow(),
        }
        self.agents[agent_id] = agent
        return AgentResponse(**agent)

    async def get_agent(self, agent_id: str) -> Optional[AgentResponse]:
        agent = self.agents.get(agent_id)
        if not agent:
            return None
        return AgentResponse(**agent)

    async def list_agents(self) -> List[AgentResponse]:
        return [AgentResponse(**agent) for agent in self.agents.values()]

    async def update_agent(
        self, agent_id: str, update_data: AgentUpdate
    ) -> Optional[AgentResponse]:
        if agent_id not in self.agents:
            return None

        agent = self.agents[agent_id]
        update_dict = update_data.dict(exclude_unset=True)

        for key, value in update_dict.items():
            if value is not None:
                agent[key] = value

        agent["last_update"] = datetime.utcnow()
        return AgentResponse(**agent)

    async def delete_agent(self, agent_id: str) -> bool:
        if agent_id in self.agents:
            del self.agents[agent_id]
            return True
        return False

    async def start_agent(self, agent_id: str) -> Optional[AgentResponse]:
        if agent_id not in self.agents:
            return None

        self.agents[agent_id]["status"] = "active"
        self.agents[agent_id]["last_update"] = datetime.utcnow()
        return AgentResponse(**self.agents[agent_id])

    async def stop_agent(self, agent_id: str) -> Optional[AgentResponse]:
        if agent_id not in self.agents:
            return None

        self.agents[agent_id]["status"] = "stopped"
        self.agents[agent_id]["last_update"] = datetime.utcnow()
        return AgentResponse(**self.agents[agent_id])
