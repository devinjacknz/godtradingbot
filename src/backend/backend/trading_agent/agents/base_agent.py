from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAgent(ABC):
    def __init__(self, agent_id: str, name: str, config: Dict[str, Any]):
        self.agent_id = agent_id
        self.name = name
        self.config = config
        self.status = "inactive"
        self.last_update = None

    @abstractmethod
    async def start(self):
        """Start the agent's operations"""
        pass

    @abstractmethod
    async def stop(self):
        """Stop the agent's operations"""
        pass

    @abstractmethod
    async def update_config(self, new_config: Dict[str, Any]):
        """Update agent configuration"""
        pass

    def get_status(self) -> Dict[str, Any]:
        """Get agent's current status"""
        return {
            "id": self.agent_id,
            "name": self.name,
            "status": self.status,
            "last_update": self.last_update,
            "config": self.config,
        }
